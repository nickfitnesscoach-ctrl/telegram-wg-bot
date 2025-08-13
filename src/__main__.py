#!/usr/bin/env python3
"""
Entry point for running as module: python -m src
"""
import asyncio
import logging
from .main import TelegramWGBot

async def _main():
    """Main entry point"""
    logging.basicConfig(
        level=logging.INFO, 
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    
    # Apply secret filter to all handlers
    from .security.logging_filters import SecretFilter
    for h in logging.getLogger().handlers:
        h.addFilter(SecretFilter())
    
    app = TelegramWGBot()
    await app.create_bot()
    await app.dp.start_polling(app.bot)

if __name__ == "__main__":
    asyncio.run(_main())
