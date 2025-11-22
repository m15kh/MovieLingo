from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, func
import os

from app.database import AsyncSessionLocal
from app.database.models import (
    User, Payment, Challenge, Video, Question,
    ChallengeAttempt, VideoAttempt,
    UserStatus, PaymentStatus, ChallengeStatus
)
from app.services import user_service, ollama_service
from app.core.config import settings
from loguru import logger


class AdminHandlers:
    """Handlers for admin functions"""
    
    @staticmethod
    def is_admin(user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in settings.admin_ids
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin panel with glass buttons"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Admin access required.")
            return
        
        keyboard = [
            [InlineKeyboardButton("📹 Add Video", callback_data="admin_add_video")],
            [InlineKeyboardButton("🎬 Create Challenge", callback_data="admin_create_challenge")],
            [InlineKeyboardButton("📤 Send Challenge", callback_data="admin_send_challenge")],
            [InlineKeyboardButton("🔄 Resend Last", callback_data="admin_resend_last")],
            [InlineKeyboardButton("💳 Pending Payments", callback_data="admin_payments")],
            [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        panel_text = (
            "🔧 *Admin Panel*\n\n"
            "╔═══════════════════════════╗\n"
            "║ Manage Challenges & Users │\n"
            "╚═══════════════════════════╝\n\n"
            "Select an option below:"
        )
        
        await update.message.reply_text(panel_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def admin_panel_from_callback(self, query, context):
        """Show admin panel from callback (edit message)"""
        keyboard = [
            [InlineKeyboardButton("📹 Add Video", callback_data="admin_add_video")],
            [InlineKeyboardButton("🎬 Create Challenge", callback_data="admin_create_challenge")],
            [InlineKeyboardButton("📤 Send Challenge", callback_data="admin_send_challenge")],
            [InlineKeyboardButton("🔄 Resend Last", callback_data="admin_resend_last")],
            [InlineKeyboardButton("💳 Pending Payments", callback_data="admin_payments")],
            [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        panel_text = (
            "🔧 *Admin Panel*\n\n"
            "╔═══════════════════════════╗\n"
            "║ Manage Challenges & Users │\n"
            "╚═══════════════════════════╝\n\n"
            "Select an option below:"
        )
        
        await query.edit_message_text(panel_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin panel callbacks"""
        query = update.callback_query
        await query.answer()

        if not self.is_admin(query.from_user.id):
            await query.edit_message_text("⛔ Admin access required.")
            return

        if query.data == "admin_add_video":
            await self.prompt_add_video(query, context)
        elif query.data == "admin_create_challenge":
            await self.prompt_create_challenge(query, context)
        elif query.data == "admin_send_challenge":
            await self.send_challenge_to_users(query, context)
        elif query.data == "admin_resend_last":
            await self.resend_last_challenge(query, context)
        elif query.data == "admin_payments":
            await self.show_pending_payments(query, context)
        elif query.data == "admin_stats":
            await self.show_stats(query, context)
        elif query.data == "admin_back":
            await self.admin_panel_from_callback(query, context)
        elif query.data.startswith("review_payment_"):
            payment_id = int(query.data.split("_")[-1])
            await self.review_payment(query, context, payment_id)
        elif query.data.startswith("approve_payment_"):
            payment_id = int(query.data.split("_")[-1])
            await self.approve_payment(query, context, payment_id)
        elif query.data.startswith("reject_payment_"):
            payment_id = int(query.data.split("_")[-1])
            await self.reject_payment(query, context, payment_id)
    
    async def prompt_add_video(self, query, context):
        """Prompt admin to add video"""
        keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📹 *Add Video to Challenge*\n\n"
            "═══════════════════════════\n"
            "1. Use: `/add_video [challenge_id]`\n"
            "2. Send the video file\n"
            "3. Set the phrase\n"
            "4. Finalize the video\n"
            "═══════════════════════════\n\n"
            "Example: `/add_video 1`",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def handle_add_video_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add_video command"""
        if not self.is_admin(update.effective_user.id):
            return
        
        try:
            challenge_id = int(context.args[0])
            context.user_data['adding_video_to_challenge'] = challenge_id
            
            await update.message.reply_text(
                f"✅ *Ready to add video to challenge {challenge_id}*\n\n"
                f"Now send me the video file."
            , parse_mode='Markdown')
        except (IndexError, ValueError):
            await update.message.reply_text(
                "⚠️ *Usage:* `/add_video [challenge_id]`\n\n"
                "Example: `/add_video 1`",
                parse_mode='Markdown'
            )
    
    async def handle_video_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle video file upload from admin"""
        if not self.is_admin(update.effective_user.id):
            return
        
        challenge_id = context.user_data.get('adding_video_to_challenge')
        if not challenge_id:
            await update.message.reply_text(
                "⚠️ Please use `/add_video [challenge_id]` first"
            )
            return
        
        try:
            video_file = await update.message.video.get_file()
            
            filename = f"video_{challenge_id}_{datetime.now().timestamp()}.mp4"
            filepath = os.path.join(settings.VIDEO_STORAGE_PATH, filename)
            
            await video_file.download_to_drive(filepath)
            
            context.user_data['pending_video'] = {
                'challenge_id': challenge_id,
                'file_path': filepath,
                'file_id': update.message.video.file_id
            }
            
            await update.message.reply_text(
                "✅ *Video saved!*\n\n"
                "Now send me the phrase to learn.\n"
                "Use: `/set_phrase Your phrase here`"
            , parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error handling video upload: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Error sending video"
            )    
    async def handle_set_phrase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /set_phrase command"""
        if not self.is_admin(update.effective_user.id):
            return
        
        pending_video = context.user_data.get('pending_video')
        if not pending_video:
            await update.message.reply_text("⚠️ Please upload a video first.")
            return
        
        phrase = ' '.join(context.args)
        if not phrase:
            await update.message.reply_text(
                "⚠️ *Usage:* `/set_phrase Your phrase here`"
            , parse_mode='Markdown')
            return
        
        pending_video['phrase'] = phrase
        
        await update.message.reply_text(
            f"✅ *Phrase set:* `{phrase}`\n\n"
            f"Optional: `/set_subtitle [text]`\n"
            f"Then: `/finalize_video`"
        , parse_mode='Markdown')
    
    async def handle_finalize_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Finalize video addition"""
        if not self.is_admin(update.effective_user.id):
            return
        
        pending_video = context.user_data.get('pending_video')
        if not pending_video or 'phrase' not in pending_video:
            await update.message.reply_text("⚠️ Please upload video and set phrase first.")
            return
        
        async with AsyncSessionLocal() as db:
            challenge = await db.get(Challenge, pending_video['challenge_id'])
            if not challenge:
                await update.message.reply_text("❌ Challenge not found.")
                return
            
            from sqlalchemy import select, func
            result = await db.execute(
                select(func.count(Video.id))
                .where(Video.challenge_id == challenge.id)
            )
            video_count = result.scalar_one()
            
            video = Video(
                challenge_id=challenge.id,
                file_path=pending_video['file_path'],
                file_id=pending_video.get('file_id'),
                phrase=pending_video['phrase'],
                subtitle=pending_video.get('subtitle'),
                movie_name=pending_video.get('movie_name'),
                order=video_count + 1
            )
            db.add(video)
            await db.commit()
            await db.refresh(video)
            
            await update.message.reply_text("🤖 *Generating question with AI...*", parse_mode='Markdown')
            
            question_data = await ollama_service.generate_question(
                video.phrase,
                video.movie_name
            )
            
            if question_data:
                question = Question(
                    video_id=video.id,
                    question_text=question_data['question'],
                    option_a=question_data['options']['A'],
                    option_b=question_data['options']['B'],
                    option_c=question_data['options']['C'],
                    option_d=question_data['options']['D'],
                    correct_option=question_data['correct'],
                    example_sentence=question_data['example']
                )
                db.add(question)
                await db.commit()
            
            keyboard = [[InlineKeyboardButton("🔄 Add Another", callback_data="admin_add_video")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ *Video added successfully!*\n\n"
                f"Challenge: {challenge.title}\n"
                f"Video #: {video.order}\n"
                f"Phrase: `{video.phrase}`\n"
                f"Question: {'✅ Generated' if question_data else '❌ Failed'}",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
            context.user_data.pop('pending_video', None)
            context.user_data.pop('adding_video_to_challenge', None)
    
    async def prompt_create_challenge(self, query, context):
        """Prompt admin to create challenge"""
        keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🎬 *Create Challenge*\n\n"
            "═══════════════════════════\n"
            "Use: `/create_challenge [title]`\n\n"
            "Example:\n"
            "`/create_challenge Daily Challenge Dec 1`\n"
            "═══════════════════════════",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def handle_create_challenge(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /create_challenge command"""
        if not self.is_admin(update.effective_user.id):
            return
        
        title = ' '.join(context.args)
        if not title:
            await update.message.reply_text(
                "⚠️ *Usage:* `/create_challenge [title]`"
            , parse_mode='Markdown')
            return
        
        async with AsyncSessionLocal() as db:
            start_date = datetime.now() + timedelta(days=1)
            start_date = start_date.replace(hour=settings.CHALLENGE_START_HOUR, minute=0, second=0)
            
            challenge = Challenge(
                title=title,
                start_date=start_date,
                status=ChallengeStatus.SCHEDULED
            )
            db.add(challenge)
            await db.commit()
            await db.refresh(challenge)
            
            keyboard = [[InlineKeyboardButton(f"➕ Add Videos", callback_data="admin_add_video")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ *Challenge created!*\n\n"
                f"ID: {challenge.id}\n"
                f"Title: {title}\n"
                f"Start: {start_date.strftime('%Y-%m-%d %H:%M')}\n\n"
                f"Next: Add 3 videos using `/add_video {challenge.id}`",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    
    async def send_challenge_to_users(self, query, context):
        """Send active challenge to all active users"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Challenge)
                .where(Challenge.status == ChallengeStatus.SCHEDULED)
                .order_by(Challenge.start_date)
                .limit(1)
            )
            challenge = result.scalar_one_or_none()
            
            if not challenge:
                keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="admin_back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    "⚠️ *No scheduled challenges.*",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                return
            
            await db.execute(
                update(Challenge)
                .where(Challenge.status == ChallengeStatus.ACTIVE)
                .values(status=ChallengeStatus.COMPLETED)
            )
            
            challenge.status = ChallengeStatus.ACTIVE
            await db.commit()
            
            logger.info(f"Challenge {challenge.id} activated")
            
            result = await db.execute(
                select(User).where(User.status == UserStatus.ACTIVE)
            )
            users = result.scalars().all()
            
            sent = 0
            for user in users:
                try:
                    keyboard_user = [[InlineKeyboardButton("🎬 Start Challenge", callback_data="start_challenge")]]
                    reply_markup_user = InlineKeyboardMarkup(keyboard_user)
                    
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=(
                            f"🎬 *New Challenge Available!*\n\n"
                            f"_{challenge.title}_\n\n"
                            f"Tap the button below to begin!"
                        ),
                        parse_mode='Markdown',
                        reply_markup=reply_markup_user
                    )
                    sent += 1
                except Exception as e:
                    logger.error(f"Failed to notify user {user.id}: {e}")
            
            keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"✅ *Challenge Activated!*\n\n"
                f"Challenge: {challenge.title}\n"
                f"Users notified: {sent}\n\n"
                f"Status: LIVE",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    
    async def resend_last_challenge(self, query, context):
        """Re-send the most recent challenge"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Challenge)
                .order_by(Challenge.id.desc())
                .limit(1)
            )
            challenge = result.scalar_one_or_none()
            
            if not challenge:
                keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="admin_back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    "⚠️ *No challenges found.*",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                return
            
            result = await db.execute(
                select(func.count(Video.id))
                .where(Video.challenge_id == challenge.id)
            )
            video_count = result.scalar()
            
            if video_count < 3:
                keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="admin_back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"⚠️ *Challenge has only {video_count}/3 videos.*",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                return
            
            await db.execute(
                update(Challenge)
                .where(Challenge.id != challenge.id)
                .values(status=ChallengeStatus.COMPLETED)
            )
            
            await db.execute(delete(VideoAttempt))
            await db.execute(
                delete(ChallengeAttempt)
                .where(ChallengeAttempt.challenge_id == challenge.id)
            )
            
            challenge.status = ChallengeStatus.ACTIVE
            await db.commit()
            
            logger.info(f"Re-sending challenge {challenge.id}: {challenge.title}")
            
            result = await db.execute(
                select(User).where(User.status == UserStatus.ACTIVE)
            )
            users = result.scalars().all()
            
            sent = 0
            for user in users:
                try:
                    keyboard_user = [[InlineKeyboardButton("🎬 Start Challenge", callback_data="start_challenge")]]
                    reply_markup_user = InlineKeyboardMarkup(keyboard_user)
                    
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=(
                            f"🔄 *Challenge Resent!*\n\n"
                            f"_{challenge.title}_\n\n"
                            f"Tap to start!"
                        ),
                        parse_mode='Markdown',
                        reply_markup=reply_markup_user
                    )
                    sent += 1
                except Exception as e:
                    logger.error(f"Failed to notify user {user.id}: {e}")
            
            keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"🔄 *Challenge Re-sent!*\n\n"
                f"Title: {challenge.title}\n"
                f"Videos: {video_count}/3\n"
                f"Users: {sent}",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    
    async def show_pending_payments(self, query, context):
        """Show pending payment approvals with glass buttons"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Payment)
                .where(Payment.status == PaymentStatus.PENDING)
                .order_by(Payment.created_at.desc())
            )
            payments = result.scalars().all()

            if not payments:
                keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="admin_back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    "✅ *No pending payments!*",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                return

            text = "💳 *Pending Payments*\n\n"
            text += "╔═══════════════════════════╗\n"
            
            keyboard = []

            for payment in payments[:10]:
                user = await db.get(User, payment.user_id)
                payment_type = "📸" if payment.payment_method == "manual" else "💳"

                text += f"║ {payment_type} @{user.username or user.telegram_id}\n"
                text += f"║ ${payment.amount} • ID: {payment.id}\n"
                text += f"╠═══════════════════════════╣\n"

                if payment.payment_method == "manual" and payment.payment_receipt_file_id:
                    keyboard.append([
                        InlineKeyboardButton(
                            f"👁️ Review {user.username or user.telegram_id}",
                            callback_data=f"review_payment_{payment.id}"
                        )
                    ])

            text += "╚═══════════════════════════╝"
            keyboard.append([InlineKeyboardButton("🏠 Back to Panel", callback_data="admin_back")])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def review_payment(self, query, context, payment_id: int):
        """Show payment receipt for review"""
        async with AsyncSessionLocal() as db:
            payment = await db.get(Payment, payment_id)
            if not payment:
                await query.answer("Payment not found.")
                return

            user = await db.get(User, payment.user_id)

            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_payment_{payment.id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_payment_{payment.id}")
                ],
                [InlineKeyboardButton("🏠 Back", callback_data="admin_payments")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            try:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=payment.payment_receipt_file_id,
                    caption=(
                        f"💳 *Payment Receipt*\n\n"
                        f"User: @{user.username or user.telegram_id}\n"
                        f"Amount: ${payment.amount}\n"
                        f"ID: {payment.id}\n"
                        f"Date: {payment.created_at.strftime('%Y-%m-%d %H:%M')}"
                    ),
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                await query.answer("Receipt displayed")
            except Exception as e:
                logger.error(f"Failed to show receipt: {e}")
                await query.answer("❌ Failed to load receipt")

    async def approve_payment(self, query, context, payment_id: int):
        """Approve a payment"""
        async with AsyncSessionLocal() as db:
            payment = await db.get(Payment, payment_id)
            if not payment:
                await query.answer("Payment not found.")
                return

            payment.status = PaymentStatus.COMPLETED
            payment.approved_at = datetime.utcnow()
            payment.approved_by = query.from_user.id

            await user_service.activate_user(db, payment.user_id)
            await db.commit()

            user = await db.get(User, payment.user_id)
            try:
                keyboard = [[InlineKeyboardButton("🎬 Start Challenge", callback_data="start_challenge")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text=(
                        "✅ *Your payment has been approved!*\n\n"
                        "Your account is now ACTIVE! 🎉\n\n"
                        "You can now participate in challenges!"
                    ),
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Failed to notify user: {e}")

            await query.answer("✅ Payment approved!")
            
            keyboard = [[InlineKeyboardButton("🏠 Back to Payments", callback_data="admin_payments")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_caption(
                    caption=f"✅ *Approved for:* @{user.username or user.telegram_id}",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except:
                pass

    async def reject_payment(self, query, context, payment_id: int):
        """Reject a payment"""
        async with AsyncSessionLocal() as db:
            payment = await db.get(Payment, payment_id)
            if not payment:
                await query.answer("Payment not found.")
                return

            payment.status = PaymentStatus.FAILED
            payment.rejection_reason = "Payment receipt was not valid"

            await db.commit()

            user = await db.get(User, payment.user_id)
            try:
                keyboard = [[InlineKeyboardButton("🔄 Try Again", callback_data="show_account")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text=(
                        "❌ *Your payment was not approved.*\n\n"
                        f"Reason: {payment.rejection_reason}\n\n"
                        "Please try again or use the referral option."
                    ),
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Failed to notify user: {e}")

            await query.answer("❌ Payment rejected")
            
            keyboard = [[InlineKeyboardButton("🏠 Back to Payments", callback_data="admin_payments")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_caption(
                    caption=f"❌ *Rejected for:* @{user.username or user.telegram_id}",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except:
                pass
    
    async def show_stats(self, query, context):
        """Show system statistics"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User.status, func.count(User.id))
                .group_by(User.status)
            )
            user_counts = dict(result.all())
            
            result = await db.execute(select(func.count(Challenge.id)))
            challenge_count = result.scalar_one()
            
            result = await db.execute(select(func.count(Video.id)))
            video_count = result.scalar_one()
            
            stats_text = (
                "📊 *System Statistics*\n\n"
                "╔═══════════════════════════╗\n"
                f"║ ACTIVE:      {user_counts.get(UserStatus.ACTIVE, 0):18}│\n"
                f"║ PENDING:     {user_counts.get(UserStatus.PENDING, 0):18}│\n"
                f"║ WAITLISTED:  {user_counts.get(UserStatus.WAITLISTED, 0):18}│\n"
                "╠════════ ══════════════════╣\n"
                f"║ CHALLENGES:  {challenge_count:18}│\n"
                f"║ VIDEOS:      {video_count:18}│\n"
                "╚═══════════════════════════╝"
            )
            
            keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="admin_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(stats_text, parse_mode='Markdown', reply_markup=reply_markup)


# Global instance
admin_handlers = AdminHandlers()