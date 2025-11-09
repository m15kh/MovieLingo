from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import os

from app.database import AsyncSessionLocal
from app.database.models import (
    User, Payment, Challenge, Video, Question,
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
        """Show admin panel"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Admin access required.")
            return
        
        keyboard = [
            [InlineKeyboardButton("📹 Add Video", callback_data="admin_add_video")],
            [InlineKeyboardButton("🎬 Create Challenge", callback_data="admin_create_challenge")],
            [InlineKeyboardButton("📤 Send Challenge", callback_data="admin_send_challenge")],
            [InlineKeyboardButton("💳 Pending Payments", callback_data="admin_payments")],
            [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔧 Admin Panel\n\nWhat would you like to do?",
            reply_markup=reply_markup
        )
    
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
        elif query.data == "admin_payments":
            await self.show_pending_payments(query, context)
        elif query.data == "admin_stats":
            await self.show_stats(query, context)
        elif query.data.startswith("approve_payment_"):
            payment_id = int(query.data.split("_")[-1])
            await self.approve_payment(query, context, payment_id)
    
    async def prompt_add_video(self, query, context):
        """Prompt admin to add video"""
        await query.edit_message_text(
            "📹 Add Video\n\n"
            "Send me:\n"
            "1. Video file\n"
            "2. Phrase (what to learn)\n"
            "3. Subtitle (optional)\n"
            "4. Movie name (optional)\n\n"
            "Format: /add_video [challenge_id]\n"
            "Then send the video file.\n\n"
            "Example: /add_video 1"
        )
    
    async def handle_add_video_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add_video command"""
        if not self.is_admin(update.effective_user.id):
            return
        
        try:
            challenge_id = int(context.args[0])
            context.user_data['adding_video_to_challenge'] = challenge_id
            
            await update.message.reply_text(
                f"✅ Ready to add video to challenge {challenge_id}\n\n"
                "Now send me the video file."
            )
        except (IndexError, ValueError):
            await update.message.reply_text(
                "⚠️ Usage: /add_video [challenge_id]\n"
                "Example: /add_video 1"
            )
    
    async def handle_video_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle video file upload from admin"""
        if not self.is_admin(update.effective_user.id):
            return
        
        challenge_id = context.user_data.get('adding_video_to_challenge')
        if not challenge_id:
            await update.message.reply_text(
                "⚠️ Please use /add_video [challenge_id] first"
            )
            return
        
        try:
            # Download video
            video_file = await update.message.video.get_file()
            
            # Create filename
            filename = f"video_{challenge_id}_{datetime.now().timestamp()}.mp4"
            filepath = os.path.join(settings.VIDEO_STORAGE_PATH, filename)
            
            await video_file.download_to_drive(filepath)
            
            # Store video info
            context.user_data['pending_video'] = {
                'challenge_id': challenge_id,
                'file_path': filepath,
                'file_id': update.message.video.file_id
            }
            
            await update.message.reply_text(
                "✅ Video saved!\n\n"
                "Now send me the phrase to learn from this video.\n"
                "Format: /set_phrase Your phrase here"
            )
            
        except Exception as e:
            logger.error(f"Error handling video upload: {e}")
            await update.message.reply_text("❌ Error saving video.")
    
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
                "⚠️ Usage: /set_phrase Your phrase here"
            )
            return
        
        pending_video['phrase'] = phrase
        
        await update.message.reply_text(
            f"✅ Phrase set: \"{phrase}\"\n\n"
            "Optional: Send subtitle with /set_subtitle [text]\n"
            "Or finalize with /finalize_video"
        )
    
    async def handle_finalize_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Finalize video addition"""
        if not self.is_admin(update.effective_user.id):
            return
        
        pending_video = context.user_data.get('pending_video')
        if not pending_video or 'phrase' not in pending_video:
            await update.message.reply_text("⚠️ Please upload video and set phrase first.")
            return
        
        async with AsyncSessionLocal() as db:
            # Get challenge
            challenge = await db.get(Challenge, pending_video['challenge_id'])
            if not challenge:
                await update.message.reply_text("❌ Challenge not found.")
                return
            
            # Count existing videos
            from sqlalchemy import select, func
            result = await db.execute(
                select(func.count(Video.id))
                .where(Video.challenge_id == challenge.id)
            )
            video_count = result.scalar_one()
            
            # Create video
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
            
            # Generate question using AI
            await update.message.reply_text("🤖 Generating question with AI...")
            
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
            
            await update.message.reply_text(
                f"✅ Video added successfully!\n\n"
                f"Challenge: {challenge.title}\n"
                f"Video #{video.order}\n"
                f"Phrase: {video.phrase}\n"
                f"Question: {'Generated' if question_data else 'Failed to generate'}"
            )
            
            # Clear context
            context.user_data.pop('pending_video', None)
            context.user_data.pop('adding_video_to_challenge', None)
    
    async def prompt_create_challenge(self, query, context):
        """Prompt admin to create challenge"""
        await query.edit_message_text(
            "🎬 Create Challenge\n\n"
            "Use: /create_challenge [title]\n\n"
            "Example: /create_challenge Daily Challenge Dec 1"
        )
    
    async def handle_create_challenge(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /create_challenge command"""
        if not self.is_admin(update.effective_user.id):
            return
        
        title = ' '.join(context.args)
        if not title:
            await update.message.reply_text(
                "⚠️ Usage: /create_challenge [title]"
            )
            return
        
        async with AsyncSessionLocal() as db:
            # Create challenge for tomorrow
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
            
            await update.message.reply_text(
                f"✅ Challenge created!\n\n"
                f"ID: {challenge.id}\n"
                f"Title: {title}\n"
                f"Start: {start_date.strftime('%Y-%m-%d %H:%M')}\n\n"
                f"Now add 3 videos using: /add_video {challenge.id}"
            )
    
    async def send_challenge_to_users(self, query, context):
        """Send active challenge to all active users"""
        async with AsyncSessionLocal() as db:
            # Get active challenge
            from sqlalchemy import select
            result = await db.execute(
                select(Challenge)
                .where(Challenge.status == ChallengeStatus.SCHEDULED)
                .order_by(Challenge.start_date)
                .limit(1)
            )
            challenge = result.scalar_one_or_none()
            
            if not challenge:
                await query.edit_message_text("⚠️ No scheduled challenges.")
                return
            
            # Activate challenge
            challenge.status = ChallengeStatus.ACTIVE
            await db.commit()
            
            # Get all active users
            result = await db.execute(
                select(User).where(User.status == UserStatus.ACTIVE)
            )
            users = result.scalars().all()
            
            # Send notification
            sent = 0
            for user in users:
                try:
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=(
                            f"🎬 New Challenge Available!\n\n"
                            f"{challenge.title}\n\n"
                            "Tap '🎬 Start Challenge' to begin!"
                        )
                    )
                    sent += 1
                except Exception as e:
                    logger.error(f"Failed to notify user {user.id}: {e}")
            
            await query.edit_message_text(
                f"✅ Challenge activated and sent to {sent} users!"
            )
    
    async def show_pending_payments(self, query, context):
        """Show pending payment approvals"""
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(Payment)
                .where(Payment.status == PaymentStatus.PENDING)
                .order_by(Payment.created_at.desc())
            )
            payments = result.scalars().all()
            
            if not payments:
                await query.edit_message_text("✅ No pending payments!")
                return
            
            text = "💳 Pending Payments:\n\n"
            keyboard = []
            
            for payment in payments[:10]:  # Show max 10
                user = await db.get(User, payment.user_id)
                text += f"User: @{user.username or user.telegram_id}\n"
                text += f"Amount: ${payment.amount}\n"
                text += f"Date: {payment.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ Approve {user.username or user.telegram_id}",
                        callback_data=f"approve_payment_{payment.id}"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def approve_payment(self, query, context, payment_id: int):
        """Approve a payment"""
        async with AsyncSessionLocal() as db:
            payment = await db.get(Payment, payment_id)
            if not payment:
                await query.answer("Payment not found.")
                return
            
            # Update payment
            payment.status = PaymentStatus.COMPLETED
            payment.approved_at = datetime.utcnow()
            payment.approved_by = query.from_user.id
            
            # Activate user
            await user_service.activate_user(db, payment.user_id)
            
            await db.commit()
            
            # Notify user
            user = await db.get(User, payment.user_id)
            try:
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text="✅ Your payment has been approved! You can now participate in challenges!"
                )
            except Exception as e:
                logger.error(f"Failed to notify user: {e}")
            
            await query.answer("✅ Payment approved!")
            await query.edit_message_text(
                f"✅ Payment approved for user {user.username or user.telegram_id}"
            )
    
    async def show_stats(self, query, context):
        """Show system statistics"""
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select, func
            
            # Count users by status
            result = await db.execute(
                select(User.status, func.count(User.id))
                .group_by(User.status)
            )
            user_counts = dict(result.all())
            
            # Count challenges
            result = await db.execute(select(func.count(Challenge.id)))
            challenge_count = result.scalar_one()
            
            # Count videos
            result = await db.execute(select(func.count(Video.id)))
            video_count = result.scalar_one()
            
            stats_text = (
                "📊 System Statistics\n\n"
                f"👥 Users:\n"
                f"• Active: {user_counts.get(UserStatus.ACTIVE, 0)}\n"
                f"• Pending: {user_counts.get(UserStatus.PENDING, 0)}\n"
                f"• Waitlisted: {user_counts.get(UserStatus.WAITLISTED, 0)}\n\n"
                f"🎬 Challenges: {challenge_count}\n"
                f"📹 Videos: {video_count}"
            )
            
            await query.edit_message_text(stats_text)


# Global instance
admin_handlers = AdminHandlers()
