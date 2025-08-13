"""
Database models for Telegram WireGuard Bot
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Text, 
    ForeignKey, UniqueConstraint, Index, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import relationship, sessionmaker

from ..config.settings import settings

# Base class for all models
Base = declarative_base()


class User(Base):
    """User model for storing Telegram user information"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_active = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    clients = relationship("VPNClient", back_populates="user", cascade="all, delete-orphan")
    command_logs = relationship("CommandLog", back_populates="user", cascade="all, delete-orphan")
    rate_limits = relationship("RateLimit", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<User(telegram_id={self.telegram_id}, username={self.username})>"


class VPNClient(Base):
    """VPN client configuration model"""
    __tablename__ = 'vpn_clients'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # WireGuard specific fields
    public_key = Column(Text, nullable=False)
    private_key = Column(Text, nullable=False)  # Encrypted with DataEncryption
    ip_address = Column(String(45), nullable=False)  # IPv4/IPv6
    
    # Status and metadata
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_connected = Column(DateTime, nullable=True)
    
    # Statistics
    bytes_sent = Column(Integer, default=0, nullable=False)
    bytes_received = Column(Integer, default=0, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="clients")
    
    __table_args__ = (
        Index('idx_vpn_client_user_active', 'user_id', 'is_active'),
    )
    
    def __repr__(self) -> str:
        return f"<VPNClient(name={self.name}, ip={self.ip_address})>"


class CommandLog(Base):
    """Command execution log for audit purposes"""
    __tablename__ = 'command_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Command details
    command = Column(String(100), nullable=False)
    arguments = Column(Text, nullable=True)
    status = Column(String(50), nullable=False)  # success, error, timeout
    
    # Execution details
    execution_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ip_address = Column(String(45), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="command_logs")
    
    __table_args__ = (
        Index('idx_command_log_user_time', 'user_id', 'created_at'),
        Index('idx_command_log_command', 'command'),
    )
    
    def __repr__(self) -> str:
        return f"<CommandLog(command={self.command}, status={self.status})>"


class RateLimit(Base):
    """Rate limiting tracking per user"""
    __tablename__ = 'rate_limits'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Rate limiting data
    window_start = Column(DateTime, nullable=False)
    command_count = Column(Integer, default=1, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="rate_limits")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'window_start', name='unique_user_window'),
        Index('idx_rate_limit_window', 'window_start'),
    )
    
    def __repr__(self) -> str:
        return f"<RateLimit(user_id={self.user_id}, count={self.command_count})>"


class SystemStatus(Base):
    """System status and health monitoring"""
    __tablename__ = 'system_status'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # System metrics
    wireguard_status = Column(String(50), nullable=False)  # active, inactive, error
    active_clients = Column(Integer, default=0, nullable=False)
    total_clients = Column(Integer, default=0, nullable=False)
    
    # Resource usage
    disk_usage_gb = Column(Integer, nullable=True)
    memory_usage_mb = Column(Integer, nullable=True)
    cpu_usage_percent = Column(Integer, nullable=True)
    
    # Network statistics
    bytes_sent_total = Column(Integer, default=0, nullable=False)
    bytes_received_total = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_system_status_time', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<SystemStatus(wg_status={self.wireguard_status}, clients={self.active_clients})>"


class BackupRecord(Base):
    """Backup operations tracking"""
    __tablename__ = 'backup_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Backup details
    backup_type = Column(String(50), nullable=False)  # manual, auto, pre_operation
    file_path = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    
    # Status
    status = Column(String(50), nullable=False)  # success, error, in_progress
    error_message = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_backup_type_time', 'backup_type', 'created_at'),
        Index('idx_backup_expires', 'expires_at'),
    )
    
    def __repr__(self) -> str:
        return f"<BackupRecord(type={self.backup_type}, status={self.status})>"


# Database engine and session management
class DatabaseManager:
    """Database connection and session management"""
    
    def __init__(self):
        self.engine = None
        self.async_session_factory = None
        
    async def init_database(self) -> None:
        """Initialize database connection and create tables"""
        # Create async engine
        self.engine = create_async_engine(
            settings.DATABASE_URL.replace('sqlite:///', 'sqlite+aiosqlite:///'),
            echo=False,  # Set to True for SQL debugging
            future=True
        )
        
        # Create session factory
        self.async_session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Create all tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def get_session(self) -> AsyncSession:
        """Get database session"""
        if not self.async_session_factory:
            await self.init_database()
        
        return self.async_session_factory()
    
    async def close(self) -> None:
        """Close database connection"""
        if self.engine:
            await self.engine.dispose()


# Global database manager instance
db_manager = DatabaseManager()


async def init_database() -> None:
    """Initialize database - called from main.py"""
    await db_manager.init_database()


async def get_db_session() -> AsyncSession:
    """Get database session - used throughout the application"""
    return await db_manager.get_session()


async def close_database() -> None:
    """Close database connection - called during shutdown"""
    await db_manager.close()