from telegram import Update
from telegram.ext import ContextTypes
import os
import uuid
from datetime import datetime

from app.database import AsyncSessionLocal
from app.database.models import VideoAttempt
from app.services import whisper_service, challenge_service, user_service, ollama_service
from app.core.config import settings
from loguru import logger


class VoiceHandler:
    """Handler for voice message processing"""
    
    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process voice message from user"""
        
        # Check if user is in a challenge
        video_attempt_id = context.user_data.get('current_video_attempt_id')
        video_id = context.user_data.get('current_video_id')
        
        if not video_attempt_id or not video_id:
            await update.message.reply_text(
                "⚠️ Please start a challenge first using '🎬 Start Challenge'"
            )
            return
        
        async with AsyncSessionLocal() as db:
            # Get video attempt
            video_attempt = await db.get(VideoAttempt, video_attempt_id)
            if not video_attempt:
                await update.message.reply_text("⚠️ Video attempt not found.")
                return
            
            # Check if already completed
            if video_attempt.completed:
                await update.message.reply_text("✅ You've already completed this video!")
                return
            
            # Check attempt limit
            max_attempts = settings.MAX_VOICE_ATTEMPTS
            if not video_attempt.subtitle_shown:
                remaining = max_attempts - video_attempt.voice_attempts
            else:
                remaining = max_attempts - (video_attempt.voice_attempts - max_attempts)
            
            if remaining <= 0 and not video_attempt.subtitle_shown:
                # Show subtitle and allow more attempts
                await self.show_subtitle(update, context, db, video_attempt)
                return
            elif remaining <= 0 and video_attempt.subtitle_shown:
                # No more attempts
                await self.handle_failed_voice(update, context, db, video_attempt)
                return
            
            # Download voice message
            voice_file = await update.message.voice.get_file()
            
            # Create unique filename
            audio_filename = f"{uuid.uuid4()}.ogg"
            audio_path = os.path.join(settings.AUDIO_STORAGE_PATH, audio_filename)
            
            try:
                await voice_file.download_to_drive(audio_path)
                logger.info(f"Voice downloaded: {audio_path}")
                
                # Get target phrase
                video = await db.get(Video, video_id)
                target_phrase = video.phrase
                
                # Process voice
                await update.message.reply_text("🎧 Processing your voice...")
                
                is_match, transcribed, similarity = await whisper_service.check_phrase_match(
                    audio_path, target_phrase
                )
                
                # Record attempt
                await challenge_service.record_voice_attempt(
                    db, video_attempt_id, transcribed, is_match
                )
                
                if is_match:
                    # Success!
                    await self.handle_successful_voice(
                        update, context, db, video_attempt
                    )
                else:
                    # Failed attempt
                    feedback = await whisper_service.get_transcription_feedback(
                        transcribed, target_phrase, similarity
                    )
                    
                    # Refresh video_attempt to get updated voice_attempts
                    await db.refresh(video_attempt)
                    
                    if not video_attempt.subtitle_shown:
                        remaining = max_attempts - video_attempt.voice_attempts
                    else:
                        remaining = max_attempts - (video_attempt.voice_attempts - max_attempts)
                    
                    if remaining > 0:
                        await update.message.reply_text(
                            f"{feedback}\n\n"
                            f"Attempts remaining: {remaining}"
                        )
                    else:
                        # Show subtitle
                        await self.show_subtitle(update, context, db, video_attempt)
                
            except Exception as e:
                logger.error(f"Error processing voice: {e}")
                await update.message.reply_text(
                    "❌ Error processing voice. Please try again."
                )
            finally:
                # Clean up audio file
                if os.path.exists(audio_path):
                    os.remove(audio_path)
    
    async def show_subtitle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        db,
        video_attempt: VideoAttempt
    ):
        """Show subtitle to user"""
        video = await db.get(Video, video_attempt.video_id)
        
        await update.message.reply_text(
            f"📝 Subtitle:\n\n\"{video.subtitle or video.phrase}\"\n\n"
            f"Now try again! You have {settings.MAX_VOICE_ATTEMPTS} more attempts."
        )
    
    async def handle_successful_voice(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        db,
        video_attempt: VideoAttempt
    ):
        """Handle successful voice recognition"""
        await update.message.reply_text(
            "✅ Perfect! That's correct!\n\n"
            f"You earned {settings.POINTS_VOICE_CORRECT} points! 🎉"
        )
        
        # Show question
        await self.send_question(update, context, db, video_attempt)
    
    async def handle_failed_voice(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        db,
        video_attempt: VideoAttempt
    ):
        """Handle failed voice attempts"""
        video = await db.get(Video, video_attempt.video_id)
        
        await update.message.reply_text(
            "😔 You couldn't say it today.\n\n"
            f"The phrase was: \"{video.phrase}\"\n\n"
            "Don't worry, you'll get it next time! 💪"
        )
        
        # Still show question with 0 voice points
        await self.send_question(update, context, db, video_attempt)
    
    async def send_question(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        db,
        video_attempt: VideoAttempt
    ):
        """Send multiple choice question"""
        video = await db.get(Video, video_attempt.video_id)
        
        # Get or generate question
        question = await challenge_service.get_question_for_video(db, video.id)
        
        if not question:
            # Generate question using AI
            question_data = await ollama_service.generate_question(
                video.phrase,
                video.movie_name
            )
            
            if not question_data:
                # Use fallback
                question_data = await ollama_service.generate_fallback_question(video.phrase)
            
            # Save question
            from app.database.models import Question
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
        
        # Format question
        question_text = (
            f"❓ Question\n\n"
            f"{question.question_text}\n\n"
            f"A) {question.option_a}\n"
            f"B) {question.option_b}\n"
            f"C) {question.option_c}\n"
            f"D) {question.option_d}\n\n"
            f"Reply with A, B, C, or D"
        )
        
        await update.message.reply_text(question_text)
        
        # Store question ID in context
        context.user_data['current_question_id'] = question.id
        context.user_data['awaiting_answer'] = True


# Global instance
voice_handler = VoiceHandler()
