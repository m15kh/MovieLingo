import whisper
import os
from difflib import SequenceMatcher
from typing import Tuple, Optional
from app.core.config import settings
from loguru import logger


class WhisperService:
    """Service for handling voice transcription and phrase matching"""
    
    def __init__(self):
        self.model = None
        self.model_name = settings.WHISPER_MODEL
        self._load_model()
    
    def _load_model(self):
        """Load Whisper model"""
        try:
            logger.info(f"Loading Whisper model: {self.model_name}")
            self.model = whisper.load_model(self.model_name)
            logger.success("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise
    
    async def transcribe_audio(self, audio_path: str) -> Optional[str]:
        """
        Transcribe audio file to text
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Transcribed text or None if failed
        """
        try:
            if not os.path.exists(audio_path):
                logger.error(f"Audio file not found: {audio_path}")
                return None
            
            logger.info(f"Transcribing audio: {audio_path}")
            result = self.model.transcribe(audio_path, language="en")
            transcribed_text = result["text"].strip()
            
            logger.info(f"Transcription result: {transcribed_text}")
            return transcribed_text
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None
    
    @staticmethod
    def calculate_similarity(text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Normalize texts
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()
        
        # Calculate similarity
        similarity = SequenceMatcher(None, text1, text2).ratio()
        
        return similarity
    
    async def check_phrase_match(
        self, 
        audio_path: str, 
        target_phrase: str
    ) -> Tuple[bool, str, float]:
        """
        Check if transcribed audio matches target phrase
        
        Args:
            audio_path: Path to audio file
            target_phrase: Expected phrase
            
        Returns:
            Tuple of (is_match, transcribed_text, similarity_score)
        """
        transcribed = await self.transcribe_audio(audio_path)
        
        if not transcribed:
            return False, "", 0.0
        
        similarity = self.calculate_similarity(transcribed, target_phrase)
        is_match = similarity >= settings.VOICE_SIMILARITY_THRESHOLD
        
        logger.info(
            f"Phrase match check - Target: '{target_phrase}', "
            f"Transcribed: '{transcribed}', "
            f"Similarity: {similarity:.2f}, "
            f"Match: {is_match}"
        )
        
        return is_match, transcribed, similarity
    
    async def get_transcription_feedback(
        self, 
        transcribed: str, 
        target: str, 
        similarity: float
    ) -> str:
        """
        Generate feedback message for user
        
        Args:
            transcribed: What was transcribed
            target: What was expected
            similarity: Similarity score
            
        Returns:
            Feedback message
        """
        if similarity >= settings.VOICE_SIMILARITY_THRESHOLD:
            return "✅ Great job! That's correct!"
        elif similarity >= 0.5:
            return f"❌ Close, but not quite. You said: '{transcribed}'\nTry again!"
        else:
            return f"❌ That's not quite right. You said: '{transcribed}'\nTry again!"


# Global instance
whisper_service = WhisperService()
