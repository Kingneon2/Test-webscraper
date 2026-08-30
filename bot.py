import os
import asyncio
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from playwright.async_api import async_playwright

# --- Set Playwright browser path for Render ---
# This ensures Playwright looks in the right place for Chromium
PLAYWRIGHT_BROWSERS_PATH = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/render/project/.cache/playwright")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = PLAYWRIGHT_BROWSERS_PATH

# --- Flask app for health checks ---
app = Flask(__name__)

@app.route('/')
def health():
    return "Bot is running!", 200

# --- Telegram Bot Setup ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("No TELEGRAM_BOT_TOKEN set in environment variables")

# --- Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send /scrape followed by a URL\n"
        "Example: /scrape https://example.com"
    )

async def scrape(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /scrape https://example.com")
        return

    url = context.args[0]
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    await update.message.reply_text(f"Scraping {url}...")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            page = await browser.new_page()
            await page.goto(url, timeout=30000)
            title = await page.title()
            await browser.close()
        await update.message.reply_text(f"Page title: {title}")
    except Exception as e:
        error_msg = str(e)[:200]
        await update.message.reply_text(f"Error: {error_msg}")

# --- Main Function ---
def main():
    # Start Flask server in a background thread
    def run_flask():
        app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)

    threading.Thread(target=run_flask, daemon=True).start()

    # Start Telegram bot
    bot_app = Application.builder().token(TELEGRAM_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("scrape", scrape))

    print("Bot is running...")
    bot_app.run_polling()

if __name__ == "__main__":
    main()
