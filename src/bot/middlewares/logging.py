"""
Logging middleware for Telegram WireGuard Bot
"""
import logging
import time
from datetime import datetime
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, Update

from ...config.logging_config import structured_logger, get_performance_logger
from ...database.models import get_db_session, CommandLog


class LoggingMiddleware(BaseMiddleware):
    """
    Logging middleware for request/response tracking and performance monitoring
    Implements TZ requirement: "Логирование всех операций с пользователем и результатами"
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.perf_logger = get_performance_logger()
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Main middleware handler"""
        
        # Record start time for performance measurement
        start_time = time.time()
        
        # Extract request info
        request_info = self._extract_request_info(event, data)
        
        # Log incoming request
        self._log_incoming_request(request_info)
        
        # Execute handler and measure performance
        error = None
        result = None
        
        try:
            result = await handler(event, data)
            
        except Exception as e:
            error = e
            self.logger.error(
                f"Handler error | user_id={request_info.get('user_id')} | "
                f"command={request_info.get('command')} | error={str(e)}"
            )
            raise  # Re-raise the exception
            
        finally:
            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000
            
            # Log request completion
            await self._log_request_completion(
                request_info, 
                execution_time_ms, 
                error,
                result
            )
        
        return result
    
    def _extract_request_info(self, event: TelegramObject, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract request information for logging"""
        info = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': type(event).__name__,
            'user_id': None,
            'username': None,
            'command': None,
            'arguments': None,
            'message_id': None,
            'chat_id': None,
            'chat_type': None
        }
        
        # Get user info from auth middleware
        user = data.get('user')
        if user:
            info['user_id'] = user.telegram_id
            info['username'] = user.username
        
        # Extract message/callback specific info
        if isinstance(event, Message):
            info.update(self._extract_message_info(event))
        elif isinstance(event, CallbackQuery):
            info.update(self._extract_callback_info(event))
        
        return info
    
    def _extract_message_info(self, message: Message) -> Dict[str, Any]:
        """Extract information from message"""
        info = {
            'message_id': message.message_id,
            'chat_id': message.chat.id,
            'chat_type': message.chat.type,
        }
        
        # Extract command and arguments
        if message.text:
            text_parts = message.text.strip().split()
            if text_parts and text_parts[0].startswith('/'):
                info['command'] = text_parts[0]
                if len(text_parts) > 1:
                    info['arguments'] = ' '.join(text_parts[1:])
            else:
                info['command'] = 'text_message'
                info['arguments'] = message.text[:100]  # First 100 chars
        
        return info
    
    def _extract_callback_info(self, callback: CallbackQuery) -> Dict[str, Any]:
        """Extract information from callback query"""
        info = {
            'command': 'callback_query',
            'arguments': callback.data,
            'message_id': callback.message.message_id if callback.message else None,
            'chat_id': callback.message.chat.id if callback.message else None,
            'chat_type': callback.message.chat.type if callback.message else None,
        }
        
        return info
    
    def _log_incoming_request(self, request_info: Dict[str, Any]) -> None:
        """Log incoming request"""
        structured_logger.log_user_action(
            user_id=request_info.get('user_id', 0),
            action='incoming_request',
            command=request_info.get('command'),
            arguments=request_info.get('arguments'),
            event_type=request_info.get('event_type'),
            chat_id=request_info.get('chat_id'),
            chat_type=request_info.get('chat_type')
        )
    
    async def _log_request_completion(
        self, 
        request_info: Dict[str, Any], 
        execution_time_ms: float,
        error: Exception = None,
        result: Any = None
    ) -> None:
        """Log request completion with performance metrics"""
        
        status = 'error' if error else 'success'
        
        # Log performance metrics
        self.perf_logger.info(
            f"operation={request_info.get('command', 'unknown')} | "
            f"duration_ms={execution_time_ms:.2f} | "
            f"user_id={request_info.get('user_id')} | "
            f"status={status}"
        )
        
        # Log structured completion
        structured_logger.log_user_action(
            user_id=request_info.get('user_id', 0),
            action='request_completed',
            command=request_info.get('command'),
            status=status,
            execution_time_ms=round(execution_time_ms, 2),
            error=str(error) if error else None
        )
        
        # Store in database for audit
        await self._store_command_log(request_info, execution_time_ms, error)
        
        # Log slow operations
        if execution_time_ms > 5000:  # > 5 seconds
            self.logger.warning(
                f"Slow operation detected | command={request_info.get('command')} | "
                f"duration={execution_time_ms:.2f}ms | user_id={request_info.get('user_id')}"
            )
    
    async def _store_command_log(
        self, 
        request_info: Dict[str, Any], 
        execution_time_ms: float,
        error: Exception = None
    ) -> None:
        """Store command log in database"""
        
        # Skip logging for non-command events
        command = request_info.get('command')
        if not command or command in ['text_message', 'callback_query']:
            return
        
        # Get user from request info
        user_id = request_info.get('user_id')
        if not user_id:
            return
        
        try:
            async with await get_db_session() as session:
                # Find user in database
                from sqlalchemy import select
                from ...database.models import User
                
                result = await session.execute(
                    select(User).where(User.telegram_id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if user:
                    # Create command log entry
                    command_log = CommandLog(
                        user_id=user.id,
                        command=command,
                        arguments=request_info.get('arguments'),
                        status='error' if error else 'success',
                        execution_time_ms=int(execution_time_ms),
                        error_message=str(error) if error else None
                    )
                    
                    session.add(command_log)
                    await session.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to store command log: {e}")


class PerformanceMonitor:
    """Performance monitoring helper"""
    
    def __init__(self, operation_name: str, user_id: int = None):
        self.operation_name = operation_name
        self.user_id = user_id
        self.start_time = None
        self.logger = get_performance_logger()
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (time.time() - self.start_time) * 1000
            
            status = 'error' if exc_type else 'success'
            
            self.logger.info(
                f"operation={self.operation_name} | "
                f"duration_ms={duration_ms:.2f} | "
                f"user_id={self.user_id} | "
                f"status={status}"
            )
            
            # Log warning for slow operations
            if duration_ms > 3000:  # > 3 seconds
                logging.getLogger(__name__).warning(
                    f"Slow {self.operation_name} operation: {duration_ms:.2f}ms"
                )


class LoggingHelper:
    """Helper class for structured logging"""
    
    @staticmethod
    def log_vpn_operation(
        user_id: int, 
        operation: str, 
        client_name: str = None,
        success: bool = True,
        error: str = None,
        **kwargs
    ) -> None:
        """Log VPN-specific operations"""
        structured_logger.log_user_action(
            user_id=user_id,
            action='vpn_operation',
            operation=operation,
            client_name=client_name,
            success=success,
            error=error,
            **kwargs
        )
    
    @staticmethod
    def log_system_operation(
        operation: str,
        success: bool = True,
        error: str = None,
        **kwargs
    ) -> None:
        """Log system-level operations"""
        structured_logger.log_system_event(
            event='system_operation',
            operation=operation,
            success=success,
            error=error,
            **kwargs
        )
    
    @staticmethod
    def log_security_event(
        event_type: str,
        user_id: int = None,
        severity: str = 'info',
        **kwargs
    ) -> None:
        """Log security-related events"""
        from ...config.logging_config import get_audit_logger
        
        audit_logger = get_audit_logger()
        
        log_method = getattr(audit_logger, severity, audit_logger.info)
        log_method(
            f"Security event | type={event_type} | "
            f"user_id={user_id} | " +
            " | ".join(f"{k}={v}" for k, v in kwargs.items())
        )


# Performance monitoring decorator
def monitor_performance(operation_name: str = None):
    """Decorator for monitoring function performance"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            # Try to extract user_id from arguments
            user_id = None
            for arg in args:
                if hasattr(arg, 'from_user') and arg.from_user:
                    user_id = arg.from_user.id
                    break
            
            with PerformanceMonitor(op_name, user_id):
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator
