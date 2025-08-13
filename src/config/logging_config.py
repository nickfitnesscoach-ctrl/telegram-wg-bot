"""
Logging configuration for Telegram WireGuard Bot
"""
import logging
import logging.handlers
import os
from pathlib import Path
from typing import Dict, Any

from .settings import settings


def setup_logging() -> None:
    """Setup logging configuration with rotation and formatting"""
    
    # Create log directory if it doesn't exist
    log_file_path = Path(settings.LOG_FILE)
    log_dir = log_file_path.parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create detailed formatter for file logging
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)-25s | %(funcName)-20s:%(lineno)-4d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=settings.LOG_FILE,
            maxBytes=settings.LOG_MAX_SIZE_MB * 1024 * 1024,  # Convert MB to bytes
            backupCount=settings.LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
        
    except (OSError, PermissionError) as e:
        # Fallback to console only if file logging fails
        console_handler.setLevel(logging.WARNING)
        root_logger.warning(f"Failed to setup file logging: {e}. Using console only.")
    
    # Configure specific loggers
    configure_library_loggers()
    
    # Log configuration info
    root_logger.info("Logging configured successfully")
    root_logger.info(f"Log level: {settings.LOG_LEVEL}")
    root_logger.info(f"Log file: {settings.LOG_FILE}")


def configure_library_loggers() -> None:
    """Configure logging for third-party libraries"""
    
    # Aiogram logging
    aiogram_logger = logging.getLogger("aiogram")
    aiogram_logger.setLevel(logging.WARNING)
    
    # HTTP libraries
    http_loggers = [
        "aiohttp.access",
        "aiohttp.client",
        "aiohttp.internal",
        "aiohttp.server",
        "aiohttp.web",
        "urllib3.connectionpool"
    ]
    
    for logger_name in http_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
    
    # SQLAlchemy (if using)
    sqlalchemy_logger = logging.getLogger("sqlalchemy")
    sqlalchemy_logger.setLevel(logging.WARNING)


def get_audit_logger() -> logging.Logger:
    """Get audit logger for security events"""
    audit_logger = logging.getLogger("audit")
    
    if not audit_logger.handlers:
        # Create audit-specific file handler
        audit_file = Path(settings.LOG_FILE).parent / "audit.log"
        
        try:
            audit_handler = logging.handlers.RotatingFileHandler(
                filename=audit_file,
                maxBytes=settings.LOG_MAX_SIZE_MB * 1024 * 1024,
                backupCount=settings.LOG_BACKUP_COUNT,
                encoding='utf-8'
            )
            
            audit_formatter = logging.Formatter(
                fmt='%(asctime)s | AUDIT | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            audit_handler.setFormatter(audit_formatter)
            audit_logger.addHandler(audit_handler)
            audit_logger.setLevel(logging.INFO)
            
        except (OSError, PermissionError):
            # Fallback to main logger
            pass
    
    return audit_logger


def get_performance_logger() -> logging.Logger:
    """Get performance logger for monitoring"""
    perf_logger = logging.getLogger("performance")
    
    if not perf_logger.handlers:
        # Create performance-specific file handler
        perf_file = Path(settings.LOG_FILE).parent / "performance.log"
        
        try:
            perf_handler = logging.handlers.RotatingFileHandler(
                filename=perf_file,
                maxBytes=settings.LOG_MAX_SIZE_MB * 1024 * 1024,
                backupCount=5,  # Keep fewer performance logs
                encoding='utf-8'
            )
            
            perf_formatter = logging.Formatter(
                fmt='%(asctime)s | PERF | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            perf_handler.setFormatter(perf_formatter)
            perf_logger.addHandler(perf_handler)
            perf_logger.setLevel(logging.INFO)
            
        except (OSError, PermissionError):
            # Fallback to main logger
            pass
    
    return perf_logger


class StructuredLogger:
    """Structured logging helper"""
    
    def __init__(self, logger_name: str):
        self.logger = logging.getLogger(logger_name)
    
    def log_user_action(self, user_id: int, action: str, **kwargs) -> None:
        """Log user action with structured data"""
        data = {
            "user_id": user_id,
            "action": action,
            **kwargs
        }
        
        self.logger.info(f"User action: {self._format_data(data)}")
    
    def log_system_event(self, event: str, **kwargs) -> None:
        """Log system event with structured data"""
        data = {
            "event": event,
            **kwargs
        }
        
        self.logger.info(f"System event: {self._format_data(data)}")
    
    def log_error(self, error: str, **kwargs) -> None:
        """Log error with structured data"""
        data = {
            "error": error,
            **kwargs
        }
        
        self.logger.error(f"Error: {self._format_data(data)}")
    
    def log_performance(self, operation: str, duration_ms: float, **kwargs) -> None:
        """Log performance metrics"""
        perf_logger = get_performance_logger()
        data = {
            "operation": operation,
            "duration_ms": duration_ms,
            **kwargs
        }
        
        perf_logger.info(self._format_data(data))
    
    @staticmethod
    def _format_data(data: Dict[str, Any]) -> str:
        """Format structured data for logging"""
        formatted_items = []
        for key, value in data.items():
            formatted_items.append(f"{key}={value}")
        return " | ".join(formatted_items)


# Global structured logger instance
structured_logger = StructuredLogger("structured")
