from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from typing import Optional, List
import secrets
import string
from datetime import datetime

from app.database.models import (
    User, Payment, ChallengeAttempt, WaitlistEntry,
    UserStatus, PaymentStatus, Challenge, ChallengeStatus
)
from loguru import logger


class UserService:
    """Service for user-related operations"""
    
    @staticmethod
    def generate_referral_code(length: int = 8) -> str:
        """Generate a unique referral code"""
        chars = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(length))
    
    async def create_user(
        self,
        db: AsyncSession,
        telegram_id: int,
        username: Optional[str] = None
    ) -> User:
        """Create a new user"""
        try:
            # Check if user exists
            result = await db.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                return existing_user
            
            # Generate unique referral code
            referral_code = self.generate_referral_code()
            
            user = User(
                telegram_id=telegram_id,
                username=username,
                referral_code=referral_code,
                status=UserStatus.PENDING
            )
            
            db.add(user)
            await db.commit()
            await db.refresh(user)
            
            logger.info(f"New user created: {telegram_id}")
            return user
            
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            await db.rollback()
            raise
    
    async def get_user_by_telegram_id(
        self,
        db: AsyncSession,
        telegram_id: int
    ) -> Optional[User]:
        """Get user by Telegram ID"""
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_referral_code(
        self,
        db: AsyncSession,
        referral_code: str
    ) -> Optional[User]:
        """Get user by referral code"""
        result = await db.execute(
            select(User).where(User.referral_code == referral_code)
        )
        return result.scalar_one_or_none()
    
    async def update_phone_number(
        self,
        db: AsyncSession,
        user_id: int,
        phone_number: str
    ) -> bool:
        """Update user's phone number"""
        try:
            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(phone_number=phone_number, updated_at=datetime.utcnow())
            )
            await db.commit()
            logger.info(f"Phone number updated for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating phone number: {e}")
            await db.rollback()
            return False
    
    async def activate_user(
        self,
        db: AsyncSession,
        user_id: int
    ) -> bool:
        """Activate a user after payment/referral verification"""
        try:
            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(status=UserStatus.ACTIVE, updated_at=datetime.utcnow())
            )
            await db.commit()
            logger.info(f"User {user_id} activated")
            return True
        except Exception as e:
            logger.error(f"Error activating user: {e}")
            await db.rollback()
            return False
    
    async def add_referral(
        self,
        db: AsyncSession,
        referrer_id: int,
        referred_user_id: int
    ) -> bool:
        """Record a referral"""
        try:
            # Update referred user
            await db.execute(
                update(User)
                .where(User.id == referred_user_id)
                .values(referred_by=referrer_id)
            )
            
            # Increment referrer count
            await db.execute(
                update(User)
                .where(User.id == referrer_id)
                .values(
                    referral_count=User.referral_count + 1,
                    updated_at=datetime.utcnow()
                )
            )
            
            await db.commit()
            logger.info(f"Referral recorded: {referrer_id} -> {referred_user_id}")
            return True
        except Exception as e:
            logger.error(f"Error recording referral: {e}")
            await db.rollback()
            return False
    
    async def check_referral_eligibility(
        self,
        db: AsyncSession,
        user_id: int,
        required_count: int = 5
    ) -> bool:
        """Check if user has enough referrals"""
        result = await db.execute(
            select(User.referral_count).where(User.id == user_id)
        )
        count = result.scalar_one_or_none()
        return count >= required_count if count else False
    
    async def add_points(
        self,
        db: AsyncSession,
        user_id: int,
        points: int
    ) -> bool:
        """Add points to user"""
        try:
            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(
                    total_points=User.total_points + points,
                    updated_at=datetime.utcnow()
                )
            )
            await db.commit()
            logger.info(f"Added {points} points to user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding points: {e}")
            await db.rollback()
            return False
    
    async def get_leaderboard(
        self,
        db: AsyncSession,
        limit: int = 10
    ) -> List[User]:
        """Get top users by points"""
        result = await db.execute(
            select(User)
            .where(User.status == UserStatus.ACTIVE)
            .order_by(User.total_points.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_user_rank(
        self,
        db: AsyncSession,
        user_id: int
    ) -> Optional[int]:
        """Get user's rank in leaderboard"""
        # Get count of users with more points
        result = await db.execute(
            select(func.count(User.id))
            .where(
                User.status == UserStatus.ACTIVE,
                User.total_points > (
                    select(User.total_points).where(User.id == user_id)
                )
            )
        )
        count = result.scalar_one()
        return count + 1
    
    async def can_participate_in_challenge(
        self,
        db: AsyncSession,
        user_id: int,
        challenge_id: int
    ) -> bool:
        """Check if user can participate in a challenge"""
        # Get user
        user = await db.get(User, user_id)
        if not user or user.status != UserStatus.ACTIVE:
            return False
        
        # Check if challenge is active
        challenge = await db.get(Challenge, challenge_id)
        if not challenge or challenge.status != ChallengeStatus.ACTIVE:
            return False
        
        # Check if user already has an attempt
        result = await db.execute(
            select(ChallengeAttempt)
            .where(
                ChallengeAttempt.user_id == user_id,
                ChallengeAttempt.challenge_id == challenge_id
            )
        )
        existing_attempt = result.scalar_one_or_none()
        
        return existing_attempt is None
    
    async def add_to_waitlist(
        self,
        db: AsyncSession,
        user_id: int,
        challenge_id: int
    ) -> bool:
        """Add user to waitlist for next challenge"""
        try:
            entry = WaitlistEntry(
                user_id=user_id,
                challenge_id=challenge_id
            )
            db.add(entry)
            await db.commit()
            logger.info(f"User {user_id} added to waitlist")
            return True
        except Exception as e:
            logger.error(f"Error adding to waitlist: {e}")
            await db.rollback()
            return False


# Global instance
user_service = UserService()
