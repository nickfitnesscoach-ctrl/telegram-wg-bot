"""
Fast authentication middleware for production
Optimized ALLOWED_USERS check with minimal overhead
"""
import logging
from typing import Callable, Dict, Any, Awaitable, Set

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from ...config.settings import settings
from ...config.logging_config import get_audit_logger


class FastAuthMiddleware(BaseMiddleware):
    """
    Fast authentication middleware for production use
    Memory-efficient ALLOWED_USERS validation
    """
    
    def __init__(self):
        # Convert to set for O(1) lookup performance
        self.allowed_users: Set[int] = set(settings.ALLOWED_USERS)
        self.audit_logger = get_audit_logger()
        self.logger = logging.getLogger(__name__)
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Fast authentication check"""
        
        # Extract user ID
        user_id = self._get_user_id(event)
        if not user_id:
            return await handler(event, data)
        
        # Fast whitelist check
        if self.allowed_users and user_id not in self.allowed_users:
            await self._handle_unauthorized(event, user_id)
            return  # Block execution
        
        # Get or create user in database
        try:
            user = await self._get_or_create_user(event)
            data['user'] = user  # Add user object for handlers
            data['authenticated_user_id'] = user_id
            
            # Log successful authentication
            self.logger.debug(f"User authenticated: {user_id} (admin: {user.is_admin if user else False})")
            
        except Exception as e:
            self.logger.error(f"Database error during auth: {e}")
            # Continue without user object
            data['authenticated_user_id'] = user_id
        
        # Continue to handler
        return await handler(event, data)
    
    def _get_user_id(self, event: TelegramObject) -> int | None:
        """Fast user ID extraction"""
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            return event.from_user.id
        elif hasattr(event, 'from_user') and event.from_user:
            return event.from_user.id
        return None
    
    async def _get_or_create_user(self, event: TelegramObject):
        """Get or create user in database from event"""
        from ...database.models import get_db_session, User
        from sqlalchemy import select
        import datetime
        
        # Extract user info
        user_info = {}
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            user_info = {
                'id': event.from_user.id,
                'username': event.from_user.username,
                'first_name': event.from_user.first_name,
                'last_name': event.from_user.last_name
            }
        
        if not user_info:
            return None
            
        async with await get_db_session() as session:
            # Try to get existing user
            result = await session.execute(
                select(User).where(User.telegram_id == user_info['id'])
            )
            user = result.scalar_one_or_none()
            
            if user:
                # Update existing user info
                user.username = user_info.get('username')
                user.first_name = user_info.get('first_name')
                user.last_name = user_info.get('last_name')
                user.last_active = datetime.datetime.utcnow()
                
                # Set admin status for first user in ALLOWED_USERS
                if self.allowed_users and user.telegram_id == list(self.allowed_users)[0]:
                    user.is_admin = True
            else:
                # Create new user
                user = User(
                    telegram_id=user_info['id'],
                    username=user_info.get('username'),
                    first_name=user_info.get('first_name'),
                    last_name=user_info.get('last_name'),
                    is_admin=(self.allowed_users and user_info['id'] == list(self.allowed_users)[0])
                )
                session.add(user)
                self.logger.info(f"Created new user: {user_info['id']} (admin: {user.is_admin})")
            
            await session.commit()
            await session.refresh(user)
            return user
    
    async def _handle_unauthorized(self, event: TelegramObject, user_id: int):
        """Handle unauthorized access efficiently"""
        
        # Log security event
        self.audit_logger.warning(f"UNAUTHORIZED_ACCESS user_id={user_id}")
        
        # Send concise denial message
        message = "🚫 Доступ только для админа."
        
        try:
            if isinstance(event, Message):
                await event.answer(message)
            elif isinstance(event, CallbackQuery):
                await event.answer(message, show_alert=True)
        except Exception as e:
            # Fail silently to prevent loops
            self.logger.debug(f"Could not send denial message: {e}")


class AllowOnly(BaseMiddleware):
    """
    Simplified authorization middleware (alternative implementation)
    Direct from user specification
    """
    
    def __init__(self):
        # Parse ALLOWED_USERS from environment
        self.allowed = {
            int(x) for x in str(settings.ALLOWED_USERS).split(",") 
            if x.strip().isdigit()
        }
        self.audit_logger = get_audit_logger()
        super().__init__()
    
    async def __call__(self, handler, event: Message, data):
        if self.allowed and event.from_user.id not in self.allowed:
            # Log unauthorized attempt
            self.audit_logger.warning(f"DENIED user_id={event.from_user.id}")
            return await event.answer("Доступ только для админа.")
        
        return await handler(event, data)


class ProductionAuth(BaseMiddleware):
    """
    Production-ready authentication with enhanced security
    """
    
    def __init__(self):
        self.allowed_users = set(settings.ALLOWED_USERS)
        self.failed_attempts: Dict[int, int] = {}
        self.audit_logger = get_audit_logger()
        super().__init__()
    
    async def __call__(self, handler, event, data):
        user_id = self._get_user_id(event)
        if not user_id:
            return await handler(event, data)
        
        # Check if user is temporarily banned (too many failed attempts)
        if self.failed_attempts.get(user_id, 0) >= 5:
            self.audit_logger.warning(f"BLOCKED_USER user_id={user_id} attempts={self.failed_attempts[user_id]}")
            await self._send_blocked_message(event)
            return
        
        # Check authorization
        if self.allowed_users and user_id not in self.allowed_users:
            # Increment failed attempts
            self.failed_attempts[user_id] = self.failed_attempts.get(user_id, 0) + 1
            
            self.audit_logger.warning(
                f"UNAUTHORIZED user_id={user_id} attempts={self.failed_attempts[user_id]}"
            )
            
            await self._send_denial_message(event, self.failed_attempts[user_id])
            return
        
        # Reset failed attempts on successful auth
        if user_id in self.failed_attempts:
            del self.failed_attempts[user_id]
        
        # Add user info and continue
        data['authenticated_user_id'] = user_id
        return await handler(event, data)
    
    def _get_user_id(self, event) -> int | None:
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            return event.from_user.id
        return None
    
    async def _send_denial_message(self, event, attempt_count: int):
        if attempt_count >= 3:
            message = f"🚫 Доступ запрещен. Попытка {attempt_count}/5."
        else:
            message = "🚫 Доступ только для админа."
        
        try:
            if isinstance(event, Message):
                await event.answer(message)
            elif isinstance(event, CallbackQuery):
                await event.answer(message, show_alert=True)
        except Exception:
            pass
    
    async def _send_blocked_message(self, event):
        message = "🚫 Заблокирован за превышение попыток доступа."
        
        try:
            if isinstance(event, Message):
                await event.answer(message)
            elif isinstance(event, CallbackQuery):
                await event.answer(message, show_alert=True)
        except Exception:
            pass


class UserValidator:
    """
    Utility class for user validation
    """
    
    @staticmethod
    def is_authorized(user_id: int) -> bool:
        """Quick authorization check"""
        return user_id in settings.ALLOWED_USERS
    
    @staticmethod
    def get_user_role(user_id: int) -> str:
        """Get user role based on position in ALLOWED_USERS"""
        if not settings.ALLOWED_USERS:
            return "unauthorized"
        
        if user_id not in settings.ALLOWED_USERS:
            return "unauthorized"
        
        # First user is admin, others are users
        if user_id == settings.ALLOWED_USERS[0]:
            return "admin"
        else:
            return "user"
    
    @staticmethod
    def validate_user_list(users_str: str) -> list[int]:
        """Validate and parse ALLOWED_USERS string"""
        if not users_str:
            return []
        
        valid_users = []
        for user_str in users_str.split(","):
            user_str = user_str.strip()
            if user_str.isdigit():
                user_id = int(user_str)
                if 100000000 <= user_id <= 9999999999:  # Valid Telegram ID range
                    valid_users.append(user_id)
        
        return valid_users


def require_auth(func: Callable) -> Callable:
    """
    Decorator for handlers that require authentication
    Usage: @require_auth
    """
    async def wrapper(message_or_query, *args, **kwargs):
        user_id = None
        
        if hasattr(message_or_query, 'from_user') and message_or_query.from_user:
            user_id = message_or_query.from_user.id
        
        if not UserValidator.is_authorized(user_id):
            audit_logger = get_audit_logger()
            audit_logger.warning(f"UNAUTHORIZED_HANDLER user_id={user_id} handler={func.__name__}")
            
            if hasattr(message_or_query, 'answer'):
                await message_or_query.answer("🚫 Доступ запрещен.")
            return
        
        return await func(message_or_query, *args, **kwargs)
    
    return wrapper


def require_admin(func: Callable) -> Callable:
    """
    Decorator for handlers that require admin privileges
    Usage: @require_admin
    """
    async def wrapper(message_or_query, *args, **kwargs):
        user_id = None
        
        if hasattr(message_or_query, 'from_user') and message_or_query.from_user:
            user_id = message_or_query.from_user.id
        
        if UserValidator.get_user_role(user_id) != "admin":
            audit_logger = get_audit_logger()
            audit_logger.warning(f"ADMIN_REQUIRED user_id={user_id} handler={func.__name__}")
            
            if hasattr(message_or_query, 'answer'):
                await message_or_query.answer("🚫 Требуются права администратора.")
            return
        
        return await func(message_or_query, *args, **kwargs)
    
    return wrapper
