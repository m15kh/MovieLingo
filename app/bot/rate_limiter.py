from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List
from loguru import logger


class RateLimiter:
    """Rate limiter to prevent spam and abuse"""
    
    def __init__(self):
        # Store message timestamps per user
        self.user_messages: Dict[int, List[datetime]] = defaultdict(list)
        # Store temporarily banned users
        self.temp_banned: Dict[int, datetime] = {}
        
        # Configuration
        self.MAX_MESSAGES = 5  # Max messages
        self.TIME_WINDOW = 2  # In seconds
        self.BAN_DURATION = 60  # Ban duration in seconds (1 minute)
        self.SEVERE_BAN_DURATION = 300  # 5 minutes for severe spam
        self.SEVERE_THRESHOLD = 15  # Messages count for severe ban
    
    def check_rate_limit(self, user_id: int) -> tuple[bool, str, int]:
        """
        Check if user exceeded rate limit
        Returns: (is_allowed, reason, cooldown_seconds)
        """
        now = datetime.now()
        
        # Check if user is temporarily banned
        if user_id in self.temp_banned:
            ban_until = self.temp_banned[user_id]
            if now < ban_until:
                remaining = int((ban_until - now).total_seconds())
                return False, "temp_banned", remaining
            else:
                # Ban expired, remove from list
                del self.temp_banned[user_id]
                self.user_messages[user_id] = []
        
        # Clean old messages (outside time window)
        cutoff_time = now - timedelta(seconds=self.TIME_WINDOW)
        self.user_messages[user_id] = [
            msg_time for msg_time in self.user_messages[user_id]
            if msg_time > cutoff_time
        ]
        
        # Check message count
        message_count = len(self.user_messages[user_id])
        
        if message_count >= self.MAX_MESSAGES:
            # Determine ban duration based on severity
            if message_count >= self.SEVERE_THRESHOLD:
                ban_duration = self.SEVERE_BAN_DURATION
                ban_type = "severe_spam"
            else:
                ban_duration = self.BAN_DURATION
                ban_type = "rate_limit"
            
            # Add to temp ban list
            self.temp_banned[user_id] = now + timedelta(seconds=ban_duration)
            
            logger.warning(
                f"User {user_id} rate limited: {message_count} messages in {self.TIME_WINDOW}s. "
                f"Banned for {ban_duration}s"
            )
            
            return False, ban_type, ban_duration
        
        # Add current message timestamp
        self.user_messages[user_id].append(now)
        
        return True, "allowed", 0
    
    def reset_user(self, user_id: int):
        """Reset rate limit for a user (admin use)"""
        if user_id in self.user_messages:
            del self.user_messages[user_id]
        if user_id in self.temp_banned:
            del self.temp_banned[user_id]
    
    def is_temp_banned(self, user_id: int) -> tuple[bool, int]:
        """Check if user is temporarily banned"""
        if user_id in self.temp_banned:
            now = datetime.now()
            ban_until = self.temp_banned[user_id]
            if now < ban_until:
                remaining = int((ban_until - now).total_seconds())
                return True, remaining
            else:
                del self.temp_banned[user_id]
        return False, 0
    
    def cleanup_old_data(self):
        """Clean up old data (call periodically)"""
        now = datetime.now()
        
        # Remove expired bans
        expired_bans = [
            user_id for user_id, ban_until in self.temp_banned.items()
            if now >= ban_until
        ]
        for user_id in expired_bans:
            del self.temp_banned[user_id]
        
        # Remove old message timestamps
        cutoff_time = now - timedelta(seconds=self.TIME_WINDOW * 2)
        for user_id in list(self.user_messages.keys()):
            self.user_messages[user_id] = [
                msg_time for msg_time in self.user_messages[user_id]
                if msg_time > cutoff_time
            ]
            # Remove empty entries
            if not self.user_messages[user_id]:
                del self.user_messages[user_id]


# Global instance
rate_limiter = RateLimiter()