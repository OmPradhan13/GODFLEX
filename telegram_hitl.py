"""
Standalone Telegram HITL service for GODFLEX.

Run this in a separate process on the server:

    python telegram_hitl.py

GODFLEX creates approval rows and sends messages through the Telegram Bot API.
This process receives inline-button callbacks and writes the human decision
back into the same SQLite database.
"""

import json
import os
import time
import urllib.parse
import urllib.request

from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("GODFLEX_DB_PATH", "data/godflex.db")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
APPROVAL_TIMEOUT_SECONDS = int(os.getenv("TELEGRAM_APPROVAL_TIMEOUT_SECONDS", "86400"))


def _db():
    import sqlite3
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _ensure_db():
    from agent.memory import GODFLEXMemory
    GODFLEXMemory(DB_PATH)


def _telegram_api(method: str, data: dict):
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")

    encoded = urllib.parse.urlencode(data).encode("utf-8")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"

    request = urllib.request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API error: {payload}")

    return payload["result"]


def send_approval_message(task_id: str, name: str, description: str):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError(
            "Telegram HITL requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."
        )

    text = (
        "GODFLEX approval required\n\n"
        f"Task: {name}\n"
        f"ID: {task_id}\n\n"
        f"{description}\n\n"
        "Choose an action:"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "Approve", "callback_data": f"godflex:approve:{task_id}"},
                {"text": "Reject", "callback_data": f"godflex:reject:{task_id}"},
            ]
        ]
    }

    return _telegram_api(
        "sendMessage",
        {
            "chat_id": CHAT_ID,
            "text": text,
            "reply_markup": json.dumps(keyboard),
        },
    )


def request_approval(task_id: str, name: str, description: str) -> bool:
    """
    Called by the GODFLEX process.

    It creates a pending approval, sends the Telegram message, then blocks
    until the bot process records approved/rejected/expired.
    """
    _ensure_db()

    from agent.memory import GODFLEXMemory
    memory = GODFLEXMemory(DB_PATH)
    memory.create_approval(task_id)

    send_approval_message(task_id, name, description)

    deadline = time.time() + APPROVAL_TIMEOUT_SECONDS

    while time.time() < deadline:
        approval = memory.get_approval(task_id)

        if approval:
            status = approval["status"]
            if status == "approved":
                return True
            if status == "rejected":
                return False
            if status == "expired":
                return False

        time.sleep(1)

    memory.set_approval(task_id, "expired")
    return False


def run_bot():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")

    if not CHAT_ID:
        raise RuntimeError("TELEGRAM_CHAT_ID is not configured.")

    _ensure_db()

    import telebot

    bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("godflex:")
    )
    def handle_callback(call):
        if str(call.message.chat.id) != str(CHAT_ID):
            bot.answer_callback_query(
                call.id,
                "This approval bot is not authorized for this chat.",
                show_alert=True,
            )
            return

        parts = call.data.split(":", 2)
        if len(parts) != 3:
            bot.answer_callback_query(call.id, "Invalid approval request.")
            return

        _, action, task_id = parts

        from agent.memory import GODFLEXMemory
        memory = GODFLEXMemory(DB_PATH)

        status = "approved" if action == "approve" else "rejected"
        changed = memory.set_approval(
            task_id=task_id,
            status=status,
            decided_by=str(call.from_user.id),
        )

        if changed:
            label = "APPROVED" if status == "approved" else "REJECTED"
            bot.answer_callback_query(call.id, label)
            bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=None,
            )
            bot.send_message(
                call.message.chat.id,
                f"GODFLEX: task {task_id} {label.lower()}.",
            )
        else:
            bot.answer_callback_query(
                call.id,
                "This request is no longer pending.",
                show_alert=True,
            )

    print("GODFLEX Telegram HITL bot is running.")
    bot.infinity_polling(skip_pending=True)


if __name__ == "__main__":
    run_bot()
