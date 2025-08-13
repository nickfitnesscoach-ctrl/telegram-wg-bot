"""
Enhanced Rate limiting middleware for PRE-PRODUCTION - Fast & Bulletproof
Anti-spam protection with memory-efficient implementation
"""
import time
from typing import Callable, Dict, Any, Awaitable, List

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from ...config.settings import settings
from ...config.logging_config import get_audit_logger


class FastRateLimit(BaseMiddleware):
    """
    Lightning-fast rate limiting using in-memory buckets
    Perfect for pre-production deployment - no DB dependencies
    """
    
    def __init__(self, per_user_per_min: int = None):
        self.per_user_per_min = per_user_per_min or settings.MAX_COMMANDS_PER_MINUTE
        self.bucket: Dict[int, List[float]] = {}  # user_id -> [timestamps]
        self.audit_logger = get_audit_logger()
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Main rate limiting logic - optimized for speed"""
        
        # Extract user ID
        user_id = self._get_user_id(event)
        if not user_id:
            return await handler(event, data)
        
        now = time.monotonic()
        
        # Get or create user bucket
        arr = self.bucket.setdefault(user_id, [])
        
        # Clean old commands (older than 60 seconds) - efficient cleanup
        while arr and now - arr[0] > 60:
            arr.pop(0)
        
        # Check rate limit
        if len(arr) >= self.per_user_per_min:
            await self._handle_rate_limit(event, user_id)
            return  # Block the request
        
        # Add current command timestamp
        arr.append(now)
        
        # Continue to handler
        return await handler(event, data)
    
    def _get_user_id(self, event: TelegramObject) -> int | None:
        """Extract user ID from event - fast path"""
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            return event.from_user.id
        elif hasattr(event, 'from_user') and event.from_user:
            return event.from_user.id
        return None
    
    async def _handle_rate_limit(self, event: TelegramObject, user_id: int) -> None:
        """Handle rate limit exceeded - quick response"""
        
        # Log violation for monitoring
        self.audit_logger.warning(f"RATE_LIMIT user_id={user_id} limit={self.per_user_per_min}/min")
        
        # Send concise user message
        message_text = "⚠️ Слишком часто. Попробуйте позже."
        
        try:
            if isinstance(event, Message):
                await event.answer(message_text)
            elif isinstance(event, CallbackQuery):
                await event.answer(message_text, show_alert=True)
        except Exception as e:
            # Fail silently to avoid infinite loops
            self.audit_logger.error(f"Rate limit notification failed: {e}")


class ProgressiveRateLimit(BaseMiddleware):
    """
    Advanced rate limiting with progressive penalties for repeat offenders
    Implements exponential backoff for spammers
    """
    
    def __init__(self):
        self.buckets: Dict[int, Dict[str, Any]] = {}
        self.audit_logger = get_audit_logger()
        super().__init__()
    
    async def __call__(self, handler, event, data):
        user_id = self._get_user_id(event)
        if not user_id:
            return await handler(event, data)
        
        now = time.monotonic()
        bucket = self.buckets.setdefault(user_id, {
            'commands': [],
            'violations': 0,
            'last_violation': 0,
            'penalty_until': 0
        })
        
        # Check if user is in penalty timeout
        if now < bucket['penalty_until']:
            remaining = bucket['penalty_until'] - now
            await self._send_penalty_message(event, remaining)
            return
        
        # Clean old commands (60-second window)
        bucket['commands'] = [t for t in bucket['commands'] if now - t <= 60]
        
        # Calculate dynamic limit based on violation history
        base_limit = settings.MAX_COMMANDS_PER_MINUTE
        if bucket['violations'] > 0:
            # Reduce limit for repeat offenders (minimum 1 command/min)
            limit = max(1, base_limit - bucket['violations'])
        else:
            limit = base_limit
        
        # Check if limit exceeded
        if len(bucket['commands']) >= limit:
            bucket['violations'] += 1
            bucket['last_violation'] = now
            
            # Progressive penalty: exponential backoff (max 5 minutes)
            penalty_seconds = min(300, 30 * (2 ** (bucket['violations'] - 1)))
            bucket['penalty_until'] = now + penalty_seconds
            
            self.audit_logger.warning(
                f"PROGRESSIVE_RATE_LIMIT user_id={user_id} violations={bucket['violations']} "
                f"penalty={penalty_seconds}s limit={limit}"
            )
            
            await self._send_penalty_message(event, penalty_seconds)
            return
        
        # Add command and continue
        bucket['commands'].append(now)
        
        # Reset violations after good behavior (24 hours clean)
        if bucket['violations'] > 0 and (now - bucket['last_violation']) > 86400:
            bucket['violations'] = 0
            self.audit_logger.info(f"Rate limit violations reset for user_id={user_id}")
        
        return await handler(event, data)
    
    def _get_user_id(self, event) -> int | None:
        """Fast user ID extraction"""
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            return event.from_user.id
        return None
    
    async def _send_penalty_message(self, event, remaining_seconds: float):
        """Send penalty notification with remaining time"""
        minutes = int(remaining_seconds // 60)
        seconds = int(remaining_seconds % 60)
        
        if minutes > 0:
            time_str = f"{minutes}м {seconds}с"
        else:
            time_str = f"{seconds}с"
        
        message = f"🚫 Превышен лимит команд. Попробуйте через {time_str}"
        
        try:
            if isinstance(event, Message):
                await event.answer(message)
            elif isinstance(event, CallbackQuery):
                await event.answer(message, show_alert=True)
        except Exception:
            pass  # Fail silently to prevent spam loops


class AdaptiveRateLimit(BaseMiddleware):
    """
    Adaptive rate limiting that adjusts based on system load
    """
    
    def __init__(self):
        self.buckets: Dict[int, List[float]] = {}
        self.system_load_factor = 1.0
        self.audit_logger = get_audit_logger()
        super().__init__()
    
    def update_system_load(self, load_factor: float):
        """Update system load factor (0.5 = high load, 2.0 = low load)"""
        self.system_load_factor = max(0.1, min(3.0, load_factor))
    
    async def __call__(self, handler, event, data):
        user_id = self._get_user_id(event)
        if not user_id:
            return await handler(event, data)
        
        now = time.monotonic()
        
        # Adaptive limit based on system load
        base_limit = settings.MAX_COMMANDS_PER_MINUTE
        adjusted_limit = max(1, int(base_limit * self.system_load_factor))
        
        # Standard rate limiting logic
        arr = self.buckets.setdefault(user_id, [])
        while arr and now - arr[0] > 60:
            arr.pop(0)
        
        if len(arr) >= adjusted_limit:
            self.audit_logger.warning(
                f"ADAPTIVE_RATE_LIMIT user_id={user_id} "
                f"limit={adjusted_limit} load_factor={self.system_load_factor:.2f}"
            )
            
            await self._handle_rate_limit(event, adjusted_limit)
            return
        
        arr.append(now)
        return await handler(event, data)
    
    def _get_user_id(self, event) -> int | None:
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            return event.from_user.id
        return None
    
    async def _handle_rate_limit(self, event, current_limit: int):
        message = f"⚠️ Лимит команд: {current_limit}/мин. Система под нагрузкой."
        
        try:
            if isinstance(event, Message):
                await event.answer(message)
            elif isinstance(event, CallbackQuery):
                await event.answer(message, show_alert=True)
        except Exception:
            pass
