#!/usr/bin/env python3
"""
Script to run the Telegram bot
"""
from loguru import logger

from app.telegram_bot import start_bot
from app.core.config import settings


def main():
    """Main function"""
    logger.info("=" * 50)
    logger.info(f"Starting {settings.APP_NAME}")
    logger.info("=" * 50)
    
    try:
        start_bot()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise


if __name__ == "__main__":
    main()