import os
import time
from threading import Thread
from http.server import HTTPServer, SimpleHTTPRequestHandler
from dotenv import load_dotenv
import telebot

load_dotenv()

# 1. Render Health Check Bypass (Dummy HTTP Server)
def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

Thread(target=run_dummy_server, daemon=True).start()

# 2. Import Agent Runtime
from agent.runtime import GODFLEXRuntime, QuotaExceededError

class GODFLEX:
    """Public application facade backed by the persistent GODFLEX runtime."""

    def __init__(self):
        self.runtime = GODFLEXRuntime()
        self.current_plan = self.runtime.core.memory.latest_plan()

    @property
    def conversation(self):
        return self.runtime.recent_chat(20)

    def chat(self, message: str) -> str:
        context = self._conversation_context()
        return self.runtime.chat(message=message, context=context)

    def _conversation_context(self) -> str:
        messages = self.runtime.recent_chat(20)
        return "\n".join(
            f'{item["role"]}: {item["content"]}'
            for item in messages
        )

# 3. Telegram Bot Integration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_TOKEN:
    print("CRITICAL ERROR: TELEGRAM_BOT_TOKEN environment variable is not set!")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
godflex = GODFLEX()

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "🔥 GODFLEX Autonomous Agent is online and connected to Telegram! Bhej apna query.")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_text = message.text
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            response = godflex.chat(user_text)
            bot.reply_to(message, response)
            break
        except QuotaExceededError as error:
            bot.reply_to(message, f"⚠️ GODFLEX paused: {error}")
            break
        except Exception as error:
            err_msg = str(error)
            # Handle Gemini 503 / High Demand Spikes automatically
            if ("503" in err_msg or "UNAVAILABLE" in err_msg) and attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))  # Wait 2s, then 4s
                continue
            
            bot.reply_to(message, f"❌ Error: {err_msg}")
            break

if __name__ == "__main__":
    print("GODFLEX Autonomous Service is live and listening on Telegram...")
    # Clear any old webhooks/locks on start
    try:
        bot.remove_webhook()
    except Exception:
        pass
    bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
    
