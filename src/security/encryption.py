"""
Encryption utilities for sensitive data
"""
import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..config.settings import settings


class DataEncryption:
    """Encryption service for sensitive data like private keys"""
    
    def __init__(self):
        self._key = self._get_or_create_key()
        self._fernet = Fernet(self._key)
    
    def _get_or_create_key(self) -> bytes:
        """Get or create encryption key from environment"""
        # In production, this should come from secure key management
        encryption_password = os.getenv('ENCRYPTION_PASSWORD', 'default-change-this-in-production')
        
        # Generate key from password
        salt = os.getenv('ENCRYPTION_SALT', 'default-salt-change-this').encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(encryption_password.encode()))
        return key
    
    def encrypt(self, data: str) -> str:
        """Encrypt sensitive string data"""
        if not data:
            return data
        
        encrypted_data = self._fernet.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted_data).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt sensitive string data"""
        if not encrypted_data:
            return encrypted_data
        
        try:
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self._fernet.decrypt(decoded_data)
            return decrypted_data.decode()
        except Exception:
            # Return original data if decryption fails (backwards compatibility)
            return encrypted_data
    
    def encrypt_private_key(self, private_key: str) -> str:
        """Specifically encrypt WireGuard private keys"""
        return self.encrypt(private_key)
    
    def decrypt_private_key(self, encrypted_private_key: str) -> str:
        """Specifically decrypt WireGuard private keys"""
        return self.decrypt(encrypted_private_key)


class InputSanitizer:
    """Input sanitization utilities"""
    
    @staticmethod
    def sanitize_client_name(name: str) -> str:
        """Sanitize client name for security"""
        if not name:
            return ""
        
        # Remove dangerous characters
        allowed_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        sanitized = "".join(c for c in name if c in allowed_chars)
        
        # Limit length
        return sanitized[:64]
    
    @staticmethod
    def sanitize_html_output(text: str) -> str:
        """Sanitize text for HTML output in Telegram"""
        if not text:
            return ""
        
        # Escape HTML entities
        html_escape_table = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#x27;",
        }
        
        return "".join(html_escape_table.get(c, c) for c in text)
    
    @staticmethod
    def validate_ip_address(ip: str) -> bool:
        """Validate IP address format"""
        import ipaddress
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False


# Global instances
data_encryption = DataEncryption()
input_sanitizer = InputSanitizer()
