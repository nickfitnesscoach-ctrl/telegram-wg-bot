import os
import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select

ALLOWED = {int(x) for x in os.getenv("ALLOWED_USERS","").split(",") if x.strip().isdigit()}

class AllowOnly(BaseMiddleware):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    async def __call__(self, handler, event, data):
        # Get user ID from event
        user_id = None
        if hasattr(event, 'from_user') and event.from_user:
            user_id = event.from_user.id
        
        if not user_id:
            return await handler(event, data)
            
        # Check if user is allowed
        if ALLOWED and user_id not in ALLOWED:
            if hasattr(event, 'answer'):
                return await event.answer("Доступ только для админа.")
            return
        
        # Create user object for admin handlers compatibility
        try:
            user = await self._get_or_create_user(event)
            data['user'] = user
            data['authenticated_user_id'] = user_id
        except Exception as e:
            self.logger.error(f"Database error during auth: {e}")
            data['authenticated_user_id'] = user_id
            
        return await handler(event, data)
    
    async def _get_or_create_user(self, event):
        """Get or create user from database"""
        from ...database.models import get_db_session, User
        import datetime

        user_info = {}
        if hasattr(event, 'from_user') and event.from_user:
            user_info = {
                'id': event.from_user.id,
                'username': event.from_user.username,
                'first_name': event.from_user.first_name,
                'last_name': event.from_user.last_name
            }
        
        if not user_info:
            return None

        async with await get_db_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_info['id'])
            )
            user = result.scalar_one_or_none()

            if user:
                # Update user info
                user.username = user_info.get('username')
                user.first_name = user_info.get('first_name')
                user.last_name = user_info.get('last_name')
                user.last_active = datetime.datetime.utcnow()
                # Set admin flag for allowed users
                if ALLOWED and user.telegram_id in ALLOWED:
                    user.is_admin = True
            else:
                # Create new user
                user = User(
                    telegram_id=user_info['id'],
                    username=user_info.get('username'),
                    first_name=user_info.get('first_name'),
                    last_name=user_info.get('last_name'),
                    is_admin=(ALLOWED and user_info['id'] in ALLOWED)
                )
                session.add(user)
                self.logger.info(f"Created new user: {user_info['id']} (admin: {user.is_admin})")

            await session.commit()
            await session.refresh(user)
            return user
