"""
Unit tests for authentication middleware
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.bot.middlewares.auth import AuthMiddleware, AuthHelper
from src.database.models import User


class TestAuthMiddleware:
    """Test cases for AuthMiddleware"""
    
    @pytest.fixture
    def auth_middleware(self, mock_settings):
        """Create AuthMiddleware instance"""
        with patch('src.bot.middlewares.auth.settings', mock_settings):
            return AuthMiddleware()
    
    def test_extract_user_info_from_message(self, auth_middleware, mock_message):
        """Test user info extraction from message"""
        user_info = auth_middleware._extract_user_info(mock_message)
        
        assert user_info is not None
        assert user_info['id'] == 12345
        assert user_info['username'] == 'testuser'
        assert user_info['first_name'] == 'Test'
    
    def test_is_authorized_valid_user(self, auth_middleware, mock_settings):
        """Test authorization for valid user"""
        with patch('src.bot.middlewares.auth.settings', mock_settings):
            assert auth_middleware._is_authorized(12345) is True
            assert auth_middleware._is_authorized(67890) is True
    
    def test_is_authorized_invalid_user(self, auth_middleware, mock_settings):
        """Test authorization for invalid user"""
        with patch('src.bot.middlewares.auth.settings', mock_settings):
            assert auth_middleware._is_authorized(99999) is False
            assert auth_middleware._is_authorized(None) is False
    
    @pytest.mark.asyncio
    async def test_handle_unauthorized_access(self, auth_middleware, mock_message):
        """Test unauthorized access handling"""
        await auth_middleware._handle_unauthorized_access(mock_message, 99999, "unknown")
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Доступ запрещен" in call_args
    
    @pytest.mark.asyncio
    async def test_successful_auth_flow(self, auth_middleware, mock_message, mock_user):
        """Test successful authentication flow"""
        handler = AsyncMock()
        data = {}
        
        with patch.object(auth_middleware, '_get_or_create_user', return_value=mock_user):
            with patch.object(auth_middleware, '_is_authorized', return_value=True):
                await auth_middleware(handler, mock_message, data)
        
        handler.assert_called_once()
        assert 'user' in data
        assert data['user'] == mock_user


class TestAuthHelper:
    """Test cases for AuthHelper"""
    
    @pytest.mark.asyncio
    async def test_is_user_authorized(self, mock_settings):
        """Test user authorization check"""
        with patch('src.bot.middlewares.auth.settings', mock_settings):
            assert await AuthHelper.is_user_authorized(12345) is True
            assert await AuthHelper.is_user_authorized(99999) is False
    
    @pytest.mark.asyncio
    async def test_is_user_admin(self, mock_user):
        """Test admin check"""
        with patch('src.bot.middlewares.auth.get_db_session') as mock_session:
            mock_session.return_value.__aenter__.return_value.execute.return_value.scalar_one_or_none.return_value = mock_user
            
            result = await AuthHelper.is_user_admin(12345)
            assert result is True
    
    @pytest.mark.asyncio
    async def test_get_user_by_telegram_id(self, mock_user):
        """Test user retrieval by Telegram ID"""
        with patch('src.bot.middlewares.auth.get_db_session') as mock_session:
            mock_session.return_value.__aenter__.return_value.execute.return_value.scalar_one_or_none.return_value = mock_user
            
            result = await AuthHelper.get_user_by_telegram_id(12345)
            assert result == mock_user
