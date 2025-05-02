import os
import logging
import aiohttp
from aiohttp import web
import json
import httpx

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8000))

if not TOKEN or not WEBHOOK_URL:
    logger.error("Missing TOKEN or WEBHOOK_URL environment variables")
    raise ValueError("TOKEN and WEBHOOK_URL must be set")

# Telegram API base URL
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

async def set_webhook():
    """Set the Telegram webhook on startup."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{TELEGRAM_API}/setWebhook",
                json={"url": WEBHOOK_URL}
            )
            if response.status_code == 200:
                logger.info("Webhook set successfully: %s", response.json())
            else:
                logger.error("Failed to set webhook: %s", response.json())
        except Exception as e:
            logger.error("Error setting webhook: %s", e)

async def send_message(chat_id, text):
    """Send a message to a Telegram chat."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{TELEGRAM_API}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text
                }
            )
            if response.status_code == 200:
                logger.info("Message sent to chat %s", chat_id)
            else:
                logger.error("Failed to send message: %s", response.json())
        except Exception as e:
            logger.error("Error sending message: %s", e)

async def handle_update(update):
    """Process incoming Telegram updates."""
    try:
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")

        if not chat_id:
            logger.warning("No chat_id found in update")
            return

        # Handle commands
        if text.startswith("/start"):
            await send_message(chat_id, "Welcome to MayBot! Use /help to see available commands.")
        elif text.startswith("/help"):
            await send_message(chat_id, "Available commands:\n/start - Start the bot\n/help - Show this help message")
        else:
            await send_message(chat_id, "Echo: " + text)

    except Exception as e:
        logger.error("Error processing update: %s", e)

async def webhook(request):
    """Handle incoming webhook requests from Telegram."""
    try:
        data = await request.json()
        logger.info("Received update: %s", data)
        await handle_update(data)
        return web.Response(status=200)
    except json.JSONDecodeError:
        logger.error("Invalid JSON received")
        return web.Response(status=400)
    except Exception as e:
        logger.error("Webhook error: %s", e)
        return web.Response(status=500)

async def on_startup(app):
    """Run on server startup."""
    await set_webhook()

def create_app():
    """Create and configure the aiohttp application."""
    app = web.Application()
    app.router.add_post("/webhook", webhook)
    app.on_startup.append(on_startup)
    return app

if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=PORT)
