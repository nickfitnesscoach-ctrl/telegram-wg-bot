"""
Validation utilities for Telegram WireGuard Bot
"""
import re
import ipaddress
from typing import Optional, Tuple, List

from ...config.settings import settings


class ValidationError(Exception):
    """Custom validation error"""
    pass


class ConfigNameValidator:
    """
    Validator for VPN config names
    Implements TZ requirements from section 3.2:
    - Длина: 3-20 символов
    - Символы: латиница, цифры, дефис, подчеркивание
    """
    
    MIN_LENGTH = 3
    MAX_LENGTH = 20
    ALLOWED_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
    
    @classmethod
    def validate(cls, name: str) -> Tuple[bool, Optional[str]]:
        """
        Validate config name
        Returns: (is_valid, error_message)
        """
        if not name:
            return False, "Имя конфигурации не может быть пустым"
        
        # Check length
        if len(name) < cls.MIN_LENGTH:
            return False, f"Имя слишком короткое (минимум {cls.MIN_LENGTH} символа)"
        
        if len(name) > cls.MAX_LENGTH:
            return False, f"Имя слишком длинное (максимум {cls.MAX_LENGTH} символов)"
        
        # Check allowed characters
        if not cls.ALLOWED_PATTERN.match(name):
            return False, (
                "Имя может содержать только:\n"
                "• Латинские буквы (a-z, A-Z)\n"
                "• Цифры (0-9)\n"
                "• Дефис (-)\n"
                "• Подчеркивание (_)"
            )
        
        # Check for reserved names
        reserved_names = ['server', 'wg0', 'admin', 'root', 'default', 'config']
        if name.lower() in reserved_names:
            return False, f"Имя '{name}' зарезервировано системой"
        
        return True, None
    
    @classmethod
    def suggest_alternatives(cls, invalid_name: str) -> List[str]:
        """Suggest valid alternatives for invalid name"""
        suggestions = []
        
        # Clean the name
        cleaned = re.sub(r'[^a-zA-Z0-9_-]', '', invalid_name)
        
        if cleaned and len(cleaned) >= cls.MIN_LENGTH:
            suggestions.append(cleaned[:cls.MAX_LENGTH])
        
        # Add timestamp-based suggestions
        import datetime
        timestamp = datetime.datetime.now().strftime("%m%d")
        
        if cleaned:
            base = cleaned[:cls.MAX_LENGTH-4]
            suggestions.extend([
                f"{base}_{timestamp}",
                f"{base}-{timestamp}",
                f"client_{timestamp}"
            ])
        else:
            suggestions.extend([
                f"client_{timestamp}",
                f"device_{timestamp}",
                f"vpn_{timestamp}"
            ])
        
        return suggestions[:3]  # Return top 3 suggestions


class IPAddressValidator:
    """Validator for IP addresses"""
    
    @staticmethod
    def is_valid_ipv4(ip: str) -> bool:
        """Check if string is valid IPv4 address"""
        try:
            ipaddress.IPv4Address(ip)
            return True
        except ipaddress.AddressValueError:
            return False
    
    @staticmethod
    def is_valid_ipv6(ip: str) -> bool:
        """Check if string is valid IPv6 address"""
        try:
            ipaddress.IPv6Address(ip)
            return True
        except ipaddress.AddressValueError:
            return False
    
    @staticmethod
    def is_valid_cidr(cidr: str) -> bool:
        """Check if string is valid CIDR notation"""
        try:
            ipaddress.ip_network(cidr, strict=False)
            return True
        except ipaddress.AddressValueError:
            return False


class SystemLimitValidator:
    """Validator for system limits"""
    
    @staticmethod
    def check_client_limit(current_count: int) -> Tuple[bool, Optional[str]]:
        """
        Check if we can create more clients
        Implements TZ requirement: MAX_CLIENTS = 50
        """
        if current_count >= settings.MAX_CLIENTS:
            return False, (
                f"Достигнут лимит клиентов ({settings.MAX_CLIENTS}).\n"
                "Удалите неиспользуемые конфигурации или обратитесь к администратору."
            )
        
        # Warning when approaching limit
        if current_count >= settings.MAX_CLIENTS * 0.9:  # 90% of limit
            remaining = settings.MAX_CLIENTS - current_count
            return True, f"⚠️ Осталось мест: {remaining}/{settings.MAX_CLIENTS}"
        
        return True, None
    
    @staticmethod
    def check_disk_space(free_space_gb: float) -> Tuple[bool, Optional[str]]:
        """
        Check available disk space
        Implements TZ requirement: warn when < 5GB free
        """
        if free_space_gb < settings.MIN_FREE_SPACE_GB:
            return False, (
                f"⚠️ Мало свободного места: {free_space_gb:.1f}GB\n"
                f"Минимум требуется: {settings.MIN_FREE_SPACE_GB}GB"
            )
        
        return True, None


class CommandValidator:
    """Validator for bot commands and arguments"""
    
    VALID_COMMANDS = {
        '/start', '/help', '/about',
        '/newconfig', '/list', '/getconfig', '/delete',
        '/status', '/logs', '/backup', '/restore'
    }
    
    @classmethod
    def validate_command(cls, command: str) -> Tuple[bool, Optional[str]]:
        """Validate if command is recognized"""
        if not command.startswith('/'):
            return False, "Команда должна начинаться с /"
        
        base_command = command.split('@')[0]  # Remove bot username if present
        
        if base_command not in cls.VALID_COMMANDS:
            return False, (
                "Неизвестная команда. Используйте /help для списка доступных команд."
            )
        
        return True, None
    
    @staticmethod
    def validate_config_number(number_str: str, max_number: int) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Validate config number from user input
        Returns: (is_valid, error_message, number)
        """
        try:
            number = int(number_str)
        except ValueError:
            return False, "Номер должен быть числом", None
        
        if number < 1:
            return False, "Номер должен быть больше 0", None
        
        if number > max_number:
            return False, f"Номер не может быть больше {max_number}", None
        
        return True, None, number


class InputSanitizer:
    """Sanitizer for user input to prevent injection attacks"""
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent path traversal"""
        # Remove path separators and dangerous characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
        sanitized = re.sub(r'\.\.', '', sanitized)  # Remove parent directory references
        
        # Limit length
        return sanitized[:100]
    
    @staticmethod
    def sanitize_shell_argument(arg: str) -> str:
        """Sanitize argument for shell commands"""
        # Only allow safe characters for shell commands
        return re.sub(r'[^a-zA-Z0-9_.-]', '', arg)
    
    @staticmethod
    def sanitize_log_message(message: str) -> str:
        """Sanitize message for logging to prevent log injection"""
        # Remove newlines and control characters
        sanitized = re.sub(r'[\r\n\t]', ' ', message)
        # Limit length
        return sanitized[:500]


class WireGuardValidator:
    """Validator for WireGuard-specific data"""
    
    @staticmethod
    def validate_public_key(key: str) -> bool:
        """Validate WireGuard public key format"""
        if not key:
            return False
        
        # WireGuard keys are 44 characters base64
        if len(key) != 44:
            return False
        
        # Check if it's valid base64
        try:
            import base64
            decoded = base64.b64decode(key + '==')  # Add padding
            return len(decoded) == 32  # WireGuard keys are 32 bytes
        except Exception:
            return False
    
    @staticmethod
    def validate_private_key(key: str) -> bool:
        """Validate WireGuard private key format"""
        return WireGuardValidator.validate_public_key(key)  # Same format
    
    @staticmethod
    def validate_port(port: str) -> Tuple[bool, Optional[str]]:
        """Validate port number"""
        try:
            port_num = int(port)
        except ValueError:
            return False, "Порт должен быть числом"
        
        if port_num < 1 or port_num > 65535:
            return False, "Порт должен быть в диапазоне 1-65535"
        
        # Check if port is commonly used by other services
        restricted_ports = [22, 23, 25, 53, 80, 110, 143, 443, 993, 995]
        if port_num in restricted_ports:
            return False, f"Порт {port_num} используется другими сервисами"
        
        return True, None


def validate_all_limits() -> List[str]:
    """
    Validate all system limits and return warnings
    Used for system health checks
    """
    warnings = []
    
    # This would be called with actual system data
    # For now, return empty list
    return warnings


def format_validation_error(field_name: str, error_message: str) -> str:
    """Format validation error message consistently"""
    return f"❌ <b>{field_name}</b>: {error_message}"


def format_validation_success(field_name: str, value: str) -> str:
    """Format validation success message"""
    return f"✅ <b>{field_name}</b>: {value}"