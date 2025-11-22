from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Telegram Configuration
    TELEGRAM_BOT_TOKEN: str
    REQUIRED_CHANNEL_1: str
    REQUIRED_CHANNEL_2: str
    ADMIN_USER_IDS: str
    
    # Database
    DATABASE_URL: str
    
    # Ollama
    OLLAMA_API_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama2"
    
    # Whisper
    WHISPER_MODEL: str = "base"
    
    # Payment
    STRIPE_SECRET_KEY: str
    STRIPE_PUBLISHABLE_KEY: str
    PAYMENT_AMOUNT: int = 100
    BANK_CARD_NUMBER: str = "1234 5678 9012 3456"  # Default card number
    BANK_CARD_HOLDER: str = "Your Name"
    BANK_NAME: str = "Your Bank"
    
    # Application
    APP_NAME: str = "English Learning Bot"
    DEBUG: bool = True
    CHALLENGE_PRICE: float = 1.00
    REFERRAL_REQUIREMENT: int = 5
    MAX_VOICE_ATTEMPTS: int = 2
    POINTS_VOICE_CORRECT: int = 50
    POINTS_QUESTION_CORRECT: int = 50
    
    # File Storage
    VIDEO_STORAGE_PATH: str = "./videos"
    AUDIO_STORAGE_PATH: str = "./audio"
    MAX_UPLOAD_SIZE: int = 52428800
    
    # Challenge Timing
    CHALLENGE_START_HOUR: int = 9
    CHALLENGE_TIMEZONE: str = "UTC"
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "app.log"
    
    # Voice Recognition
    VOICE_SIMILARITY_THRESHOLD: float = 0.75
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def admin_ids(self) -> List[int]:
        """Parse admin IDs from comma-separated string"""
        return [int(id.strip()) for id in self.ADMIN_USER_IDS.split(",")]
    
    @property
    def required_channels(self) -> List[str]:
        """Get list of required channels"""
        return [self.REQUIRED_CHANNEL_1, self.REQUIRED_CHANNEL_2]


# Global settings instance
settings = Settings()

# Ensure directories exist
os.makedirs(settings.VIDEO_STORAGE_PATH, exist_ok=True)
os.makedirs(settings.AUDIO_STORAGE_PATH, exist_ok=True)
