"""
Simplified logging configuration for production (journald only)
"""
import logging
import sys
from .settings import settings


def setup_logging() -> None:
    """
    Setup logging configuration for production with journald
    Eliminates file handler complexity - use journalctl for log access
    """
    # Create formatter for console/journald
    formatter = logging.Formatter(
        fmt='%(levelname)-8s | %(name)-25s | %(funcName)-20s:%(lineno)-4d | %(message)s'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler (goes to journald in systemd)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Configure specific loggers for different purposes
    # Audit logger for security events
    audit_logger = logging.getLogger('audit')
    audit_logger.setLevel(logging.INFO)
    
    # Performance logger for metrics
    performance_logger = logging.getLogger('performance')
    performance_logger.setLevel(logging.INFO)
    
    # Disable third-party library verbose logging
    logging.getLogger('aiogram').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)


def get_audit_logger():
    """Get audit logger for security events"""
    return logging.getLogger('audit')


def get_performance_logger():
    """Get performance logger for metrics"""
    return logging.getLogger('performance')


def structured_logger(category: str) -> logging.Logger:
    """Get structured logger for specific category"""
    return logging.getLogger(f'structured.{category}')


class SecurityFilter(logging.Filter):
    """Filter to prevent token leakage in logs"""
    
    def filter(self, record):
        if hasattr(record, 'msg'):
            # Hide potential tokens in log messages
            msg = str(record.msg)
            if ':' in msg and len(msg) > 20:
                # Look for token-like patterns (bot tokens are long)
                import re
                record.msg = re.sub(r'\b\d{10}:[A-Za-z0-9_-]{35}\b', '[BOT_TOKEN_HIDDEN]', msg)
        return True
