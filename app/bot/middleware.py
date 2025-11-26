from telegram import Update
from telegram.ext import ContextTypes
from functools import wraps
from app.database import AsyncSessionLocal
from app.services import user_service
from loguru import logger


def check_user_blocked(func):
    """Decorator to check if user is blocked"""
    @wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # Skip for admin commands
        if update.message and update.message.text and update.message.text.startswith('/admin'):
            return await func(self, update, context, *args, **kwargs)
        
        user_id = update.effective_user.id
        
        async with AsyncSessionLocal() as db:
            user = await user_service.get_user_by_telegram_id(db, user_id)
            
            if user and user.blocked:
                if update.message:
                    await update.message.reply_text(
                        "🚫 *Your account has been blocked.*\n\n"
                        f"Reason: {user.blocked_reason or 'Policy violation'}\n\n"
                        "Contact support for more information.",
                        parse_mode='Markdown'
                    )
                elif update.callback_query:
                    await update.callback_query.answer(
                        "🚫 Your account is blocked.",
                        show_alert=True
                    )
                return
        
        return await func(self, update, context, *args, **kwargs)
    
    return wrapper