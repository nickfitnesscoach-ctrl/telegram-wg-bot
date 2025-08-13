"""
Pytest configuration and fixtures for Telegram WireGuard Bot tests
"""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, User, VPNClient
from src.config.settings import Settings


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db():
    """Create test database"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    yield async_session
    
    await engine.dispose()


@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    settings = Settings()
    settings.BOT_TOKEN = "test_token"
    settings.ALLOWED_USERS = [12345, 67890]
    settings.MAX_CLIENTS = 10
    settings.COMMAND_TIMEOUT = 30
    return settings


@pytest.fixture
def mock_user():
    """Create mock user for testing"""
    return User(
        id=1,
        telegram_id=12345,
        username="testuser",
        first_name="Test",
        last_name="User",
        is_admin=True,
        is_active=True
    )


@pytest.fixture
def mock_vpn_client():
    """Create mock VPN client for testing"""
    return VPNClient(
        id=1,
        name="test_client",
        user_id=1,
        public_key="test_public_key",
        private_key="test_private_key",
        ip_address="10.0.0.2",
        is_active=True
    )


@pytest.fixture
def mock_message():
    """Create mock Telegram message"""
    message = AsyncMock()
    message.from_user.id = 12345
    message.from_user.username = "testuser"
    message.from_user.first_name = "Test"
    message.text = "/start"
    message.answer = AsyncMock()
    return message


@pytest.fixture
def mock_wg_manager():
    """Create mock WireGuard manager"""
    wg_manager = AsyncMock()
    wg_manager.add_client = AsyncMock(return_value=(True, "Success", {"name": "test"}))
    wg_manager.list_clients = AsyncMock(return_value=[{"name": "test", "ip": "10.0.0.2"}])
    wg_manager._execute_wg_command = AsyncMock(return_value=(True, "Success"))
    return wg_manager
