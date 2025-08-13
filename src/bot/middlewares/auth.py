"""
Authentication middleware for Telegram WireGuard Bot
"""
import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, Message, CallbackQuery

from ...config.settings import settings
from ...config.logging_config import get_audit_logger
from ...database.models import get_db_session, User


class AuthMiddleware(BaseMiddleware):
    """
    Authentication middleware to check user permissions
    Implements whitelist-based authorization from TZ section 2
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
        
        # Extract user info from different event types
        user_info = self._extract_user_info(event)
        
        if not user_info:
            # No user info available, skip middleware
            return await handler(event, data)
        
        telegram_id = user_info.get('id')
        username = user_info.get('username', 'unknown')
        
        # Check if user is in whitelist (from TZ section 3.1)
        if not self._is_authorized(telegram_id):
            await self._handle_unauthorized_access(event, telegram_id, username)
            return  # Block further processing
        
        # Get or create user in database
        try:
            user = await self._get_or_create_user(user_info)
            data['user'] = user  # Add user to handler data
            
            # Log authorized access
            self.audit_logger.info(
                f"Authorized access | user_id={telegram_id} | "
                f"username={username} | is_admin={user.is_admin}"
            )
            
        except Exception as e:
            self.logger.error(f"Database error during auth: {e}")
            await self._handle_database_error(event)
            return
        
        # Continue to next middleware/handler
        return await handler(event, data)
    
    def _extract_user_info(self, event: TelegramObject) -> Dict[str, Any] | None:
        """Extract user information from different event types"""
        user = None
        
        if isinstance(event, Message) and event.from_user:
            user = event.from_user
        elif isinstance(event, CallbackQuery) and event.from_user:
            user = event.from_user
        elif hasattr(event, 'from_user') and event.from_user:
            user = event.from_user
        
        if user:
            return {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_bot': user.is_bot
            }
        
        return None
    
    def _is_authorized(self, telegram_id: int) -> bool:
        """
        Check if user is in whitelist
        Implements TZ requirement: "Whitelist Telegram ID (жестко зашитый список)"
        """
        if not telegram_id:
            return False
        
        # Check against ALLOWED_USERS from settings
        return telegram_id in settings.ALLOWED_USERS
    
    async def _get_or_create_user(self, user_info: Dict[str, Any]) -> User:
        """Get existing user or create new one in database"""
        async with await get_db_session() as session:
            # Try to find existing user
            from sqlalchemy import select
            
            result = await session.execute(
                select(User).where(User.telegram_id == user_info['id'])
            )
            user = result.scalar_one_or_none()
            
            if user:
                # Update user info and last active time
                user.username = user_info.get('username')
                user.first_name = user_info.get('first_name')
                user.last_name = user_info.get('last_name')
                user.last_active = __import__('datetime').datetime.utcnow()
                
                # Check if user should be admin (if in first position of ALLOWED_USERS)
                if settings.ALLOWED_USERS and user.telegram_id == settings.ALLOWED_USERS[0]:
                    user.is_admin = True
                
            else:
                # Create new user
                user = User(
                    telegram_id=user_info['id'],
                    username=user_info.get('username'),
                    first_name=user_info.get('first_name'),
                    last_name=user_info.get('last_name'),
                    is_admin=(
                        settings.ALLOWED_USERS and 
                        user_info['id'] == settings.ALLOWED_USERS[0]
                    )  # First user in list is admin
                )
                session.add(user)
                
                self.logger.info(f"Created new user: {user_info['id']} ({user_info.get('username')})")
            
            await session.commit()
            await session.refresh(user)
            return user
    
    async def _handle_unauthorized_access(
        self, 
        event: TelegramObject, 
        telegram_id: int, 
        username: str
    ) -> None:
        """Handle unauthorized access attempt"""
        
        # Log security event
        self.audit_logger.warning(
            f"UNAUTHORIZED ACCESS ATTEMPT | user_id={telegram_id} | "
            f"username={username} | allowed_users={settings.ALLOWED_USERS}"
        )
        
        # Send denial message if it's a message event
        if isinstance(event, Message):
            try:
                await event.answer(
                    "🚫 <b>Доступ запрещен</b>\n\n"
                    "У вас нет прав для использования этого бота.\n"
                    "Обратитесь к администратору для получения доступа.",
                    parse_mode="HTML"
                )
            except Exception as e:
                self.logger.error(f"Failed to send denial message: {e}")
        
        elif isinstance(event, CallbackQuery):
            try:
                await event.answer("🚫 Доступ запрещен", show_alert=True)
            except Exception as e:
                self.logger.error(f"Failed to answer callback query: {e}")
    
    async def _handle_database_error(self, event: TelegramObject) -> None:
        """Handle database errors during authentication"""
        
        self.logger.error("Database error during authentication")
        
        # Send error message if possible
        if isinstance(event, Message):
            try:
                await event.answer(
                    "⚠️ <b>Временная ошибка</b>\n\n"
                    "Произошла ошибка при обработке запроса.\n"
                    "Попробуйте позже.",
                    parse_mode="HTML"
                )
            except Exception as e:
                self.logger.error(f"Failed to send error message: {e}")


def require_admin(func: Callable) -> Callable:
    """
    Decorator for handlers that require admin privileges
    Usage: @require_admin
    """
    async def wrapper(message_or_query, *args, **kwargs):
        # Get user from middleware data
        user = kwargs.get('user') or getattr(message_or_query, 'user', None)
        
        if not user or not user.is_admin:
            # User is not admin
            audit_logger = get_audit_logger()
            audit_logger.warning(
                f"Admin access denied | user_id={getattr(user, 'telegram_id', 'unknown')} | "
                f"handler={func.__name__}"
            )
            
            if hasattr(message_or_query, 'answer'):
                await message_or_query.answer(
                    "🚫 <b>Недостаточно прав</b>\n\n"
                    "Эта команда доступна только администраторам.",
                    parse_mode="HTML"
                )
            return
        
        # User is admin, proceed with handler
        return await func(message_or_query, *args, **kwargs)
    
    return wrapper


class AuthHelper:
    """Helper class for authentication checks"""
    
    @staticmethod
    async def is_user_authorized(telegram_id: int) -> bool:
        """Check if user is authorized (in whitelist)"""
        return telegram_id in settings.ALLOWED_USERS
    
    @staticmethod
    async def is_user_admin(telegram_id: int) -> bool:
        """Check if user is admin"""
        try:
            async with await get_db_session() as session:
                from sqlalchemy import select
                
                result = await session.execute(
                    select(User).where(
                        User.telegram_id == telegram_id,
                        User.is_admin == True,
                        User.is_active == True
                    )
                )
                user = result.scalar_one_or_none()
                return user is not None
                
        except Exception:
            return False
    
    @staticmethod
    async def get_user_by_telegram_id(telegram_id: int) -> User | None:
        """Get user by Telegram ID"""
        try:
            async with await get_db_session() as session:
                from sqlalchemy import select
                
                result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                return result.scalar_one_or_none()
                
        except Exception:
            return None
