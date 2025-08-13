"""
Configuration settings for Telegram WireGuard Bot
"""
import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv  # для локальной разработки
    load_dotenv()
except Exception:
    pass

@dataclass
class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ALLOWED_USERS: str = os.getenv("ALLOWED_USERS", "")
    RATE_LIMIT_PER_MIN: int = int(os.getenv("RATE_LIMIT_PER_MIN", "10"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # WireGuard settings (needed for compatibility)
    WG_MANAGER_PATH: str = os.getenv("WG_MANAGER_PATH", "scripts/mock-wg-manager.py")
    WG_INTERFACE: str = os.getenv("WG_INTERFACE", "wg0")
    WG_CLIENTS_PATH: str = os.getenv("WG_CLIENTS_PATH", "/etc/wireguard/clients")
    MAX_CLIENTS: int = int(os.getenv("MAX_CLIENTS", "50"))
    SERVER_IP: str = os.getenv("SERVER_IP", "127.0.0.1")
    VPN_PORT: int = int(os.getenv("VPN_PORT", "51820"))
    
    # Additional settings for compatibility
    BACKUP_PATH: str = os.getenv("BACKUP_PATH", "./backups")
    BACKUP_RETENTION_DAYS: int = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
    HEALTH_CHECK_INTERVAL: int = int(os.getenv("HEALTH_CHECK_INTERVAL", "30"))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///wireguard_bot.db")
    COMMAND_TIMEOUT: int = int(os.getenv("COMMAND_TIMEOUT", "30"))
    MAX_COMMANDS_PER_MINUTE: int = int(os.getenv("MAX_COMMANDS_PER_MINUTE", "10"))
    
    # Logging settings
    LOG_FILE: str = os.getenv("LOG_FILE", "./logs/bot.log")
    LOG_MAX_SIZE_MB: int = int(os.getenv("LOG_MAX_SIZE_MB", "10"))
    LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "10"))
    
    def validate(self) -> None:
        """Validate required settings"""
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required")
        if not self.ALLOWED_USERS:
            raise ValueError("ALLOWED_USERS is required")


# Global settings instance
settings = Settings()
