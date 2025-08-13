"""
Telegram API utilities with timeouts and retry logic
Production-ready error handling for Telegram bot
"""
import asyncio
import logging
from typing import Any, Awaitable, Callable, TypeVar

from aiohttp import ClientTimeout
from aiogram.exceptions import (
    TelegramRetryAfter, 
    TelegramNetworkError, 
    TelegramBadRequest,
    TelegramUnauthorizedError,
    TelegramForbiddenError
)

T = TypeVar('T')

logger = logging.getLogger(__name__)


class TelegramTimeout:
    """Telegram API timeout configuration"""
    
    # Production timeouts
    CONNECT_TIMEOUT = 10  # Connection timeout
    TOTAL_TIMEOUT = 30    # Total request timeout
    READ_TIMEOUT = 25     # Read timeout
    
    @classmethod
    def get_client_timeout(cls) -> ClientTimeout:
        """Get optimized ClientTimeout for Telegram API"""
        return ClientTimeout(
            total=cls.TOTAL_TIMEOUT,
            connect=cls.CONNECT_TIMEOUT,
            sock_read=cls.READ_TIMEOUT
        )


async def safe_telegram_call(
    callable_func: Callable[..., Awaitable[T]], 
    *args, 
    max_retries: int = 5,
    initial_delay: float = 2.0,
    max_delay: float = 30.0,
    **kwargs
) -> T | None:
    """
    Universal wrapper for Telegram API calls with retry logic
    
    Args:
        callable_func: Async function to call (message.answer, bot.send_message, etc.)
        *args: Arguments for the function
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        **kwargs: Keyword arguments for the function
    
    Returns:
        Result of the function call or None if all retries failed
    """
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            # Execute the Telegram API call
            result = await callable_func(*args, **kwargs)
            
            # Reset delay on successful call
            if attempt > 0:
                logger.info(f"Telegram call succeeded after {attempt + 1} attempts")
            
            return result
            
        except TelegramRetryAfter as e:
            # Telegram tells us exactly how long to wait
            wait_time = e.retry_after + 1  # Add 1 second buffer
            logger.warning(f"Telegram rate limit: waiting {wait_time}s (attempt {attempt + 1})")
            await asyncio.sleep(wait_time)
            last_exception = e
            
        except TelegramNetworkError as e:
            # Network issues - exponential backoff
            logger.warning(f"Telegram network error: {e} (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)
            last_exception = e
            
        except TelegramBadRequest as e:
            # Bad request - usually permanent, don't retry
            logger.error(f"Telegram bad request: {e}")
            return None
            
        except TelegramUnauthorizedError as e:
            # Bot token issues - don't retry
            logger.error(f"Telegram unauthorized: {e}")
            return None
            
        except TelegramForbiddenError as e:
            # User blocked bot or similar - don't retry
            logger.warning(f"Telegram forbidden: {e}")
            return None
            
        except Exception as e:
            # Other unexpected errors
            logger.error(f"Unexpected error in Telegram call: {e} (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)
            last_exception = e
    
    # All retries failed
    logger.error(f"All {max_retries} Telegram call attempts failed. Last error: {last_exception}")
    return None


async def safe_send_message(message_func: Callable, text: str, **kwargs) -> bool:
    """
    Safely send message with automatic retry and error handling
    
    Args:
        message_func: Message sending function (message.answer, bot.send_message, etc.)
        text: Message text to send
        **kwargs: Additional parameters (parse_mode, reply_markup, etc.)
    
    Returns:
        True if message was sent successfully, False otherwise
    """
    result = await safe_telegram_call(message_func, text, **kwargs)
    return result is not None


async def safe_send_document(send_func: Callable, document: Any, **kwargs) -> bool:
    """
    Safely send document with retry logic
    
    Args:
        send_func: Document sending function
        document: Document to send (file, BufferedInputFile, etc.)
        **kwargs: Additional parameters
    
    Returns:
        True if document was sent successfully, False otherwise
    """
    result = await safe_telegram_call(send_func, document, **kwargs)
    return result is not None


async def safe_send_photo(send_func: Callable, photo: Any, **kwargs) -> bool:
    """
    Safely send photo with retry logic
    
    Args:
        send_func: Photo sending function
        photo: Photo to send
        **kwargs: Additional parameters
    
    Returns:
        True if photo was sent successfully, False otherwise
    """
    result = await safe_telegram_call(send_func, photo, **kwargs)
    return result is not None


class TelegramAPIMonitor:
    """Monitor Telegram API performance and issues"""
    
    def __init__(self):
        self.total_calls = 0
        self.failed_calls = 0
        self.retry_calls = 0
        self.rate_limited_calls = 0
    
    def record_call(self, success: bool, retries: int = 0, rate_limited: bool = False):
        """Record API call statistics"""
        self.total_calls += 1
        if not success:
            self.failed_calls += 1
        if retries > 0:
            self.retry_calls += 1
        if rate_limited:
            self.rate_limited_calls += 1
    
    def get_stats(self) -> dict:
        """Get API call statistics"""
        if self.total_calls == 0:
            return {
                "total_calls": 0,
                "success_rate": 100.0,
                "retry_rate": 0.0,
                "rate_limit_rate": 0.0
            }
        
        return {
            "total_calls": self.total_calls,
            "success_rate": ((self.total_calls - self.failed_calls) / self.total_calls) * 100,
            "retry_rate": (self.retry_calls / self.total_calls) * 100,
            "rate_limit_rate": (self.rate_limited_calls / self.total_calls) * 100,
            "failed_calls": self.failed_calls
        }
    
    def reset_stats(self):
        """Reset all statistics"""
        self.total_calls = 0
        self.failed_calls = 0
        self.retry_calls = 0
        self.rate_limited_calls = 0


# Global API monitor instance
telegram_monitor = TelegramAPIMonitor()


def monitor_telegram_call(func: Callable) -> Callable:
    """
    Decorator to monitor Telegram API calls
    Usage: @monitor_telegram_call
    """
    async def wrapper(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            telegram_monitor.record_call(success=True)
            return result
        except TelegramRetryAfter:
            telegram_monitor.record_call(success=False, rate_limited=True)
            raise
        except Exception:
            telegram_monitor.record_call(success=False)
            raise
    
    return wrapper


class BulkMessageSender:
    """
    Efficiently send messages to multiple users with rate limiting
    """
    
    def __init__(self, delay_between_messages: float = 0.1):
        self.delay = delay_between_messages
    
    async def send_to_users(
        self, 
        bot, 
        user_ids: list[int], 
        message_text: str,
        **kwargs
    ) -> tuple[int, int]:
        """
        Send message to multiple users
        
        Returns:
            Tuple of (successful_sends, failed_sends)
        """
        successful = 0
        failed = 0
        
        for user_id in user_ids:
            try:
                success = await safe_send_message(
                    bot.send_message,
                    chat_id=user_id,
                    text=message_text,
                    **kwargs
                )
                
                if success:
                    successful += 1
                else:
                    failed += 1
                
                # Small delay to avoid rate limiting
                if self.delay > 0:
                    await asyncio.sleep(self.delay)
                    
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id}: {e}")
                failed += 1
        
        return successful, failed


# Utility functions for common operations
async def try_delete_message(message, delay: float = 0) -> bool:
    """Safely try to delete a message"""
    try:
        if delay > 0:
            await asyncio.sleep(delay)
        await message.delete()
        return True
    except Exception as e:
        logger.debug(f"Could not delete message: {e}")
        return False


async def try_edit_message(message, new_text: str, **kwargs) -> bool:
    """Safely try to edit a message"""
    result = await safe_telegram_call(message.edit_text, new_text, **kwargs)
    return result is not None


async def try_answer_callback(callback_query, text: str = None, **kwargs) -> bool:
    """Safely try to answer a callback query"""
    result = await safe_telegram_call(callback_query.answer, text, **kwargs)
    return result is not None
