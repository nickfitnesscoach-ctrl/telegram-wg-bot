#!/usr/bin/env python3
"""Test middleware chain creation"""
import asyncio
import os

# Set minimal environment
os.environ.setdefault('BOT_TOKEN', 'test_token_123:ABC')
os.environ.setdefault('ALLOWED_USERS', '123456789')
os.environ.setdefault('SERVER_IP', '127.0.0.1')

async def test_middleware():
    try:
        from main import TelegramWGBot
        bot_app = TelegramWGBot()
        await bot_app.create_bot()
        print('✅ Middleware chain created successfully')
        print('✅ Bot created:', type(bot_app.bot).__name__)
        print('✅ Dispatcher created:', type(bot_app.dp).__name__)
        return True
    except Exception as e:
        print(f'❌ Middleware test failed: {e}')
        return False

if __name__ == "__main__":
    success = asyncio.run(test_middleware())
    exit(0 if success else 1)
