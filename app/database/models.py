from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class UserStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    WAITLISTED = "waitlisted"
    BANNED = "banned"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ChallengeStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    SCHEDULED = "scheduled"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    status = Column(Enum(UserStatus), default=UserStatus.PENDING)
    referral_code = Column(String, unique=True, index=True)
    referred_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    referral_count = Column(Integer, default=0)
    total_points = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    payments = relationship("Payment", back_populates="user")
    challenge_attempts = relationship("ChallengeAttempt", back_populates="user")
    referrals = relationship("User", backref="referrer", remote_side=[id])


class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    stripe_payment_id = Column(String, unique=True, nullable=True)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(Integer, nullable=True)  # Admin ID
    
    # Relationships
    user = relationship("User", back_populates="payments")


class Challenge(Base):
    __tablename__ = "challenges"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    status = Column(Enum(ChallengeStatus), default=ChallengeStatus.SCHEDULED)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    videos = relationship("Video", back_populates="challenge")
    attempts = relationship("ChallengeAttempt", back_populates="challenge")


class Video(Base):
    __tablename__ = "videos"
    
    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    file_path = Column(String, nullable=False)
    file_id = Column(String, nullable=True)  # Telegram file_id for caching
    phrase = Column(Text, nullable=False)  # The English phrase to learn
    subtitle = Column(Text, nullable=True)
    movie_name = Column(String, nullable=True)
    order = Column(Integer, default=0)  # Order in challenge (1, 2, or 3)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    challenge = relationship("Challenge", back_populates="videos")
    attempts = relationship("VideoAttempt", back_populates="video")
    question = relationship("Question", uselist=False, back_populates="video")


class Question(Base):
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), unique=True, nullable=False)
    question_text = Column(Text, nullable=False)
    option_a = Column(Text, nullable=False)
    option_b = Column(Text, nullable=False)
    option_c = Column(Text, nullable=False)
    option_d = Column(Text, nullable=False)
    correct_option = Column(String(1), nullable=False)  # A, B, C, or D
    example_sentence = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    video = relationship("Video", back_populates="question")


class ChallengeAttempt(Base):
    __tablename__ = "challenge_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    total_points = Column(Integer, default=0)
    completed = Column(Boolean, default=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="challenge_attempts")
    challenge = relationship("Challenge", back_populates="attempts")
    video_attempts = relationship("VideoAttempt", back_populates="challenge_attempt")


class VideoAttempt(Base):
    __tablename__ = "video_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    challenge_attempt_id = Column(Integer, ForeignKey("challenge_attempts.id"), nullable=False)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    voice_attempts = Column(Integer, default=0)
    subtitle_shown = Column(Boolean, default=False)
    voice_successful = Column(Boolean, default=False)
    transcribed_text = Column(Text, nullable=True)
    question_answered = Column(Boolean, default=False)
    question_correct = Column(Boolean, default=False)
    user_answer = Column(String(1), nullable=True)
    points_earned = Column(Integer, default=0)
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    challenge_attempt = relationship("ChallengeAttempt", back_populates="video_attempts")
    video = relationship("Video", back_populates="attempts")


class WaitlistEntry(Base):
    __tablename__ = "waitlist"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    notified = Column(Boolean, default=False)
