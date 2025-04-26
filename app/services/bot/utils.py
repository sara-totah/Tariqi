"""Utility functions for the Telegram Bot service."""

import logging
from telegram import Bot
from telegram.error import TelegramError

from app.settings import settings

logger = logging.getLogger(__name__)

async def set_telegram_webhook():
    """Sets the Telegram bot webhook using the URL from settings."""
    bot_token = settings.telegram_bot_token
    webhook_url = settings.webhook_url

    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set. Cannot set webhook.")
        return False
    if not webhook_url:
        logger.error("WEBHOOK_URL not set. Cannot set webhook.")
        return False

    bot = Bot(token=bot_token)
    logger.info(f"Attempting to set Telegram webhook to: {webhook_url}")

    try:
        # The set_webhook method returns True on success
        success = await bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message"],  # Only process new messages
            # Consider adding drop_pending_updates=True if needed
        )
        if success:
            logger.info(f"Successfully set Telegram webhook to {webhook_url}")
            # Optionally, verify the webhook info
            # webhook_info = await bot.get_webhook_info()
            # logger.info(f"Current webhook info: {webhook_info}")
            return True
        else:
            logger.error("Telegram API call set_webhook returned False.")
            return False
    except TelegramError as e:
        logger.error(f"TelegramError while setting webhook: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Unexpected error while setting webhook: {e}", exc_info=True)
        return False 