import os
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
    try:
        user_text = message.text
        response = godflex.chat(user_text)
        bot.reply_to(message, response)
    except QuotaExceededError as error:
        bot.reply_to(message, f"⚠️ GODFLEX paused: {error}")
    except Exception as error:
        bot.reply_to(message, f"❌ Error: {str(error)}")

if __name__ == "__main__":
    print("GODFLEX Autonomous Service is live and listening on Telegram...")
    bot.infinity_polling(skip_pending=True)
    
