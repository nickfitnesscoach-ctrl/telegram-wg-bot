"""
Database repository for Telegram WireGuard Bot
"""
import logging
from typing import List, Optional
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User, VPNClient, CommandLog, RateLimit, SystemStatus, BackupRecord


class UserRepository:
    """Repository for User operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = logging.getLogger(__name__)
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID"""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    async def create_user(self, telegram_id: int, username: str = None, 
                         first_name: str = None, last_name: str = None,
                         is_admin: bool = False) -> User:
        """Create new user"""
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            is_admin=is_admin
        )
        
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        
        return user
    
    async def update_last_active(self, user_id: int) -> None:
        """Update user's last active timestamp"""
        from datetime import datetime
        
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_active=datetime.utcnow())
        )
        await self.session.commit()


class VPNClientRepository:
    """Repository for VPN Client operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = logging.getLogger(__name__)
    
    async def create_client(self, user_id: int, name: str, ip_address: str,
                           public_key: str, private_key: str) -> VPNClient:
        """Create new VPN client"""
        client = VPNClient(
            user_id=user_id,
            name=name,
            ip_address=ip_address,
            public_key=public_key,
            private_key=private_key
        )
        
        self.session.add(client)
        await self.session.commit()
        await self.session.refresh(client)
        
        return client
    
    async def get_by_name(self, name: str) -> Optional[VPNClient]:
        """Get client by name"""
        result = await self.session.execute(
            select(VPNClient).where(VPNClient.name == name)
        )
        return result.scalar_one_or_none()
    
    async def delete_by_name(self, name: str) -> bool:
        """Delete client by name"""
        result = await self.session.execute(
            delete(VPNClient).where(VPNClient.name == name)
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def list_by_user(self, user_id: int) -> List[VPNClient]:
        """List clients by user"""
        result = await self.session.execute(
            select(VPNClient).where(VPNClient.user_id == user_id)
        )
        return list(result.scalars().all())
    
    async def count_total(self) -> int:
        """Count total clients"""
        result = await self.session.execute(
            select(VPNClient)
        )
        return len(list(result.scalars().all()))


