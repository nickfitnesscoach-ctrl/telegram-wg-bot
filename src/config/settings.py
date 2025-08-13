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
    
    def validate(self) -> None:
        """Validate required settings"""
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required")
        if not self.ALLOWED_USERS:
            raise ValueError("ALLOWED_USERS is required")


# Global settings instance
settings = Settings()
