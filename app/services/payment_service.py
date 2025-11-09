import stripe
from typing import Optional, Dict
from app.core.config import settings
from loguru import logger

stripe.api_key = settings.STRIPE_SECRET_KEY


class PaymentService:
    """Service for handling payments via Stripe"""
    
    def __init__(self):
        self.publishable_key = settings.STRIPE_PUBLISHABLE_KEY
        self.amount = settings.PAYMENT_AMOUNT  # Amount in cents
    
    async def create_payment_intent(
        self, 
        user_id: int, 
        amount: Optional[int] = None
    ) -> Optional[Dict]:
        """
        Create a Stripe payment intent
        
        Args:
            user_id: User ID for metadata
            amount: Amount in cents (defaults to configured amount)
            
        Returns:
            Payment intent data or None if failed
        """
        try:
            payment_amount = amount or self.amount
            
            intent = stripe.PaymentIntent.create(
                amount=payment_amount,
                currency="usd",
                metadata={
                    "user_id": user_id,
                    "product": "challenge_access"
                },
                description=f"English Learning Challenge Access - User {user_id}"
            )
            
            logger.info(f"Payment intent created for user {user_id}: {intent.id}")
            
            return {
                "payment_intent_id": intent.id,
                "client_secret": intent.client_secret,
                "amount": payment_amount,
                "status": intent.status
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {e}")
            return None
        except Exception as e:
            logger.error(f"Payment intent creation failed: {e}")
            return None
    
    async def verify_payment(self, payment_intent_id: str) -> bool:
        """
        Verify if a payment was successful
        
        Args:
            payment_intent_id: Stripe payment intent ID
            
        Returns:
            True if payment was successful
        """
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            is_successful = intent.status == "succeeded"
            
            logger.info(
                f"Payment verification - ID: {payment_intent_id}, "
                f"Status: {intent.status}, Success: {is_successful}"
            )
            
            return is_successful
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe verification error: {e}")
            return False
        except Exception as e:
            logger.error(f"Payment verification failed: {e}")
            return False
    
    async def create_payment_link(self, user_id: int) -> Optional[str]:
        """
        Create a payment link for user
        
        Args:
            user_id: User ID
            
        Returns:
            Payment link URL or None
        """
        try:
            # Create a checkout session
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[
                    {
                        'price_data': {
                            'currency': 'usd',
                            'product_data': {
                                'name': 'English Learning Challenge Access',
                                'description': 'Daily video challenges with AI-powered feedback',
                            },
                            'unit_amount': self.amount,
                        },
                        'quantity': 1,
                    },
                ],
                mode='payment',
                success_url='https://t.me/your_bot?success=true',
                cancel_url='https://t.me/your_bot?cancelled=true',
                metadata={
                    'user_id': user_id
                }
            )
            
            logger.info(f"Payment link created for user {user_id}: {session.url}")
            return session.url
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating link: {e}")
            return None
        except Exception as e:
            logger.error(f"Payment link creation failed: {e}")
            return None
    
    async def refund_payment(self, payment_intent_id: str) -> bool:
        """
        Refund a payment
        
        Args:
            payment_intent_id: Payment intent ID to refund
            
        Returns:
            True if refund was successful
        """
        try:
            refund = stripe.Refund.create(
                payment_intent=payment_intent_id
            )
            
            logger.info(f"Refund created: {refund.id}")
            return refund.status == "succeeded"
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe refund error: {e}")
            return False
        except Exception as e:
            logger.error(f"Refund failed: {e}")
            return False
    
    def get_publishable_key(self) -> str:
        """Get Stripe publishable key for frontend"""
        return self.publishable_key


# Global instance
payment_service = PaymentService()
