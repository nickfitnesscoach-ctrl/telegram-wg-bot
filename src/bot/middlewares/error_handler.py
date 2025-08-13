"""
Global error handling middleware with secure logging
Production-ready error handling for Telegram bot
"""
import logging
import re
import traceback
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, Message, CallbackQuery
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramUnauthorizedError,
    TelegramNetworkError,
    TelegramRetryAfter
)

from ...config.logging_config import get_audit_logger


class SecretFilter(logging.Filter):
    """
    Filter to remove sensitive information from logs
    Prevents token leaks and PII exposure
    """
    
    # Patterns to sanitize
    PATTERNS = [
        # Bot tokens (format: 123456789:ABC-DEF...)
        (r'\b\d{8,10}:[A-Za-z0-9_\-]{35,}\b', '[BOT_TOKEN]'),
        # API keys
        (r'\bapi[_\-]?key["\s]*[:=]["\s]*[A-Za-z0-9_\-]{20,}\b', 'api_key=[API_KEY]'),
        # Telegram user IDs (when sensitive)
        (r'\buser[_\-]?id["\s]*[:=]["\s]*\d{8,12}\b', 'user_id=[USER_ID]'),
        # Passwords and secrets
        (r'\b(password|secret|token)["\s]*[:=]["\s]*[^\s"]{8,}\b', r'\1=[HIDDEN]'),
        # Private keys
        (r'-----BEGIN [A-Z\s]+ PRIVATE KEY-----.*?-----END [A-Z\s]+ PRIVATE KEY-----', '[PRIVATE_KEY]'),
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Clean sensitive data from log records"""
        try:
            # Convert message to string
            msg = str(record.msg)
            
            # Apply all sanitization patterns
            for pattern, replacement in self.PATTERNS:
                msg = re.sub(pattern, replacement, msg, flags=re.IGNORECASE | re.DOTALL)
            
            # Update the record
            record.msg = msg
            
            # Also clean args if present
            if record.args:
                clean_args = []
                for arg in record.args:
                    clean_arg = str(arg)
                    for pattern, replacement in self.PATTERNS:
                        clean_arg = re.sub(pattern, replacement, clean_arg, flags=re.IGNORECASE | re.DOTALL)
                    clean_args.append(clean_arg)
                record.args = tuple(clean_args)
            
            return True
            
        except Exception:
            # If sanitization fails, still log but mark as potentially unsafe
            record.msg = f"[LOG_SANITIZATION_FAILED] {record.msg}"
            return True


class GlobalErrorHandler(BaseMiddleware):
    """
    Global error handling middleware for unhandled exceptions
    Provides graceful error recovery and user feedback
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.audit_logger = get_audit_logger()
        
        # Install secret filter on all loggers
        self._install_secret_filter()
        super().__init__()
    
    def _install_secret_filter(self):
        """Install SecretFilter on all active loggers"""
        secret_filter = SecretFilter()
        
        # Add to root logger
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            handler.addFilter(secret_filter)
        
        # Add to specific loggers
        for logger_name in ['aiogram', 'aiohttp', 'telegram']:
            logger = logging.getLogger(logger_name)
            for handler in logger.handlers:
                handler.addFilter(secret_filter)
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Main error handling wrapper"""
        
        try:
            # Execute the handler
            return await handler(event, data)
            
        except TelegramUnauthorizedError as e:
            # Bot token issues - critical error
            self.audit_logger.critical(f"BOT_UNAUTHORIZED: {e}")
            await self._handle_unauthorized_error(event, e)
            
        except TelegramForbiddenError as e:
            # User blocked bot or chat restrictions
            self.audit_logger.warning(f"TELEGRAM_FORBIDDEN: {e}")
            await self._handle_forbidden_error(event, e)
            
        except TelegramBadRequest as e:
            # Invalid request - usually a bug
            self.audit_logger.error(f"TELEGRAM_BAD_REQUEST: {e}")
            await self._handle_bad_request_error(event, e)
            
        except TelegramRetryAfter as e:
            # Rate limiting from Telegram
            self.audit_logger.warning(f"TELEGRAM_RATE_LIMIT: retry_after={e.retry_after}")
            await self._handle_rate_limit_error(event, e)
            
        except TelegramNetworkError as e:
            # Network connectivity issues
            self.audit_logger.warning(f"TELEGRAM_NETWORK_ERROR: {e}")
            await self._handle_network_error(event, e)
            
        except TelegramAPIError as e:
            # Other Telegram API errors
            self.audit_logger.error(f"TELEGRAM_API_ERROR: {e}")
            await self._handle_api_error(event, e)
            
        except Exception as e:
            # Unexpected application errors
            self.audit_logger.error(f"UNHANDLED_ERROR: {e}")
            self.logger.exception("Unhandled exception in bot")
            await self._handle_unexpected_error(event, e)
    
    async def _handle_unauthorized_error(self, event: TelegramObject, error: Exception):
        """Handle bot authorization errors"""
        # This is critical - bot token is invalid
        self.logger.critical("Bot token is invalid or revoked!")
        # Cannot send messages with invalid token
    
    async def _handle_forbidden_error(self, event: TelegramObject, error: Exception):
        """Handle forbidden errors (user blocked bot, etc.)"""
        # Log for analytics but don't try to respond
        user_id = self._get_user_id(event)
        if user_id:
            self.audit_logger.info(f"User {user_id} blocked bot or chat is restricted")
    
    async def _handle_bad_request_error(self, event: TelegramObject, error: Exception):
        """Handle bad request errors"""
        await self._send_safe_error_message(
            event,
            "⚠️ Произошла ошибка при обработке команды. Попробуйте еще раз."
        )
    
    async def _handle_rate_limit_error(self, event: TelegramObject, error: TelegramRetryAfter):
        """Handle Telegram rate limiting"""
        await self._send_safe_error_message(
            event,
            f"⏱️ Бот временно ограничен Telegram. Попробуйте через {error.retry_after} секунд."
        )
    
    async def _handle_network_error(self, event: TelegramObject, error: Exception):
        """Handle network connectivity errors"""
        await self._send_safe_error_message(
            event,
            "🌐 Проблемы с сетью. Попробуйте позже."
        )
    
    async def _handle_api_error(self, event: TelegramObject, error: Exception):
        """Handle other Telegram API errors"""
        await self._send_safe_error_message(
            event,
            "🤖 Ошибка Telegram API. Команда не выполнена."
        )
    
    async def _handle_unexpected_error(self, event: TelegramObject, error: Exception):
        """Handle unexpected application errors"""
        await self._send_safe_error_message(
            event,
            "❌ Внутренняя ошибка. Администратор уведомлен."
        )
    
    async def _send_safe_error_message(self, event: TelegramObject, message: str):
        """Safely send error message to user"""
        try:
            if isinstance(event, Message):
                await event.answer(message)
            elif isinstance(event, CallbackQuery):
                await event.answer(message, show_alert=True)
        except Exception as e:
            # If we can't even send error message, just log it
            self.logger.error(f"Could not send error message: {e}")
    
    def _get_user_id(self, event: TelegramObject) -> int | None:
        """Extract user ID from event"""
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            return event.from_user.id
        elif hasattr(event, 'from_user') and event.from_user:
            return event.from_user.id
        return None


class ErrorReporter:
    """
    Error reporting system for production monitoring
    """
    
    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.audit_logger = get_audit_logger()
    
    def report_error(self, error_type: str, error_message: str, user_id: int = None):
        """Report error for monitoring and analytics"""
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        self.audit_logger.error(
            f"ERROR_REPORT type={error_type} count={self.error_counts[error_type]} "
            f"user_id={user_id} message={error_message}"
        )
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics for monitoring"""
        total_errors = sum(self.error_counts.values())
        return {
            "total_errors": total_errors,
            "error_types": dict(self.error_counts),
            "most_common_error": max(self.error_counts.items(), key=lambda x: x[1])[0] if self.error_counts else None
        }
    
    def reset_stats(self):
        """Reset error statistics"""
        self.error_counts.clear()


# Global error reporter instance
error_reporter = ErrorReporter()


def setup_secure_logging():
    """
    Setup secure logging configuration with secret filtering
    Call this during application initialization
    """
    # Create secret filter
    secret_filter = SecretFilter()
    
    # Configure root logger
    root_logger = logging.getLogger()
    
    # Add filter to all existing handlers
    for handler in root_logger.handlers:
        handler.addFilter(secret_filter)
    
    # Configure specific logger levels
    logging.getLogger('aiogram').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Add audit logger with secret filter
    audit_logger = get_audit_logger()
    for handler in audit_logger.handlers:
        handler.addFilter(secret_filter)


def log_safe(logger: logging.Logger, level: int, message: str, *args, **kwargs):
    """
    Safe logging function that automatically sanitizes sensitive data
    """
    secret_filter = SecretFilter()
    
    # Create temporary log record for sanitization
    record = logging.LogRecord(
        name=logger.name,
        level=level,
        pathname="",
        lineno=0,
        msg=message,
        args=args,
        exc_info=None
    )
    
    # Apply secret filter
    secret_filter.filter(record)
    
    # Log the sanitized message
    logger.log(level, record.msg, *record.args, **kwargs)


# Convenience functions for safe logging
def log_safe_info(logger: logging.Logger, message: str, *args, **kwargs):
    """Safe info logging"""
    log_safe(logger, logging.INFO, message, *args, **kwargs)


def log_safe_error(logger: logging.Logger, message: str, *args, **kwargs):
    """Safe error logging"""
    log_safe(logger, logging.ERROR, message, *args, **kwargs)


def log_safe_warning(logger: logging.Logger, message: str, *args, **kwargs):
    """Safe warning logging"""
    log_safe(logger, logging.WARNING, message, *args, **kwargs)
