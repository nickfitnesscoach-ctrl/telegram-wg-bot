#!/usr/bin/env python3
"""
Telegram WireGuard Bot - Main Entry Point
"""
import asyncio
import logging
import signal
import sys
from typing import NoReturn

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiohttp import ClientTimeout

# For aiogram 3.10.0 - using ClientTimeout and simple configuration

# Import configuration
from .config.settings import settings
from .config.logging_config import setup_logging

# Import handlers
from .bot.handlers import admin, vpn, system

# Import middlewares
from .bot.middlewares.logging import LoggingMiddleware

# Import services
from .services.health_checker import health_checker
from .database.models import init_database


class TelegramWGBot:
    """Main bot application class"""
    
    def __init__(self):
        """Initialize bot instance"""
        self.bot: Bot = None
        self.dp: Dispatcher = None
        self.health_checker = None
        self.logger = logging.getLogger(__name__)
        
    async def create_bot(self) -> None:
        """Create bot and dispatcher instances"""
        try:
            # Validate settings
            settings.validate()
            
            # Create bot with timeout configuration for aiogram 3.10.0
            self.bot = Bot(
                token=settings.BOT_TOKEN,
                timeout=ClientTimeout(total=30, connect=10)
            )
            
            # Create dispatcher
            self.dp = Dispatcher()
            
            # Setup database
            await init_database()
            
            # Import and register middleware (order matters!)
            from .config.settings import settings
            from .bot.middlewares.allow_only import AllowOnly
            from .bot.middlewares.simple_rate_limit import RateLimit

            # Authentication middleware
            self.dp.message.middleware(AllowOnly())
            
            # Rate limiting middleware
            self.dp.message.middleware(RateLimit(per_user_per_min=settings.RATE_LIMIT_PER_MIN))

            # Regular logging (last)
            self.dp.message.middleware(LoggingMiddleware())
            
            # Register handlers
            self.dp.include_router(system.router)
            self.dp.include_router(vpn.router)
            self.dp.include_router(admin.router)
            
            # Start health checker
            self.health_checker = health_checker
            asyncio.create_task(self.health_checker.start())
            
            self.logger.info("Bot created successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to create bot: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Graceful shutdown"""
        self.logger.info("Shutting down bot...")
        
        if self.health_checker:
            await self.health_checker.stop()
        
        if self.bot:
            await self.bot.session.close()
        
        self.logger.info("Bot shutdown complete")


async def signal_handler(app: TelegramWGBot) -> NoReturn:
    """Handle shutdown signals"""
    def signal_handler_sync(signum, frame):
        logging.getLogger(__name__).info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(app.shutdown())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler_sync)
    signal.signal(signal.SIGTERM, signal_handler_sync)


async def main() -> None:
    """Main application entry point"""
    # Setup logging first
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting Telegram WireGuard Bot...")
    
    try:
        # Create and initialize bot
        app = TelegramWGBot()
        
        # Setup signal handlers
        await signal_handler(app)
        
        # Create bot instance
        await app.create_bot()
        
        logger.info("Bot is ready! Starting polling...")
        
        # Start polling
        await app.dp.start_polling(
            app.bot,
            skip_updates=True,
            allowed_updates=["message", "callback_query"]
        )
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        if 'app' in locals():
            await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
