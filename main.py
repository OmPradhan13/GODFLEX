import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from agent.runtime import GODFLEXRuntime, QuotaExceededError
from agent.telegram_hitl import HITLManager, handle_approval_callback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

runtime = GODFLEXRuntime()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🤖 *GODFLEX Autonomous System Active*\n\n"
        "Operating Mode: Background Autonomous Engine\n"
        "Profit Protocol: 95% Owner / 5% Agent Pool\n\n"
        "Main 24/7 background me tasks process kar raha hu. Critical decisions par permission maangunga."
    )
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def test_hitl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test command to trigger an approval notification."""
    app = context.application
    hitl = HITLManager(app)
    await hitl.request_approval(
        task_id="TEST_001",
        title="Micro-SaaS API Deployment",
        details="Automated Lead Scraping Tool setup completed. Ready to launch.",
        projected_revenue=100.00
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message.text
    try:
        response = runtime.chat(user_msg)
        await update.message.reply_text(response)
    except QuotaExceededError:
        await update.message.reply_text("⚠️ API Quota reach ho gaya hai. Render par GEMINI_API_KEY update karein.")
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN missing!")
        
    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("testhitl", test_hitl))
    app.add_handler(CallbackQueryHandler(handle_approval_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("GODFLEX Agent Started...")
    app.run_polling()

if __name__ == "__main__":
    main()
