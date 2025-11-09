from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from loguru import logger

from app.core.config import settings
from app.bot import bot_handlers, voice_handler, message_handler, admin_handlers


def setup_bot() -> Application:
    """Set up and configure the bot"""
    
    # Create application
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    
    logger.info("Setting up bot handlers...")
    
    # User commands
    application.add_handler(CommandHandler("start", bot_handlers.start_command))
    application.add_handler(CommandHandler("help", message_handler.show_help))
    
    # Admin commands
    application.add_handler(CommandHandler("admin_panel", admin_handlers.admin_panel))
    application.add_handler(CommandHandler("add_video", admin_handlers.handle_add_video_command))
    application.add_handler(CommandHandler("set_phrase", admin_handlers.handle_set_phrase))
    application.add_handler(CommandHandler("finalize_video", admin_handlers.handle_finalize_video))
    application.add_handler(CommandHandler("create_challenge", admin_handlers.handle_create_challenge))
    
    # Contact handler (phone number sharing)
    application.add_handler(
        MessageHandler(filters.CONTACT, bot_handlers.handle_contact)
    )
    
    # Voice message handler
    application.add_handler(
        MessageHandler(filters.VOICE, voice_handler.handle_voice)
    )
    
    # Video upload handler (for admins)
    application.add_handler(
        MessageHandler(
            filters.VIDEO & filters.User(user_id=settings.admin_ids),
            admin_handlers.handle_video_upload
        )
    )
    
    # Text message handler
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler.handle_text_message)
    )
    
    # Callback query handlers
    application.add_handler(
        CallbackQueryHandler(
            bot_handlers.handle_activation_callback,
            pattern="^activate_"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            admin_handlers.handle_admin_callback,
            pattern="^admin_"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            admin_handlers.handle_admin_callback,
            pattern="^approve_payment_"
        )
    )
    
    logger.success("Bot handlers configured successfully!")
    
    return application


async def start_bot():
    """Start the bot"""
    logger.info("Starting Telegram bot...")
    
    application = setup_bot()
    
    logger.info("Bot is running! Press Ctrl+C to stop.")
    
    # Start the bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=["message", "callback_query"])
    
    # Run until stopped
    await application.updater.idle()
    
    # Cleanup
    await application.stop()
    await application.shutdown()


if __name__ == "__main__":
    import asyncio
    asyncio.run(start_bot())
