"""
Audit logging middleware for command tracking
Production-ready audit trail for security and compliance
"""
import logging
import time
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from ...config.logging_config import get_audit_logger


class AuditMiddleware(BaseMiddleware):
    """
    Audit logging middleware for tracking all user commands
    Essential for security monitoring and compliance
    """
    
    def __init__(self):
        self.audit_logger = get_audit_logger()
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Log command execution with audit trail"""
        
        # Extract audit information
        audit_info = self._extract_audit_info(event)
        if not audit_info:
            return await handler(event, data)
        
        start_time = time.time()
        
        try:
            # Execute handler
            result = await handler(event, data)
            
            # Log successful command
            execution_time = (time.time() - start_time) * 1000
            self._log_command_success(audit_info, execution_time)
            
            return result
            
        except Exception as e:
            # Log failed command
            execution_time = (time.time() - start_time) * 1000
            self._log_command_error(audit_info, execution_time, str(e))
            raise  # Re-raise for error handling middleware
    
    def _extract_audit_info(self, event: TelegramObject) -> Dict[str, Any] | None:
        """Extract information needed for audit logging"""
        
        if isinstance(event, Message):
            return {
                "user_id": event.from_user.id if event.from_user else None,
                "username": event.from_user.username if event.from_user else None,
                "chat_id": event.chat.id,
                "message_id": event.message_id,
                "command": self._extract_command(event.text or ""),
                "event_type": "message"
            }
        
        elif isinstance(event, CallbackQuery):
            return {
                "user_id": event.from_user.id if event.from_user else None,
                "username": event.from_user.username if event.from_user else None,
                "chat_id": event.message.chat.id if event.message else None,
                "message_id": event.message.message_id if event.message else None,
                "command": event.data or "",
                "event_type": "callback"
            }
        
        return None
    
    def _extract_command(self, text: str) -> str:
        """Extract command name from message text"""
        if not text or not text.startswith('/'):
            return "text"
        
        # Extract command without parameters
        command = text.split()[0] if text.split() else text
        return command.lower()
    
    def _log_command_success(self, audit_info: Dict[str, Any], execution_time: float):
        """Log successful command execution"""
        self.audit_logger.info(
            f"COMMAND_SUCCESS "
            f"user_id={audit_info['user_id']} "
            f"username={audit_info.get('username', 'N/A')} "
            f"command={audit_info['command']} "
            f"type={audit_info['event_type']} "
            f"execution_time={execution_time:.1f}ms"
        )
    
    def _log_command_error(self, audit_info: Dict[str, Any], execution_time: float, error: str):
        """Log failed command execution"""
        self.audit_logger.error(
            f"COMMAND_ERROR "
            f"user_id={audit_info['user_id']} "
            f"username={audit_info.get('username', 'N/A')} "
            f"command={audit_info['command']} "
            f"type={audit_info['event_type']} "
            f"execution_time={execution_time:.1f}ms "
            f"error={error}"
        )


class CommandAuditor:
    """
    Simple command auditor for direct use in handlers
    """
    
    def __init__(self):
        self.audit_logger = get_audit_logger()
    
    def log_command(self, user_id: int, command: str, success: bool = True, **kwargs):
        """Log command execution"""
        status = "SUCCESS" if success else "ERROR"
        
        log_message = f"CMD_{status} user_id={user_id} cmd={command}"
        
        # Add additional context
        for key, value in kwargs.items():
            log_message += f" {key}={value}"
        
        if success:
            self.audit_logger.info(log_message)
        else:
            self.audit_logger.error(log_message)
    
    def log_vpn_operation(self, user_id: int, operation: str, client_name: str = None, success: bool = True, **kwargs):
        """Log VPN-specific operations"""
        log_data = {
            "operation": operation,
            "success": success
        }
        
        if client_name:
            log_data["client_name"] = client_name
        
        log_data.update(kwargs)
        
        self.log_command(user_id, f"vpn_{operation}", success, **log_data)
    
    def log_admin_action(self, user_id: int, action: str, target: str = None, success: bool = True, **kwargs):
        """Log administrative actions"""
        log_data = {
            "admin_action": action,
            "success": success
        }
        
        if target:
            log_data["target"] = target
        
        log_data.update(kwargs)
        
        self.log_command(user_id, f"admin_{action}", success, **log_data)


# Global auditor instance for easy access
command_auditor = CommandAuditor()


def audit_command(command_name: str):
    """
    Decorator for automatic command auditing
    Usage: @audit_command("newconfig")
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            # Try to extract user_id from args
            user_id = None
            for arg in args:
                if hasattr(arg, 'from_user') and arg.from_user:
                    user_id = arg.from_user.id
                    break
            
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                
                command_auditor.log_command(
                    user_id=user_id or 0,
                    command=command_name,
                    success=True,
                    execution_time=f"{execution_time:.1f}ms"
                )
                
                return result
                
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                
                command_auditor.log_command(
                    user_id=user_id or 0,
                    command=command_name,
                    success=False,
                    execution_time=f"{execution_time:.1f}ms",
                    error=str(e)
                )
                
                raise
        
        return wrapper
    return decorator


class SecurityAuditor:
    """
    Security-focused audit logging
    """
    
    def __init__(self):
        self.audit_logger = get_audit_logger()
    
    def log_security_event(self, event_type: str, user_id: int, details: Dict[str, Any] = None):
        """Log security-related events"""
        log_message = f"SECURITY_{event_type.upper()} user_id={user_id}"
        
        if details:
            for key, value in details.items():
                log_message += f" {key}={value}"
        
        self.audit_logger.warning(log_message)
    
    def log_access_violation(self, user_id: int, attempted_action: str, **kwargs):
        """Log unauthorized access attempts"""
        self.log_security_event("ACCESS_VIOLATION", user_id, {
            "attempted_action": attempted_action,
            **kwargs
        })
    
    def log_rate_limit_violation(self, user_id: int, limit: int, current_count: int):
        """Log rate limit violations"""
        self.log_security_event("RATE_LIMIT_VIOLATION", user_id, {
            "limit": limit,
            "current_count": current_count
        })
    
    def log_suspicious_activity(self, user_id: int, activity_type: str, **kwargs):
        """Log suspicious user activity"""
        self.log_security_event("SUSPICIOUS_ACTIVITY", user_id, {
            "activity_type": activity_type,
            **kwargs
        })


# Global security auditor
security_auditor = SecurityAuditor()


def log_audit(message: str, **kwargs):
    """
    Quick audit logging function
    Usage: log_audit("User created VPN config", user_id=123, client_name="test")
    """
    audit_logger = get_audit_logger()
    
    log_parts = [message]
    for key, value in kwargs.items():
        log_parts.append(f"{key}={value}")
    
    audit_logger.info(" | ".join(log_parts))


def log_security(event_type: str, **kwargs):
    """
    Quick security logging function  
    Usage: log_security("unauthorized_access", user_id=123, action="admin_command")
    """
    audit_logger = get_audit_logger()
    
    log_parts = [f"SECURITY_{event_type.upper()}"]
    for key, value in kwargs.items():
        log_parts.append(f"{key}={value}")
    
    audit_logger.warning(" | ".join(log_parts))
