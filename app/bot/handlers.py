from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import os

from app.database import AsyncSessionLocal
from app.database.models import UserStatus
from app.services import user_service, payment_service, challenge_service
from app.core.config import settings
from loguru import logger


class BotHandlers:
    """Main bot handlers for user interactions"""
    
    @staticmethod
    async def get_db() -> AsyncSession:
        """Get database session"""
        return AsyncSessionLocal()
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        # Extract referral code from /start parameter
        referral_code = None
        if context.args and len(context.args) > 0:
            referral_code = context.args[0]
            logger.info(f"User {user.id} started with referral code: {referral_code}")
        
        async with await self.get_db() as db:
            # Check if user exists, create if not
            db_user = await user_service.get_user_by_telegram_id(db, user.id)
            
            if not db_user:
                db_user = await user_service.create_user(
                    db, user.id, user.username
                )
                
                # Process referral if provided
                if referral_code:
                    # Find the referrer
                    referrer = await user_service.get_user_by_referral_code(db, referral_code)
                    
                    if referrer and referrer.id != db_user.id:
                        # Link the referral
                        await user_service.add_referral(db, referrer.id, db_user.id)
                        
                        # Check if referrer now has enough referrals to activate
                        if referrer.referral_count + 1 >= settings.REFERRAL_REQUIREMENT:
                            await user_service.activate_user(db, referrer.id)
                            
                            # Notify referrer
                            try:
                                await context.bot.send_message(
                                    chat_id=referrer.telegram_id,
                                    text=(
                                        "🎉 Congratulations!\n\n"
                                        f"You've invited {settings.REFERRAL_REQUIREMENT} friends!\n"
                                        "Your account is now ACTIVATED! 🚀\n\n"
                                        "You can now participate in challenges!"
                                    )
                                )
                            except Exception as e:
                                logger.error(f"Failed to notify referrer: {e}")
                        else:
                            # Notify referrer of progress
                            try:
                                await context.bot.send_message(
                                    chat_id=referrer.telegram_id,
                                    text=(
                                        f"👥 New referral!\n\n"
                                        f"@{user.username or 'Someone'} joined using your link!\n"
                                        f"Progress: {referrer.referral_count + 1}/{settings.REFERRAL_REQUIREMENT}"
                                    )
                                )
                            except Exception as e:
                                logger.error(f"Failed to notify referrer: {e}")
                
                welcome_msg = (
                    f"👋 Welcome {user.first_name}!\n\n"
                    "🎬 Learn English with movie clips!\n\n"
                    "How it works:\n"
                    "1️⃣ Watch 3 video clips daily\n"
                    "2️⃣ Repeat the phrases you hear\n"
                    "3️⃣ Answer questions\n"
                    "4️⃣ Earn points & compete!\n\n"
                    "Let's get started! 🚀"
                )
                
                if referral_code and referrer:
                    welcome_msg += f"\n\n✅ Referred by: @{referrer.username or 'friend'}"
            else:
                welcome_msg = f"Welcome back, {user.first_name}! 👋"
            
            await update.message.reply_text(welcome_msg)
            
            # Check membership and activation status
            await self.check_user_status(update, context, db_user)
    
    async def check_user_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user):
        """Check and guide user through activation process"""
        
        # Check channel membership
        is_member = await self.check_channel_membership(update, context)
        
        if not is_member:
            channels_text = "\n".join([f"• {ch}" for ch in settings.required_channels])
            await update.message.reply_text(
                f"⚠️ You must join these channels first:\n\n{channels_text}\n\n"
                "After joining, use /start again."
            )
            return
        
        # Check activation status
        if user.status == UserStatus.PENDING:
            # Need phone number
            if not user.phone_number:
                keyboard = ReplyKeyboardMarkup(
                    [[KeyboardButton("📱 Share Phone Number", request_contact=True)]],
                    one_time_keyboard=True,
                    resize_keyboard=True
                )
                await update.message.reply_text(
                    "📱 Please share your phone number to continue:",
                    reply_markup=keyboard
                )
            else:
                # Need payment or referrals
                await self.show_activation_options(update, context, user)
        
        elif user.status == UserStatus.WAITLISTED:
            await update.message.reply_text(
                "⏳ You're on the waitlist!\n\n"
                "The current challenge is ongoing. You'll be notified when the next challenge starts."
            )
        
        elif user.status == UserStatus.ACTIVE:
            await self.show_main_menu(update, context)
    
    async def check_channel_membership(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
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
    
    async def show_activation_options(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user
    ):
        """Show activation options: payment or referrals"""
        keyboard = [
            [InlineKeyboardButton("💳 Pay with Card Transfer", callback_data="activate_manual_payment")],
            [InlineKeyboardButton("🌐 Pay with Stripe", callback_data="activate_stripe_payment")],
            [InlineKeyboardButton("👥 Invite 5 Friends", callback_data="activate_referral")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "🔓 Activate your account:\n\n"
            f"Option 1: Pay ${settings.CHALLENGE_PRICE}\n"
            f"Option 2: Invite {settings.REFERRAL_REQUIREMENT} friends\n\n"
            f"Your referral link:\n`https://t.me/{context.bot.username}?start={user.referral_code}`\n\n"
            f"Referrals so far: {user.referral_count}/{settings.REFERRAL_REQUIREMENT}",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def handle_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle phone number sharing"""
        contact = update.message.contact
        
        if contact.user_id != update.effective_user.id:
            await update.message.reply_text("⚠️ Please share YOUR phone number.")
            return
        
        async with await self.get_db() as db:
            user = await user_service.get_user_by_telegram_id(db, contact.user_id)
            
            if user:
                await user_service.update_phone_number(
                    db, user.id, contact.phone_number
                )
                await update.message.reply_text(
                    "✅ Phone number saved!\n\n"
                    "Now, let's activate your account."
                )
                await self.show_activation_options(update, context, user)
    
    async def handle_activation_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle activation button callbacks"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id

        async with await self.get_db() as db:
            user = await user_service.get_user_by_telegram_id(db, user_id)

            if query.data == "activate_manual_payment":
                # Show bank card details for manual payment
                await query.edit_message_text(
                    f"💳 Manual Payment Instructions\n\n"
                    f"Amount: ${settings.CHALLENGE_PRICE}\n\n"
                    f"🏦 Bank Details:\n"
                    f"Card Number: `{settings.BANK_CARD_NUMBER}`\n"
                    f"Card Holder: {settings.BANK_CARD_HOLDER}\n"
                    f"Bank: {settings.BANK_NAME}\n\n"
                    f"📸 After payment:\n"
                    f"1. Take a screenshot of your payment receipt\n"
                    f"2. Send the screenshot to this bot\n"
                    f"3. Admin will review and approve your payment\n\n"
                    f"⏳ Waiting for your payment receipt...",
                    parse_mode='Markdown'
                )

                # Set user state to expect payment receipt
                context.user_data['awaiting_payment_receipt'] = True
                context.user_data['payment_user_id'] = user.id

            elif query.data == "activate_stripe_payment":
                # Generate Stripe payment link
                payment_link = await payment_service.create_payment_link(user.id)

                if payment_link:
                    keyboard = [[InlineKeyboardButton("💳 Pay Now", url=payment_link)]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"💳 Payment Link Generated!\n\n"
                        f"Amount: ${settings.CHALLENGE_PRICE}\n\n"
                        "Click the button below to complete payment.\n"
                        "After payment, admin will approve your access.",
                        reply_markup=reply_markup
                    )
                else:
                    await query.edit_message_text("❌ Error creating payment link. Please try again later.")

            elif query.data == "activate_referral":
                ref_link = f"https://t.me/{context.bot.username}?start={user.referral_code}"

                await query.edit_message_text(
                    "👥 Invite Friends!\n\n"
                    f"Share your referral link:\n`{ref_link}`\n\n"
                    f"Progress: {user.referral_count}/{settings.REFERRAL_REQUIREMENT}\n\n"
                    "Send this link to your friends. When 5 people join using your link, "
                    "your account will be automatically activated!",
                    parse_mode='Markdown'
                )
    
    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main menu for active users"""
        keyboard = [
            [KeyboardButton("🎬 Start Challenge")],
            [KeyboardButton("📊 Leaderboard"), KeyboardButton("📈 My Stats")],
            [KeyboardButton("ℹ️ Help")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "🏠 Main Menu\n\nWhat would you like to do?",
            reply_markup=reply_markup
        )
    
    async def handle_start_challenge(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle challenge start request"""
        user_id = update.effective_user.id
        
        async with await self.get_db() as db:
            # Get user
            user = await user_service.get_user_by_telegram_id(db, user_id)
            
            if not user or user.status != UserStatus.ACTIVE:
                await update.message.reply_text("⚠️ You need to activate your account first.")
                return
            
            # Get active challenge
            challenge = await challenge_service.get_active_challenge(db)
            
            if not challenge:
                await update.message.reply_text("⏸️ No active challenge right now. Check back later!")
                return
            
            # Check if user can participate
            can_participate = await user_service.can_participate_in_challenge(
                db, user.id, challenge.id
            )
            
            if not can_participate:
                # Add to waitlist
                await user_service.add_to_waitlist(db, user.id, challenge.id)
                await update.message.reply_text(
                    "⏳ The current challenge is ongoing.\n\n"
                    "You've been added to the waitlist and will be notified when the next challenge starts!"
                )
                return
            
            # Create challenge attempt
            attempt = await challenge_service.create_challenge_attempt(
                db, user.id, challenge.id
            )
            
            # Store challenge attempt ID in context
            context.user_data['challenge_attempt_id'] = attempt.id
            context.user_data['current_video_index'] = 0
            
            await update.message.reply_text(
                f"🎬 {challenge.title}\n\n"
                "You'll watch 3 video clips. For each video:\n\n"
                "1️⃣ Watch without subtitles\n"
                "2️⃣ Send voice message repeating the phrase\n"
                "3️⃣ Answer a question\n\n"
                "Let's start! 🚀"
            )
            
            # Send first video
            await self.send_next_video(update, context, db)
    
    async def send_next_video(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE,
        db: AsyncSession
    ):
        """Send next video in the challenge"""
        challenge_attempt_id = context.user_data.get('challenge_attempt_id')
        video_index = context.user_data.get('current_video_index', 0)
        
        if not challenge_attempt_id:
            await update.message.reply_text("⚠️ Please start the challenge first.")
            return
        
        # Get challenge attempt
        attempt = await db.get(ChallengeAttempt, challenge_attempt_id)
        if not attempt:
            return
        
        # Get videos
        videos = await challenge_service.get_challenge_videos(db, attempt.challenge_id)
        
        if video_index >= len(videos):
            # Challenge completed
            await self.complete_challenge(update, context, db, attempt)
            return
        
        video = videos[video_index]
        
        # Create video attempt
        video_attempt = await challenge_service.create_video_attempt(
            db, challenge_attempt_id, video.id
        )
        
        context.user_data['current_video_attempt_id'] = video_attempt.id
        context.user_data['current_video_id'] = video.id
        
        # Send video
        try:
            if video.file_id:
                await update.message.reply_video(
                    video.file_id,
                    caption=f"🎬 Video {video_index + 1}/3\n\nWatch and repeat the phrase!"
                )
            else:
                with open(video.file_path, 'rb') as video_file:
                    message = await update.message.reply_video(
                        video_file,
                        caption=f"🎬 Video {video_index + 1}/3\n\nWatch and repeat the phrase!"
                    )
                    # Save file_id for future use
                    video.file_id = message.video.file_id
                    await db.commit()
            
            await update.message.reply_text(
                "🎤 Now send me a voice message repeating the phrase you heard!\n\n"
                f"You have {settings.MAX_VOICE_ATTEMPTS} attempts."
            )
            
        except Exception as e:
            logger.error(f"Error sending video: {e}")
            await update.message.reply_text("❌ Error sending video. Please try again.")
    
    async def complete_challenge(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        db: AsyncSession,
        attempt
    ):
        """Complete the challenge and show results"""
        await challenge_service.complete_challenge_attempt(db, attempt.id)
        
        # Get user
        user = await db.get(User, attempt.user_id)
        
        # Get rank
        rank = await user_service.get_user_rank(db, user.id)
        
        await update.message.reply_text(
            "🎉 Challenge Completed!\n\n"
            f"Total Points: {attempt.total_points}\n"
            f"Your Rank: #{rank}\n\n"
            "Great job! See you tomorrow for the next challenge! 🚀"
        )
        
        # Clear context
        context.user_data.clear()
    
    async def show_leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show top users leaderboard"""
        async with await self.get_db() as db:
            top_users = await user_service.get_leaderboard(db, limit=10)
            
            if not top_users:
                await update.message.reply_text("📊 No rankings yet!")
                return
            
            leaderboard_text = "🏆 Top 10 Leaderboard\n\n"
            
            for i, user in enumerate(top_users, 1):
                emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
                username = user.username or f"User{user.telegram_id}"
                leaderboard_text += f"{emoji} {i}. @{username} - {user.total_points} pts\n"
            
            await update.message.reply_text(leaderboard_text)
    
    async def show_my_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's statistics"""
        user_id = update.effective_user.id

        async with await self.get_db() as db:
            user = await user_service.get_user_by_telegram_id(db, user_id)

            if not user:
                await update.message.reply_text("⚠️ User not found.")
                return

            rank = await user_service.get_user_rank(db, user.id)

            stats_text = (
                "📈 Your Statistics\n\n"
                f"Total Points: {user.total_points}\n"
                f"Rank: #{rank}\n"
                f"Referrals: {user.referral_count}\n"
                f"Status: {user.status.value.upper()}\n"
            )

            await update.message.reply_text(stats_text)

    async def handle_payment_receipt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle payment receipt photo from user"""
        # Check if user is expecting to send payment receipt
        if not context.user_data.get('awaiting_payment_receipt'):
            return

        user_id = update.effective_user.id

        async with await self.get_db() as db:
            from app.database.models import Payment, PaymentStatus

            user = await user_service.get_user_by_telegram_id(db, user_id)

            if not user:
                await update.message.reply_text("⚠️ User not found.")
                return

            # Get the photo file_id (largest size)
            photo = update.message.photo[-1]
            file_id = photo.file_id

            # Create payment record
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

            # Notify user
            await update.message.reply_text(
                "✅ Payment receipt received!\n\n"
                "Your payment is now under review by our admin team.\n"
                "You'll be notified once it's approved.\n\n"
                "⏳ This usually takes a few minutes to 24 hours."
            )

            # Clear the awaiting state
            context.user_data['awaiting_payment_receipt'] = False
            context.user_data.pop('payment_user_id', None)

            # Notify admin
            for admin_id in settings.admin_ids:
                try:
                    keyboard = [
                        [
                            InlineKeyboardButton("✅ Approve", callback_data=f"approve_payment_{payment.id}"),
                            InlineKeyboardButton("❌ Reject", callback_data=f"reject_payment_{payment.id}")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=(
                            f"💳 New Payment Receipt!\n\n"
                            f"User: @{user.username or user.telegram_id}\n"
                            f"User ID: {user.telegram_id}\n"
                            f"Amount: ${settings.CHALLENGE_PRICE}\n"
                            f"Payment ID: {payment.id}\n\n"
                            f"Please review the receipt below:"
                        )
                    )

                    # Send the receipt photo to admin
                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=file_id,
                        reply_markup=reply_markup
                    )

                except Exception as e:
                    logger.error(f"Failed to notify admin {admin_id}: {e}")


# Global instance
bot_handlers = BotHandlers()