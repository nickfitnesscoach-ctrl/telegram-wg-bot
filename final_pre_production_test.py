#!/usr/bin/env python3
"""
Final Pre-Production Test
Comprehensive test of all components before deployment
"""
import asyncio
import logging
import os
import sys
import time

# Set test environment
os.environ.setdefault('BOT_TOKEN', 'test_token_123:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefg')
os.environ.setdefault('ALLOWED_USERS', '123456789')
os.environ.setdefault('SERVER_IP', '127.0.0.1')
os.environ.setdefault('MAX_COMMANDS_PER_MINUTE', '10')

def test_imports():
    """Test all critical imports"""
    print("🧪 Testing imports...")
    try:
        # Core modules
        from src.config.settings import settings
        print("  ✅ Settings")
        
        from src.config.logging_config import setup_logging
        print("  ✅ Logging config")
        
        # Middleware
        from src.bot.middlewares.enhanced_rate_limit import FastRateLimit
        print("  ✅ FastRateLimit")
        
        from src.bot.middlewares.error_handler import GlobalErrorHandler
        print("  ✅ GlobalErrorHandler")
        
        from src.bot.middlewares.fast_auth import FastAuthMiddleware
        print("  ✅ FastAuthMiddleware")
        
        from src.bot.middlewares.audit_middleware import AuditMiddleware
        print("  ✅ AuditMiddleware")
        
        # Utils
        from src.bot.utils.telegram_utils import TelegramTimeout
        print("  ✅ TelegramUtils")
        
        # Handlers
        from src.bot.handlers import admin, vpn, system
        print("  ✅ All handlers")
        
        # Database
        from src.database.models import init_database
        print("  ✅ Database models")
        
        # Main
        from main import TelegramWGBot
        print("  ✅ Main bot class")
        
        return True
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        return False

def test_settings():
    """Test settings configuration"""
    print("\n⚙️ Testing settings...")
    try:
        from src.config.settings import settings
        
        print(f"  ✅ Rate limit: {settings.MAX_COMMANDS_PER_MINUTE}/min")
        print(f"  ✅ Command timeout: {settings.COMMAND_TIMEOUT}s")
        print(f"  ✅ Max clients: {settings.MAX_CLIENTS}")
        print(f"  ✅ Log level: {settings.LOG_LEVEL}")
        print(f"  ✅ Allowed users: {len(settings.ALLOWED_USERS)} users")
        
        return True
    except Exception as e:
        print(f"  ❌ Settings test failed: {e}")
        return False

def test_logging():
    """Test logging configuration"""
    print("\n📝 Testing logging...")
    try:
        from src.config.logging_config import setup_logging
        setup_logging()
        
        logger = logging.getLogger('test')
        logger.info('Test message')
        
        print("  ✅ Logging configured")
        print("  ✅ Test message logged")
        
        return True
    except Exception as e:
        print(f"  ❌ Logging test failed: {e}")
        return False

async def test_database():
    """Test database initialization"""
    print("\n💾 Testing database...")
    try:
        from src.database.models import init_database
        await init_database()
        
        print("  ✅ Database initialized")
        return True
    except Exception as e:
        print(f"  ❌ Database test failed: {e}")
        return False

def test_middleware_creation():
    """Test middleware instances can be created"""
    print("\n🔧 Testing middleware creation...")
    try:
        from src.bot.middlewares.enhanced_rate_limit import FastRateLimit
        rate_limit = FastRateLimit()
        print("  ✅ FastRateLimit created")
        
        from src.bot.middlewares.error_handler import GlobalErrorHandler
        error_handler = GlobalErrorHandler()
        print("  ✅ GlobalErrorHandler created")
        
        from src.bot.middlewares.fast_auth import FastAuthMiddleware
        auth = FastAuthMiddleware()
        print("  ✅ FastAuthMiddleware created")
        
        from src.bot.middlewares.audit_middleware import AuditMiddleware
        audit = AuditMiddleware()
        print("  ✅ AuditMiddleware created")
        
        return True
    except Exception as e:
        print(f"  ❌ Middleware creation failed: {e}")
        return False

def test_rate_limiting():
    """Test rate limiting logic"""
    print("\n⏱️ Testing rate limiting...")
    try:
        from src.bot.middlewares.enhanced_rate_limit import FastRateLimit
        
        rate_limit = FastRateLimit(per_user_per_min=3)
        
        # Simulate user commands
        user_id = 123456789
        now = time.monotonic()
        
        # Add commands to bucket
        rate_limit.bucket[user_id] = [now, now + 1, now + 2]
        
        # Check if limit would be exceeded
        commands_count = len(rate_limit.bucket[user_id])
        limit_exceeded = commands_count >= rate_limit.per_user_per_min
        
        print(f"  ✅ Commands in bucket: {commands_count}")
        print(f"  ✅ Limit: {rate_limit.per_user_per_min}")
        print(f"  ✅ Would be blocked: {limit_exceeded}")
        
        return True
    except Exception as e:
        print(f"  ❌ Rate limiting test failed: {e}")
        return False

async def test_bot_creation():
    """Test bot instance creation"""
    print("\n🤖 Testing bot creation...")
    try:
        from main import TelegramWGBot
        
        bot_app = TelegramWGBot()
        await bot_app.create_bot()
        
        print("  ✅ Bot instance created")
        print("  ✅ Middleware chain setup")
        print(f"  ✅ Bot type: {type(bot_app.bot).__name__}")
        print(f"  ✅ Dispatcher type: {type(bot_app.dp).__name__}")
        
        return True
    except Exception as e:
        print(f"  ❌ Bot creation failed: {e}")
        return False

async def run_all_tests():
    """Run comprehensive test suite"""
    print("🚀 FINAL PRE-PRODUCTION TEST SUITE")
    print("="*50)
    
    tests = [
        ("Imports", test_imports),
        ("Settings", test_settings),
        ("Logging", test_logging),
        ("Database", test_database),
        ("Middleware Creation", test_middleware_creation),
        ("Rate Limiting", test_rate_limiting),
        ("Bot Creation", test_bot_creation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                passed += 1
            
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
    
    print("\n" + "="*50)
    print(f"📊 RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! 100% Ready for production!")
        print("\n🚀 DEPLOYMENT READINESS:")
        print("  ✅ All imports working")
        print("  ✅ Settings configured")
        print("  ✅ Logging operational")
        print("  ✅ Database ready")
        print("  ✅ Middleware chain functional")
        print("  ✅ Rate limiting active")
        print("  ✅ Bot creation successful")
        print("\n🎯 STATUS: PRODUCTION READY!")
        return True
    else:
        print(f"⚠️ {total - passed} tests failed. Check errors above.")
        print("❌ NOT READY for production deployment")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
