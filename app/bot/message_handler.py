from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from app.database import AsyncSessionLocal
from app.database.models import Question, VideoAttempt, ChallengeAttempt
from app.services import challenge_service, user_service
from app.core.config import settings
from loguru import logger


class MessageHandler:
    """Handler for text messages"""
    
    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help message"""
        msg = "ℹ️ *Help*\n\n"
        msg += "🎬 *How to Play:*\n"
        msg += "1. Watch video without subtitles\n"
        msg += "2. Send voice message repeating phrase\n"
        msg += "3. Answer multiple choice question\n"
        msg += "4. Earn points & climb leaderboard!\n\n"
        msg += "🎯 *Points:*\n"
        msg += f"• Voice correct: {settings.POINTS_VOICE_CORRECT}pts\n"
        msg += f"• Question correct: {settings.POINTS_QUESTION_CORRECT}pts\n"
        msg += f"• Max per video: {settings.POINTS_VOICE_CORRECT + settings.POINTS_QUESTION_CORRECT}pts\n\n"
        msg += "🎤 *Voice Tips:*\n"
        msg += "• Speak clearly\n"
        msg += "• Try to match pronunciation\n"
        msg += f"• You get {settings.MAX_VOICE_ATTEMPTS} attempts\n"
        msg += "• Subtitles shown if needed\n\n"
        msg += "💡 Need support? Contact @admin"
        
        keyboard = [[InlineKeyboardButton("◀️ Back to Menu", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages from users"""
        
        text = update.message.text.strip()
        
        # Check if awaiting question answer
        if context.user_data.get('awaiting_answer'):
            await self.handle_question_answer(update, context)
            return
        
        # Unknown message
        await update.message.reply_text(
            "❓ I don't understand that command.\n\n"
            "Use the menu buttons to navigate."
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


# Global instance
message_handler = MessageHandler()