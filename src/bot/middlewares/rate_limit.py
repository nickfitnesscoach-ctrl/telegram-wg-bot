"""
Rate limiting middleware for Telegram WireGuard Bot
"""
import logging
from datetime import datetime, timedelta
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from ...config.settings import settings
from ...config.logging_config import get_audit_logger
from ...database.models import get_db_session, RateLimit


class RateLimitMiddleware(BaseMiddleware):
    """
    Rate limiting middleware to prevent command spam
    Implements TZ requirement: "Rate limiting (максимум 5 команд в минуту на пользователя)"
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.audit_logger = get_audit_logger()
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Main middleware handler"""
        
        # Only process messages and callback queries
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)
        
        # Get user from auth middleware
        user = data.get('user')
        if not user:
            # No user data, skip rate limiting
            return await handler(event, data)
        
        # Check if user is rate limited
        try:
            is_allowed = await self._check_rate_limit(user.id, user.telegram_id)
            
            if not is_allowed:
                await self._handle_rate_limit_exceeded(event, user.telegram_id)
                return  # Block further processing
            
        except Exception as e:
            self.logger.error(f"Rate limit check error: {e}")
            # On error, allow the request (fail open)
        
        # Continue to next middleware/handler
        return await handler(event, data)
    
    async def _check_rate_limit(self, user_id: int, telegram_id: int) -> bool:
        """
        Check if user has exceeded rate limit
        Returns True if request is allowed, False if rate limited
        """
        now = datetime.utcnow()
        window_start = now.replace(second=0, microsecond=0)  # Current minute
        
        try:
            async with await get_db_session() as session:
                from sqlalchemy import select, and_
                
                # Find rate limit record for current window
                result = await session.execute(
                    select(RateLimit).where(
                        and_(
                            RateLimit.user_id == user_id,
                            RateLimit.window_start == window_start
                        )
                    )
                )
                rate_limit_record = result.scalar_one_or_none()
                
                if rate_limit_record:
                    # Check if limit exceeded
                    if rate_limit_record.command_count >= settings.MAX_COMMANDS_PER_MINUTE:
                        # Log rate limit violation
                        self.audit_logger.warning(
                            f"Rate limit exceeded | user_id={telegram_id} | "
                            f"count={rate_limit_record.command_count} | "
                            f"limit={settings.MAX_COMMANDS_PER_MINUTE}"
                        )
                        return False
                    
                    # Increment counter
                    rate_limit_record.command_count += 1
                    
                else:
                    # Create new rate limit record
                    rate_limit_record = RateLimit(
                        user_id=user_id,
                        window_start=window_start,
                        command_count=1
                    )
                    session.add(rate_limit_record)
                
                await session.commit()
                
                # Clean up old rate limit records (older than 5 minutes)
                await self._cleanup_old_records(session, now)
                
                return True
                
        except Exception as e:
            self.logger.error(f"Database error in rate limit check: {e}")
            return True  # Fail open
    
    async def _cleanup_old_records(self, session, current_time: datetime) -> None:
        """Clean up rate limit records older than 5 minutes"""
        try:
            cutoff_time = current_time - timedelta(minutes=5)
            
            from sqlalchemy import delete
            
            await session.execute(
                delete(RateLimit).where(RateLimit.window_start < cutoff_time)
            )
            await session.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old rate limit records: {e}")
    
    async def _handle_rate_limit_exceeded(
        self, 
        event: TelegramObject, 
        telegram_id: int
    ) -> None:
        """Handle rate limit exceeded"""
        
        message_text = (
            "⏱️ <b>Превышен лимит команд</b>\n\n"
            f"Максимум <b>{settings.MAX_COMMANDS_PER_MINUTE} команд в минуту</b>.\n"
            "Подождите немного перед следующей командой."
        )
        
        if isinstance(event, Message):
            try:
                await event.answer(message_text, parse_mode="HTML")
            except Exception as e:
                self.logger.error(f"Failed to send rate limit message: {e}")
        
        elif isinstance(event, CallbackQuery):
            try:
                await event.answer(
                    f"⏱️ Лимит команд: {settings.MAX_COMMANDS_PER_MINUTE}/мин", 
                    show_alert=True
                )
            except Exception as e:
                self.logger.error(f"Failed to answer callback query: {e}")


class RateLimitHelper:
    """Helper class for rate limiting operations"""
    
    @staticmethod
    async def get_user_current_count(user_id: int) -> int:
        """Get current command count for user in current minute"""
        try:
            now = datetime.utcnow()
            window_start = now.replace(second=0, microsecond=0)
            
            async with await get_db_session() as session:
                from sqlalchemy import select, and_
                
                result = await session.execute(
                    select(RateLimit).where(
                        and_(
                            RateLimit.user_id == user_id,
                            RateLimit.window_start == window_start
                        )
                    )
                )
                rate_limit_record = result.scalar_one_or_none()
                
                return rate_limit_record.command_count if rate_limit_record else 0
                
        except Exception:
            return 0
    
    @staticmethod
    async def get_remaining_commands(user_id: int) -> int:
        """Get remaining commands for user in current minute"""
        current_count = await RateLimitHelper.get_user_current_count(user_id)
        return max(0, settings.MAX_COMMANDS_PER_MINUTE - current_count)
    
    @staticmethod
    async def reset_user_rate_limit(user_id: int) -> bool:
        """Reset rate limit for user (admin function)"""
        try:
            now = datetime.utcnow()
            window_start = now.replace(second=0, microsecond=0)
            
            async with await get_db_session() as session:
                from sqlalchemy import delete, and_
                
                await session.execute(
                    delete(RateLimit).where(
                        and_(
                            RateLimit.user_id == user_id,
                            RateLimit.window_start == window_start
                        )
                    )
                )
                await session.commit()
                return True
                
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to reset rate limit: {e}")
            return False
    
    @staticmethod
    async def get_rate_limit_stats() -> Dict[str, Any]:
        """Get rate limiting statistics for monitoring"""
        try:
            now = datetime.utcnow()
            window_start = now.replace(second=0, microsecond=0)
            
            async with await get_db_session() as session:
                from sqlalchemy import select, func
                
                # Count active rate limits
                result = await session.execute(
                    select(func.count(RateLimit.id)).where(
                        RateLimit.window_start == window_start
                    )
                )
                active_limits = result.scalar() or 0
                
                # Count users hitting limit
                result = await session.execute(
                    select(func.count(RateLimit.id)).where(
                        RateLimit.window_start == window_start,
                        RateLimit.command_count >= settings.MAX_COMMANDS_PER_MINUTE
                    )
                )
                users_at_limit = result.scalar() or 0
                
                return {
                    "active_rate_limits": active_limits,
                    "users_at_limit": users_at_limit,
                    "limit_per_minute": settings.MAX_COMMANDS_PER_MINUTE,
                    "window_start": window_start.isoformat()
                }
                
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get rate limit stats: {e}")
            return {
                "active_rate_limits": 0,
                "users_at_limit": 0,
                "limit_per_minute": settings.MAX_COMMANDS_PER_MINUTE,
                "error": str(e)
            }


def rate_limit_exempt(func: Callable) -> Callable:
    """
    Decorator to exempt a handler from rate limiting
    Usage: @rate_limit_exempt
    """
    func._rate_limit_exempt = True
    return func


def check_rate_limit_exempt(handler: Callable) -> bool:
    """Check if handler is exempt from rate limiting"""
    return getattr(handler, '_rate_limit_exempt', False)
