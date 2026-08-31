import os
import asyncio
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from playwright.async_api import async_playwright

# --- Set Playwright browser path for Render ---
PLAYWRIGHT_BROWSERS_PATH = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/render/project/.cache/playwright")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = PLAYWRIGHT_BROWSERS_PATH

# --- Flask app ---
app = Flask(__name__)
PORT = int(os.environ.get("PORT", 8000))

# --- Telegram Bot Setup ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("No TELEGRAM_BOT_TOKEN set in environment variables")

# --- Create bot application ---
bot_app = Application.builder().token(TELEGRAM_TOKEN).build()

# --- Routes ---
@app.route('/')
def health():
    return "Bot is running!", 200

@app.route('/webhook', methods=['POST'])
async def webhook():
    """Handle incoming Telegram updates via webhook."""
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, bot_app.bot)
        await bot_app.process_update(update)
        return "OK", 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **Web Scraper Bot**\n\n"
        "Send /scrape followed by a URL\n"
        "Example: `/scrape https://example.com`\n\n"
        "I'll return:\n"
        "• Page title\n"
        "• Meta description\n"
        "• First 5 links\n"
        "• First 3 images\n\n"
        "⚠️ Large or slow sites may take up to 60 seconds."
    )

async def scrape(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /scrape https://example.com")
        return

    url = context.args[0]
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    await update.message.reply_text(f"🔍 Scraping {url}... (this may take up to 60 seconds)")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            page = await browser.new_page()

            # --- 60-second timeout ---
            await page.goto(url, timeout=60000, wait_until='domcontentloaded')

            # --- Extract data ---
            title = await page.title()
            description = await page.get_attribute('meta[name="description"]', 'content') or "No description found"

            links = await page.eval_on_selector_all(
                'a[href]',
                'els => els.slice(0,5).map(el => el.href)'
            )

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
                    display_link = link[:80] + "..." if len(link) > 80 else link
                    response += f"{i}. {display_link}\n"
            else:
                response += "No links found\n"

            response += f"\n🖼️ **Images ({len(images)} found):**\n"
            if images:
                for i, img in enumerate(images, 1):
                    display_img = img[:80] + "..." if len(img) > 80 else img
                    response += f"{i}. {display_img}\n"
            else:
                response += "No images found\n"

            if len(response) > 4000:
                response = response[:4000] + "... (truncated)"

            await update.message.reply_text(response)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")

# --- Register handlers ---
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("scrape", scrape))

# --- Main Function ---
def main():
    # Set webhook
    webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'test-webscraper-ok3c.onrender.com')}/webhook"
    
    async def set_webhook():
        await bot_app.bot.delete_webhook(drop_pending_updates=True)
        await bot_app.bot.set_webhook(url=webhook_url)
        print(f"Webhook set to: {webhook_url}")
    
    asyncio.run(set_webhook())
    
    # Start Flask server
    print(f"Starting Flask server on port {PORT}...")
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()
