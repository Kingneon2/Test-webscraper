import os
import asyncio
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from playwright.async_api import async_playwright

# --- Set Playwright browser path for Render ---
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
        "🤖 Web Scraper Bot\n\n"
        "Send /scrape followed by a URL\n"
        "Example: /scrape https://example.com\n\n"
        "I'll return:\n"
        "• Page title\n"
        "• Meta description\n"
        "• First 5 links\n"
        "• First 3 images"
    )

async def scrape(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /scrape https://example.com")
        return

    url = context.args[0]
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    await update.message.reply_text(f"🔍 Scraping {url}...")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            page = await browser.new_page()
            await page.goto(url, timeout=30000)

            # --- Extract data ---
            title = await page.title()
            
            # Meta description
            description = await page.get_attribute('meta[name="description"]', 'content')
            if not description:
                description = "No description found"
            
            # Get first 5 links
            links = await page.eval_on_selector_all(
                'a[href]', 
                'els => els.slice(0,5).map(el => el.href)'
            )
            
            # Get first 3 images
            images = await page.eval_on_selector_all(
                'img[src]', 
                'els => els.slice(0,3).map(el => el.src)'
            )

            await browser.close()

            # --- Build response ---
            response = f"📄 **Title:** {title}\n"
            response += f"📝 **Description:** {description[:200]}...\n\n"
            
            response += f"🔗 **Links ({len(links)} found):**\n"
            if links:
                for i, link in enumerate(links, 1):
                    response += f"{i}. {link[:80]}...\n" if len(link) > 80 else f"{i}. {link}\n"
            else:
                response += "No links found\n"
            
            response += f"\n🖼️ **Images ({len(images)} found):**\n"
            if images:
                for i, img in enumerate(images, 1):
                    response += f"{i}. {img[:80]}...\n" if len(img) > 80 else f"{i}. {img}\n"
            else:
                response += "No images found\n"

            # Truncate if too long for Telegram
            if len(response) > 4000:
                response = response[:4000] + "... (truncated)"

            await update.message.reply_text(response)

    except Exception as e:
        error_msg = str(e)[:200]
        await update.message.reply_text(f"❌ Error: {error_msg}")

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

    print("🤖 Bot is running...")
    bot_app.run_polling(allowed_updates=[])

if __name__ == "__main__":
    main()
