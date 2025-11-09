from telegram import Update
from telegram.ext import ContextTypes

from app.database import AsyncSessionLocal
from app.database.models import Question, VideoAttempt, ChallengeAttempt
from app.services import challenge_service, user_service
from app.core.config import settings
from loguru import logger


class MessageHandler:
    """Handler for text messages"""
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages from users"""
        
        text = update.message.text.strip()
        
        # Check if awaiting question answer
        if context.user_data.get('awaiting_answer'):
            await self.handle_question_answer(update, context)
            return
        
        # Handle menu buttons
        if text == "🎬 Start Challenge":
            from app.bot.handlers import bot_handlers
            await bot_handlers.handle_start_challenge(update, context)
        
        elif text == "📊 Leaderboard":
            from app.bot.handlers import bot_handlers
            await bot_handlers.show_leaderboard(update, context)
        
        elif text == "📈 My Stats":
            from app.bot.handlers import bot_handlers
            await bot_handlers.show_my_stats(update, context)
        
        elif text == "ℹ️ Help":
            await self.show_help(update, context)
        
        else:
            # Unknown message
            await update.message.reply_text(
                "❓ I don't understand that command.\n"
                "Use the menu buttons or type /help"
            )
    
    async def handle_question_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user's answer to question"""
        
        answer = update.message.text.strip().upper()
        
        # Validate answer
        if answer not in ['A', 'B', 'C', 'D']:
            await update.message.reply_text(
                "⚠️ Please answer with A, B, C, or D"
            )
            return
        
        question_id = context.user_data.get('current_question_id')
        video_attempt_id = context.user_data.get('current_video_attempt_id')
        challenge_attempt_id = context.user_data.get('challenge_attempt_id')
        
        if not question_id or not video_attempt_id:
            await update.message.reply_text(
                "⚠️ Something went wrong. Please start the challenge again."
            )
            return
        
        async with AsyncSessionLocal() as db:
            # Get question
            question = await db.get(Question, question_id)
            if not question:
                await update.message.reply_text("⚠️ Question not found.")
                return
            
            # Check answer
            is_correct = (answer == question.correct_option)
            
            # Record answer
            success, points = await challenge_service.record_question_answer(
                db, video_attempt_id, answer, is_correct
            )
            
            if not success:
                await update.message.reply_text("❌ Error recording answer.")
                return
            
            # Update challenge attempt points
            await challenge_service.update_challenge_attempt_points(
                db, challenge_attempt_id, points
            )
            
            # Update user total points
            video_attempt = await db.get(VideoAttempt, video_attempt_id)
            challenge_attempt = await db.get(ChallengeAttempt, challenge_attempt_id)
            await user_service.add_points(db, challenge_attempt.user_id, points)
            
            # Send feedback
            if is_correct:
                feedback = (
                    f"✅ Correct! +{settings.POINTS_QUESTION_CORRECT} points!\n\n"
                    f"💡 Example:\n{question.example_sentence}\n\n"
                    f"Total points this video: {points}"
                )
            else:
                correct_answer = getattr(question, f'option_{question.correct_option.lower()}')
                feedback = (
                    f"❌ Incorrect.\n\n"
                    f"The correct answer was {question.correct_option}: {correct_answer}\n\n"
                    f"💡 Example:\n{question.example_sentence}\n\n"
                    f"Total points this video: {points}"
                )
            
            await update.message.reply_text(feedback)
            
            # Clear question context
            context.user_data['awaiting_answer'] = False
            context.user_data['current_question_id'] = None
            context.user_data['current_video_attempt_id'] = None
            
            # Move to next video
            context.user_data['current_video_index'] = context.user_data.get('current_video_index', 0) + 1
            
            await update.message.reply_text("⏭️ Moving to next video...")
            
            # Send next video
            from app.bot.handlers import bot_handlers
            await bot_handlers.send_next_video(update, context, db)
    
    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help message"""
        help_text = (
            "ℹ️ Help\n\n"
            "🎬 *How to Play:*\n"
            "1. Watch the video without subtitles\n"
            "2. Send a voice message repeating the phrase\n"
            "3. Answer the multiple choice question\n"
            "4. Earn points and climb the leaderboard!\n\n"
            "🎯 *Points:*\n"
            f"• Voice correct: {settings.POINTS_VOICE_CORRECT} points\n"
            f"• Question correct: {settings.POINTS_QUESTION_CORRECT} points\n"
            f"• Max per video: {settings.POINTS_VOICE_CORRECT + settings.POINTS_QUESTION_CORRECT} points\n\n"
            "🎤 *Voice Tips:*\n"
            "• Speak clearly\n"
            "• Try to match the pronunciation\n"
            f"• You get {settings.MAX_VOICE_ATTEMPTS} attempts\n"
            "• Subtitles shown after first attempts\n\n"
            "📱 *Commands:*\n"
            "/start - Restart bot\n"
            "/help - Show this message\n\n"
            "Need support? Contact @admin"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')


# Global instance
message_handler = MessageHandler()
