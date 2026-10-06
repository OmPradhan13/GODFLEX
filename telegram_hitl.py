import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

class HITLManager:
    def __init__(self, bot_app):
        self.app = bot_app
        self.owner_chat_id = os.environ.get("OWNER_CHAT_ID")

    async def request_approval(self, task_id: str, title: str, details: str, projected_revenue: float):
        """Background agent triggers this to send approval request to owner."""
        if not self.owner_chat_id:
            logger.error("OWNER_CHAT_ID missing in environment variables!")
            return

        owner_payout = projected_revenue * 0.95
        agent_pool = projected_revenue * 0.05

        message_text = (
            f"⚡ *AUTONOMOUS ACTION APPROVAL REQUIRED*\n\n"
            f"📌 *Task:* {title}\n"
            f"📝 *Details:* {details}\n\n"
            f"💰 *Projected Revenue:* ${projected_revenue:.2f}\n"
            f"├─ 👤 *Owner Payout (95%):* ${owner_payout:.2f}\n"
            f"└─ 🤖 *Agent Pool (5%):* ${agent_pool:.2f}\n\n"
            f"Do you authorize execution?"
        )

        keyboard = [
            [
                InlineKeyboardButton("Approve ✅", callback_data=f"approve_{task_id}"),
                InlineKeyboardButton("Reject ❌", callback_data=f"reject_{task_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self.app.bot.send_message(
            chat_id=self.owner_chat_id,
            text=message_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles Approve/Reject button clicks from Telegram."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("approve_"):
        task_id = data.replace("approve_", "")
        await query.edit_message_text(text=f"✅ *Task {task_id} Approved!* Executing deployment and processing 95% payout routing.", parse_mode='Markdown')
        # Trigger actual action execution logic here
    elif data.startswith("reject_"):
        task_id = data.replace("reject_", "")
        await query.edit_message_text(text=f"❌ *Task {task_id} Rejected.* Aborting operation.", parse_mode='Markdown')
    
