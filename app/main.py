from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import datetime

from app.core.config import settings
from app.database import get_db, init_db
from app.database.models import User, Challenge, UserStatus, ChallengeStatus
from app.services import user_service, challenge_service
from loguru import logger

# Configure logging
logger.add(
    settings.LOG_FILE,
    rotation="500 MB",
    level=settings.LOG_LEVEL
)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    debug=settings.DEBUG
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Run on startup"""
    logger.info("Starting FastAPI application...")
    logger.info(f"Debug mode: {settings.DEBUG}")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on shutdown"""
    logger.info("Shutting down FastAPI application...")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "app": settings.APP_NAME,
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


# User endpoints
@app.get("/api/users/{telegram_id}")
async def get_user(
    telegram_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get user by Telegram ID"""
    user = await user_service.get_user_by_telegram_id(db, telegram_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "status": user.status.value,
        "total_points": user.total_points,
        "referral_code": user.referral_code,
        "referral_count": user.referral_count
    }


@app.get("/api/leaderboard")
async def get_leaderboard(
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """Get leaderboard"""
    users = await user_service.get_leaderboard(db, limit)
    
    return [
        {
            "rank": i + 1,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "points": user.total_points
        }
        for i, user in enumerate(users)
    ]


@app.get("/api/challenges/active")
async def get_active_challenge(db: AsyncSession = Depends(get_db)):
    """Get active challenge"""
    challenge = await challenge_service.get_active_challenge(db)
    
    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active challenge"
        )
    
    videos = await challenge_service.get_challenge_videos(db, challenge.id)
    
    return {
        "id": challenge.id,
        "title": challenge.title,
        "start_date": challenge.start_date.isoformat(),
        "status": challenge.status.value,
        "video_count": len(videos)
    }


@app.get("/api/user/{telegram_id}/progress/{challenge_id}")
async def get_user_progress(
    telegram_id: int,
    challenge_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get user's progress in a challenge"""
    user = await user_service.get_user_by_telegram_id(db, telegram_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    progress = await challenge_service.get_user_progress(db, user.id, challenge_id)
    
    return progress


@app.post("/api/webhook/stripe")
async def stripe_webhook(
    payload: dict,
    db: AsyncSession = Depends(get_db)
):
    """Handle Stripe webhook events"""
    # TODO: Verify webhook signature
    
    event_type = payload.get('type')
    
    if event_type == 'payment_intent.succeeded':
        payment_intent = payload['data']['object']
        user_id = payment_intent['metadata'].get('user_id')
        
        if user_id:
            # Record payment
            from app.database.models import Payment, PaymentStatus
            
            payment = Payment(
                user_id=int(user_id),
                amount=payment_intent['amount'] / 100,  # Convert from cents
                stripe_payment_id=payment_intent['id'],
                status=PaymentStatus.COMPLETED
            )
            db.add(payment)
            
            # Activate user
            await user_service.activate_user(db, int(user_id))
            
            await db.commit()
            
            logger.info(f"Payment processed for user {user_id}")
    
    return {"status": "success"}


@app.get("/api/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get system statistics"""
    from sqlalchemy import select, func
    
    # Count users
    result = await db.execute(select(func.count(User.id)))
    total_users = result.scalar_one()
    
    result = await db.execute(
        select(func.count(User.id)).where(User.status == UserStatus.ACTIVE)
    )
    active_users = result.scalar_one()
    
    # Count challenges
    result = await db.execute(select(func.count(Challenge.id)))
    total_challenges = result.scalar_one()
    
    result = await db.execute(
        select(func.count(Challenge.id)).where(Challenge.status == ChallengeStatus.ACTIVE)
    )
    active_challenges = result.scalar_one()
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_challenges": total_challenges,
        "active_challenges": active_challenges
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
