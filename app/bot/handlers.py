from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import os

from app.database import AsyncSessionLocal
from app.database.models import UserStatus
from app.services import user_service, payment_service, challenge_service
from app.core.config import settings
from loguru import logger
from app.database.models import (
    User, Payment, Challenge, Video, Question, ChallengeAttempt,
    UserStatus, PaymentStatus, ChallengeStatus
)


from app.bot.rate_limiter import rate_limiter
from app.bot.middleware import check_user_blocked

class BotHandlers:
    """Main bot handlers for user interactions"""
    
    @staticmethod
    def get_db():
        """Get database session"""
        return AsyncSessionLocal()
    
    @check_user_blocked  # Add this decorator
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        # Check rate limit
        user_id = update.effective_user.id
        is_allowed, reason, cooldown = rate_limiter.check_rate_limit(user_id)
        
        if not is_allowed:
            if reason == "temp_banned":
                await update.message.reply_text(
                    f"⏸️ *Slow down!*\n\n"
                    f"You're sending messages too fast.\n"
                    f"Please wait {cooldown} seconds.",
                    parse_mode='Markdown'
                )
            elif reason == "severe_spam":
                await update.message.reply_text(
                    f"🚫 *Spam detected!*\n\n"
                    f"You've been temporarily restricted.\n"
                    f"Cooldown: {cooldown} seconds.",
                    parse_mode='Markdown'
                )
            return
        
        # Rest of your start_command code...
        user = update.effective_user
        # ... existing code ...
        # Extract referral code from /start parameter
        referral_code = None
        if context.args and len(context.args) > 0:
            referral_code = context.args[0]
            logger.info(f"User {user.id} started with referral code: {referral_code}")
        
        async with self.get_db() as db:
            # Check if user exists, create if not
            db_user = await user_service.get_user_by_telegram_id(db, user.id)
            
            if not db_user:
                db_user = await user_service.create_user(
                    db, user.id, user.username
                )
                
                # Process referral if provided
                if referral_code:
                    referrer = await user_service.get_user_by_referral_code(db, referral_code)
                    
                    if referrer and referrer.id != db_user.id:
                        await user_service.add_referral(db, referrer.id, db_user.id)
                        
                        if referrer.referral_count + 1 >= settings.REFERRAL_REQUIREMENT:
                            await user_service.activate_user(db, referrer.id)
                            
                            try:
                                await context.bot.send_message(
                                    chat_id=referrer.telegram_id,
                                    text=(
                                        "🎉 *Congratulations!*\n\n"
                                        f"You've invited {settings.REFERRAL_REQUIREMENT} friends!\n"
                                        "Your account is now *ACTIVATED!* 🚀"
                                    ),
                                    parse_mode='Markdown'
                                )
                            except Exception as e:
                                logger.error(f"Failed to notify referrer: {e}")
                
                welcome_msg = (
                    f"👋 *Welcome {user.first_name}!*\n\n"
                    "🎬 *Learn English with movie clips*\n\n"
                    "How it works:\n"
                    "1️⃣ Watch 3 video clips daily\n"
                    "2️⃣ Repeat the phrases\n"
                    "3️⃣ Answer questions\n"
                    "4️⃣ Earn points & compete!"
                )
            else:
                welcome_msg = f"👋 Welcome back, {user.first_name}!"
            
            await update.message.reply_text(welcome_msg, parse_mode='Markdown')
            await self.check_user_status(update, context, db_user)
    
    async def check_user_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user):
        """Check and guide user through activation process"""
        
        is_member = await self.check_channel_membership(update, context)
        
        if not is_member:
            channels_text = "\n".join([f"• {ch}" for ch in settings.required_channels])
            
            keyboard = [[InlineKeyboardButton("✅ I Joined!", callback_data="check_membership")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"⚠️ *Join these channels first:*\n\n{channels_text}",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return
        
        if user.status == UserStatus.PENDING:
            if not user.phone_number:
                keyboard = [[InlineKeyboardButton("📱 Share Phone", callback_data="request_contact")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "📱 *Share your phone number:*",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            else:
                await self.show_activation_options(update, context, user)
        
        elif user.status == UserStatus.ACTIVE:
            await self.show_main_menu(update, context, user)
    
    async def check_channel_membership(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Check if user is member of required channels"""
        user_id = update.effective_user.id
        
        for channel in settings.required_channels:
            try:
                member = await context.bot.get_chat_member(channel, user_id)
                if member.status not in ['member', 'administrator', 'creator']:
                    return False
            except Exception as e:
                logger.error(f"Error checking membership for {channel}: {e}")
                return False
        
        return True
    
    async def show_activation_options(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user):
        """Show activation options"""
        keyboard = [
            [InlineKeyboardButton("💳 Manual Payment", callback_data="activate_manual_payment")],
            [InlineKeyboardButton("👥 Invite Friends", callback_data="activate_referral")],
            [InlineKeyboardButton("◀️ Back", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        msg = f"🔓 *Activate Your Account*\n\n"
        msg += f"Option 1: Pay ${settings.CHALLENGE_PRICE}\n"
        msg += f"Option 2: Invite {settings.REFERRAL_REQUIREMENT} friends\n\n"
        msg += f"Current Referrals: {user.referral_count}/{settings.REFERRAL_REQUIREMENT}"

        if update.callback_query:
            await update.callback_query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def handle_activation_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle activation buttons"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id

        async with self.get_db() as db:
            user = await user_service.get_user_by_telegram_id(db, user_id)

            if query.data == "activate_manual_payment":
                msg = f"💳 *Manual Payment*\n\n"
                msg += f"Amount: ${settings.CHALLENGE_PRICE}\n\n"
                msg += f"Card: {settings.BANK_CARD_NUMBER}\n"
                msg += f"Holder: {settings.BANK_CARD_HOLDER}\n\n"
                msg += "Send your payment receipt screenshot below:"
                
                keyboard = [[InlineKeyboardButton("◀️ Back", callback_data="back_to_main")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
                context.user_data['awaiting_payment_receipt'] = True

            elif query.data == "activate_referral":
                ref_link = f"https://t.me/{context.bot.username}?start={user.referral_code}"
                msg = f"👥 *Invite Friends*\n\n"
                msg += f"Share: `{ref_link}`\n\n"
                msg += f"Progress: {user.referral_count}/{settings.REFERRAL_REQUIREMENT}\n\n"
                msg += f"When {settings.REFERRAL_REQUIREMENT} people join,\n"
                msg += "your account will be activated!"
                
                keyboard = [[InlineKeyboardButton("◀️ Back", callback_data="back_to_main")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
        """Show main menu"""
        if not user:
            user_id = update.effective_user.id
            async with self.get_db() as db:
                user = await user_service.get_user_by_telegram_id(db, user_id)
        
        status_emoji = {
            UserStatus.ACTIVE: "✅",
            UserStatus.PENDING: "⏳",
            UserStatus.WAITLISTED: "📋"
        }
        
        status_text = status_emoji.get(user.status, "❓")
        
        menu_text = f"🏠 *Main Menu*\n\n"
        menu_text += f"Account: {status_text} {user.status.value.upper()}\n"
        menu_text += f"Points: {user.total_points}\n\n"
        menu_text += "Select an option:"
        
        keyboard = [
            [InlineKeyboardButton("🎬 Start Challenge", callback_data="start_challenge")],
            [InlineKeyboardButton("📊 Leaderboard", callback_data="show_leaderboard"), 
             InlineKeyboardButton("📈 My Stats", callback_data="show_my_stats")],
        ]
        
        # Show activation button if PENDING, otherwise show account button
        if user.status == UserStatus.PENDING:
            keyboard.append([InlineKeyboardButton("💳 Activate Account", callback_data="show_activation")])
        else:
            keyboard.append([InlineKeyboardButton("👤 Account", callback_data="show_account")])
        
        keyboard.append([InlineKeyboardButton("ℹ️ Help", callback_data="show_help")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(menu_text, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            await update.message.reply_text(menu_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def show_account_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show account menu"""
        user_id = update.effective_user.id
        
        async with self.get_db() as db:
            user = await user_service.get_user_by_telegram_id(db, user_id)
            
            msg = f"👤 *Account Information*\n\n"
            msg += f"Status: {user.status.value.upper()}\n"
            msg += f"Username: @{user.username or 'N/A'}\n"
            msg += f"Phone: {user.phone_number or 'Not set'}\n"
            msg += f"Points: {user.total_points}\n"
            msg += f"Referrals: {user.referral_count}/{settings.REFERRAL_REQUIREMENT}\n"
            
            if user.created_at:
                msg += f"Joined: {user.created_at.strftime('%Y-%m-%d')}"
            
            # Add status-specific message
            if user.status == UserStatus.ACTIVE:
                msg += "\n\n✅ *Account is Active!*\n"
                msg += f"Current referrals: {user.referral_count}\n"
                if user.referral_count < settings.REFERRAL_REQUIREMENT:
                    msg += f"Invite {settings.REFERRAL_REQUIREMENT - user.referral_count} more for bonus! 🎁"
                else:
                    msg += "You've unlocked all referral rewards! 🏆"
            
            # Build keyboard with referral button for active users
            keyboard = []
            if user.status == UserStatus.ACTIVE:
                keyboard.append([InlineKeyboardButton("👥 Invite Friends", callback_data="show_referral_link")])
            keyboard.append([InlineKeyboardButton("◀️ Back", callback_data="back_to_main")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    
    
    
    async def show_referral_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show referral link for active users"""
        user_id = update.effective_user.id
        
        async with self.get_db() as db:
            user = await user_service.get_user_by_telegram_id(db, user_id)
            
            ref_link = f"https://t.me/{context.bot.username}?start={user.referral_code}"
            
            msg = f"👥 *Invite Friends & Earn Bonuses!*\n\n"
            msg += f"Share your link: `{ref_link}`\n\n"
            msg += f"📊 Progress: {user.referral_count} friends invited\n\n"
            
            if user.referral_count >= settings.REFERRAL_REQUIREMENT:
                msg += "🏆 You've completed the referral requirement!\n"
                msg += "Keep inviting for extra rewards! 🎁"
            else:
                msg += f"Invite {settings.REFERRAL_REQUIREMENT - user.referral_count} more friends to unlock rewards! 🎁"
            
            keyboard = [[InlineKeyboardButton("◀️ Back", callback_data="show_account")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

    
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all callbacks"""
        query = update.callback_query
        await query.answer()

        if query.data == "back_to_main":
            user_id = query.from_user.id
            async with self.get_db() as db:
                user = await user_service.get_user_by_telegram_id(db, user_id)
                await self.show_main_menu(update, context, user)
            return
        
        if query.data == "start_challenge":
            await self.handle_start_challenge(update, context)
        elif query.data == "show_leaderboard":
            await self.show_leaderboard(update, context)
        elif query.data == "show_my_stats":
            await self.show_my_stats(update, context)
        elif query.data == "show_account":
            await self.show_account_menu(update, context)
        elif query.data == "show_referral_link":  # ADD THIS
            await self.show_referral_link(update, context)
        elif query.data == "show_activation":
            user_id = query.from_user.id
            async with self.get_db() as db:
                user = await user_service.get_user_by_telegram_id(db, user_id)
                await self.show_activation_options(update, context, user)
        elif query.data == "show_help":
            await self.show_help(update, context)
        elif query.data.startswith("activate_"):
            await self.handle_activation_callback(update, context)
        
    async def handle_start_challenge(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start challenge"""
        user_id = update.effective_user.id
        

        async with self.get_db() as db:
            user = await user_service.get_user_by_telegram_id(db, user_id)

            if not user or user.status != UserStatus.ACTIVE:

                msg = (
                    "⚠️ *You need to activate your account first.*\n\n"
                    "Go to the main menu and click *💳 Activate Account*"
                )

                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
                ])

                if update.callback_query:
                    await update.callback_query.edit_message_text(
                        text=msg,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        text=msg,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
                return

            
            challenge = await challenge_service.get_active_challenge(db)
            
            if not challenge:
                msg = "⏸️ No active challenge right now.\n\nCheck back later!"
                
                keyboard = [[InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                if update.callback_query:
                    await update.callback_query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
                else:
                    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
                return
            
            can_participate = await user_service.can_participate_in_challenge(db, user.id, challenge.id)
            
            if not can_participate:
                await user_service.add_to_waitlist(db, user.id, challenge.id)
                msg = "⏳ Current challenge is ongoing.\n\nAdded to waitlist!"
                
                if update.callback_query:
                    await update.callback_query.edit_message_text(msg, parse_mode='Markdown')
                else:
                    await update.message.reply_text(msg, parse_mode='Markdown')
                return
            
            attempt = await challenge_service.create_challenge_attempt(db, user.id, challenge.id)
            
            context.user_data['challenge_attempt_id'] = attempt.id
            context.user_data['current_video_index'] = 0
            
            msg = f"🎬 *{challenge.title}*\n\n"
            msg += "3 videos:\n"
            msg += "1️⃣ Watch\n"
            msg += "2️⃣ Repeat\n"
            msg += "3️⃣ Answer"
            
            if update.callback_query:
                await update.callback_query.edit_message_text(msg, parse_mode='Markdown')
            else:
                await update.message.reply_text(msg, parse_mode='Markdown')
            
            await self.send_next_video(update, context, db)
    
    async def send_next_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, db: AsyncSession):
        """Send next video"""
        challenge_attempt_id = context.user_data.get('challenge_attempt_id')
        video_index = context.user_data.get('current_video_index', 0)
        
        if not challenge_attempt_id:
            await update.message.reply_text("⚠️ Start challenge first")
            return
        
        attempt = await db.get(ChallengeAttempt, challenge_attempt_id)
        if not attempt:
            return
        
        videos = await challenge_service.get_challenge_videos(db, attempt.challenge_id)
        
        if video_index >= len(videos):
            await self.complete_challenge(update, context, db, attempt)
            return
        
        video = videos[video_index]
        video_attempt = await challenge_service.create_video_attempt(db, challenge_attempt_id, video.id)
        
        context.user_data['current_video_attempt_id'] = video_attempt.id
        context.user_data['current_video_id'] = video.id
        
        try:
            if video.file_id:
                await update.message.reply_video(video.file_id, caption=f"🎬 Video {video_index + 1}/3")
            else:
                with open(video.file_path, 'rb') as f:
                    msg = await update.message.reply_video(f, caption=f"🎬 Video {video_index + 1}/3")
                    video.file_id = msg.video.file_id
                    await db.commit()
            
            await update.message.reply_text(
                f"🎤 *Send voice message*\n\n"
                f"Attempts: {settings.MAX_VOICE_ATTEMPTS}",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error: {e}")
            await update.message.reply_text("❌ Error sending video")
    
    async def complete_challenge(self, update: Update, context: ContextTypes.DEFAULT_TYPE, db: AsyncSession, attempt):
        """Complete challenge"""
        await challenge_service.complete_challenge_attempt(db, attempt.id)
        
        user = await db.get(User, attempt.user_id)
        rank = await user_service.get_user_rank(db, user.id)
        
        keyboard = [[InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        msg = f"🎉 *Challenge Completed!*\n\n"
        msg += f"Points: {attempt.total_points}\n"
        msg += f"Rank: #{rank}"
        
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
        context.user_data.clear()
    
    async def show_leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show leaderboard"""
        async with self.get_db() as db:
            top_users = await user_service.get_leaderboard(db, limit=10)
            
            if not top_users:
                await update.message.reply_text("📊 No rankings yet")
                return
            
            msg = "🏆 *Top 10*\n\n"
            
            for i, user in enumerate(top_users, 1):
                emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}️⃣"
                username = user.username or f"User{user.telegram_id}"
                msg += f"{emoji} @{username} — {user.total_points}pts\n"
            
            keyboard = [[InlineKeyboardButton("◀️ Back", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def show_my_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user stats"""
        user_id = update.effective_user.id

        async with self.get_db() as db:
            user = await user_service.get_user_by_telegram_id(db, user_id)

            if not user:
                await update.message.reply_text("⚠️ User not found")
                return

            rank = await user_service.get_user_rank(db, user.id)

            msg = f"📈 *Your Stats*\n\n"
            msg += f"Points: {user.total_points}\n"
            msg += f"Rank: #{rank}\n"
            msg += f"Referrals: {user.referral_count}/{settings.REFERRAL_REQUIREMENT}\n"
            msg += f"Status: {user.status.value.upper()}"

            keyboard = [[InlineKeyboardButton("◀️ Back", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if update.callback_query:
                await update.callback_query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help"""
        msg = "ℹ️ *Help*\n\n"
        msg += "🎬 *How to Play:*\n"
        msg += "1. Watch video\n"
        msg += "2. Send voice\n"
        msg += "3. Answer question\n\n"
        msg += "🎯 *Points:*\n"
        msg += f"Voice: {settings.POINTS_VOICE_CORRECT}pts\n"
        msg += f"Question: {settings.POINTS_QUESTION_CORRECT}pts"
        
        keyboard = [[InlineKeyboardButton("◀️ Back", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def handle_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle phone number sharing"""
        contact = update.message.contact
        
        if contact.user_id != update.effective_user.id:
            await update.message.reply_text("⚠️ Please share YOUR phone number.")
            return
        
        async with self.get_db() as db:
            user = await user_service.get_user_by_telegram_id(db, contact.user_id)
            
            if user:
                await user_service.update_phone_number(db, user.id, contact.phone_number)
                await update.message.reply_text("✅ Phone number saved!")
                await self.show_activation_options(update, context, user)

    async def handle_payment_receipt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle payment receipt"""
        if not context.user_data.get('awaiting_payment_receipt'):
            return

        user_id = update.effective_user.id

        async with self.get_db() as db:
            user = await user_service.get_user_by_telegram_id(db, user_id)

            if not user:
                await update.message.reply_text("⚠️ User not found")
                return

            photo = update.message.photo[-1]
            file_id = photo.file_id

            payment = Payment(
                user_id=user.id,
                amount=settings.CHALLENGE_PRICE,
                payment_method="manual",
                payment_receipt_file_id=file_id,
                status=PaymentStatus.PENDING
            )
            db.add(payment)
            await db.commit()
            await db.refresh(payment)

            await update.message.reply_text(
                "✅ *Payment received!*\n\n"
                "Under review...",
                parse_mode='Markdown'
            )

            context.user_data['awaiting_payment_receipt'] = False

            for admin_id in settings.admin_ids:
                try:
                    keyboard_admin = [
                        [InlineKeyboardButton("✅ Approve", callback_data=f"approve_payment_{payment.id}"),
                         InlineKeyboardButton("❌ Reject", callback_data=f"reject_payment_{payment.id}")]
                    ]
                    reply_markup_admin = InlineKeyboardMarkup(keyboard_admin)

                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"💳 Payment from @{user.username or user.telegram_id}",
                        parse_mode='Markdown'
                    )

                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=file_id,
                        reply_markup=reply_markup_admin
                    )

                except Exception as e:
                    logger.error(f"Failed to notify admin: {e}")


# Global instance
bot_handlers = BotHandlers()