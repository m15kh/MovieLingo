from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional, List, Tuple
from datetime import datetime

from app.database.models import (
    Challenge, Video, Question, ChallengeAttempt, VideoAttempt,
    ChallengeStatus, User
)
from app.core.config import settings
from loguru import logger


class ChallengeService:
    """Service for challenge-related operations"""
    
    async def create_challenge(
        self,
        db: AsyncSession,
        title: str,
        start_date: datetime
    ) -> Challenge:
        """Create a new challenge"""
        try:
            challenge = Challenge(
                title=title,
                start_date=start_date,
                status=ChallengeStatus.SCHEDULED
            )
            db.add(challenge)
            await db.commit()
            await db.refresh(challenge)
            logger.info(f"Challenge created: {challenge.id}")
            return challenge
        except Exception as e:
            logger.error(f"Error creating challenge: {e}")
            await db.rollback()
            raise
    
    async def get_active_challenge(
        self,
        db: AsyncSession
    ) -> Optional[Challenge]:
        """Get currently active challenge"""
        result = await db.execute(
            select(Challenge)
            .where(Challenge.status == ChallengeStatus.ACTIVE)
            .order_by(Challenge.start_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def get_challenge_videos(
        self,
        db: AsyncSession,
        challenge_id: int
    ) -> List[Video]:
        """Get all videos for a challenge"""
        result = await db.execute(
            select(Video)
            .where(Video.challenge_id == challenge_id)
            .order_by(Video.order)
        )
        return result.scalars().all()
    
    async def create_challenge_attempt(
        self,
        db: AsyncSession,
        user_id: int,
        challenge_id: int
    ) -> ChallengeAttempt:
        """Create a new challenge attempt for user"""
        try:
            attempt = ChallengeAttempt(
                user_id=user_id,
                challenge_id=challenge_id
            )
            db.add(attempt)
            await db.commit()
            await db.refresh(attempt)
            logger.info(f"Challenge attempt created for user {user_id}")
            return attempt
        except Exception as e:
            logger.error(f"Error creating challenge attempt: {e}")
            await db.rollback()
            raise
    
    async def get_user_challenge_attempt(
        self,
        db: AsyncSession,
        user_id: int,
        challenge_id: int
    ) -> Optional[ChallengeAttempt]:
        """Get user's attempt for a challenge"""
        result = await db.execute(
            select(ChallengeAttempt)
            .where(
                ChallengeAttempt.user_id == user_id,
                ChallengeAttempt.challenge_id == challenge_id
            )
        )
        return result.scalar_one_or_none()
    
    async def create_video_attempt(
        self,
        db: AsyncSession,
        challenge_attempt_id: int,
        video_id: int
    ) -> VideoAttempt:
        """Create a new video attempt"""
        try:
            attempt = VideoAttempt(
                challenge_attempt_id=challenge_attempt_id,
                video_id=video_id
            )
            db.add(attempt)
            await db.commit()
            await db.refresh(attempt)
            return attempt
        except Exception as e:
            logger.error(f"Error creating video attempt: {e}")
            await db.rollback()
            raise
    
    async def get_video_attempt(
        self,
        db: AsyncSession,
        challenge_attempt_id: int,
        video_id: int
    ) -> Optional[VideoAttempt]:
        """Get video attempt"""
        result = await db.execute(
            select(VideoAttempt)
            .where(
                VideoAttempt.challenge_attempt_id == challenge_attempt_id,
                VideoAttempt.video_id == video_id
            )
        )
        return result.scalar_one_or_none()
    
    async def record_voice_attempt(
        self,
        db: AsyncSession,
        video_attempt_id: int,
        transcribed_text: str,
        is_successful: bool
    ) -> bool:
        """Record a voice attempt"""
        try:
            attempt = await db.get(VideoAttempt, video_attempt_id)
            if not attempt:
                return False
            
            attempt.voice_attempts += 1
            attempt.transcribed_text = transcribed_text
            attempt.voice_successful = is_successful
            
            # Check if should show subtitle
            if attempt.voice_attempts >= settings.MAX_VOICE_ATTEMPTS and not is_successful:
                attempt.subtitle_shown = True
            
            await db.commit()
            return True
        except Exception as e:
            logger.error(f"Error recording voice attempt: {e}")
            await db.rollback()
            return False
    
    async def record_question_answer(
        self,
        db: AsyncSession,
        video_attempt_id: int,
        user_answer: str,
        is_correct: bool
    ) -> Tuple[bool, int]:
        """
        Record user's answer to question
        
        Returns:
            Tuple of (success, points_earned)
        """
        try:
            attempt = await db.get(VideoAttempt, video_attempt_id)
            if not attempt:
                return False, 0
            
            attempt.question_answered = True
            attempt.question_correct = is_correct
            attempt.user_answer = user_answer
            
            # Calculate points
            points = 0
            if attempt.voice_successful:
                points += settings.POINTS_VOICE_CORRECT
            if is_correct:
                points += settings.POINTS_QUESTION_CORRECT
            
            attempt.points_earned = points
            attempt.completed = True
            
            await db.commit()
            logger.info(f"Question answered - Points: {points}")
            return True, points
            
        except Exception as e:
            logger.error(f"Error recording question answer: {e}")
            await db.rollback()
            return False, 0
    
    async def update_challenge_attempt_points(
        self,
        db: AsyncSession,
        challenge_attempt_id: int,
        points: int
    ) -> bool:
        """Update total points for challenge attempt"""
        try:
            await db.execute(
                update(ChallengeAttempt)
                .where(ChallengeAttempt.id == challenge_attempt_id)
                .values(total_points=ChallengeAttempt.total_points + points)
            )
            await db.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating challenge points: {e}")
            await db.rollback()
            return False
    
    async def complete_challenge_attempt(
        self,
        db: AsyncSession,
        challenge_attempt_id: int
    ) -> bool:
        """Mark challenge attempt as completed"""
        try:
            await db.execute(
                update(ChallengeAttempt)
                .where(ChallengeAttempt.id == challenge_attempt_id)
                .values(
                    completed=True,
                    completed_at=datetime.utcnow()
                )
            )
            await db.commit()
            logger.info(f"Challenge attempt {challenge_attempt_id} completed")
            return True
        except Exception as e:
            logger.error(f"Error completing challenge: {e}")
            await db.rollback()
            return False
    
    async def get_user_progress(
        self,
        db: AsyncSession,
        user_id: int,
        challenge_id: int
    ) -> dict:
        """Get user's progress in a challenge"""
        attempt = await self.get_user_challenge_attempt(db, user_id, challenge_id)
        
        if not attempt:
            return {
                "started": False,
                "videos_completed": 0,
                "total_videos": 3,
                "points": 0
            }
        
        # Get video attempts
        result = await db.execute(
            select(VideoAttempt)
            .where(VideoAttempt.challenge_attempt_id == attempt.id)
        )
        video_attempts = result.scalars().all()
        
        completed = sum(1 for va in video_attempts if va.completed)
        
        return {
            "started": True,
            "videos_completed": completed,
            "total_videos": 3,
            "points": attempt.total_points,
            "completed": attempt.completed
        }
    
    async def get_question_for_video(
        self,
        db: AsyncSession,
        video_id: int
    ) -> Optional[Question]:
        """Get question for a video"""
        result = await db.execute(
            select(Question).where(Question.video_id == video_id)
        )
        return result.scalar_one_or_none()


# Global instance
challenge_service = ChallengeService()
