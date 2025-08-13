#!/usr/bin/env python3
"""
Quick Windows test for telegram-wg-bot
Verify imports and basic functionality work on Windows
"""
import os
import sys

def test_imports():
    """Test that all modules can be imported"""
    print("🧪 Testing imports...")
    
    try:
        from src.config.settings import settings
        print("✅ Settings imported successfully")
    except Exception as e:
        print(f"❌ Settings import failed: {e}")
        return False
    
    try:
        from src.bot.middlewares.enhanced_rate_limit import FastRateLimit
        print("✅ FastRateLimit imported successfully")
    except Exception as e:
        print(f"❌ FastRateLimit import failed: {e}")
        return False
    
    try:
        from src.bot.middlewares.error_handler import GlobalErrorHandler
        print("✅ GlobalErrorHandler imported successfully")
    except Exception as e:
        print(f"❌ GlobalErrorHandler import failed: {e}")
        return False
    
    try:
        from src.bot.middlewares.fast_auth import FastAuthMiddleware
        print("✅ FastAuthMiddleware imported successfully")
    except Exception as e:
        print(f"❌ FastAuthMiddleware import failed: {e}")
        return False
    
    try:
        from src.bot.middlewares.audit_middleware import AuditMiddleware
        print("✅ AuditMiddleware imported successfully")
    except Exception as e:
        print(f"❌ AuditMiddleware import failed: {e}")
        return False
    
    try:
        from src.bot.utils.telegram_utils import TelegramTimeout
        print("✅ TelegramUtils imported successfully")
    except Exception as e:
        print(f"❌ TelegramUtils import failed: {e}")
        return False
    
    return True

def test_settings():
    """Test settings configuration"""
    print("\n⚙️ Testing settings...")
    
    try:
        from src.config.settings import settings
        
        # Set some required environment variables for testing
        os.environ.setdefault('BOT_TOKEN', 'test_token_123')
        os.environ.setdefault('ALLOWED_USERS', '123456789')
        os.environ.setdefault('SERVER_IP', '127.0.0.1')
        
        print(f"✅ Rate limit: {settings.MAX_COMMANDS_PER_MINUTE}/min")
        print(f"✅ Command timeout: {settings.COMMAND_TIMEOUT}s") 
        print(f"✅ Max clients: {settings.MAX_CLIENTS}")
        print(f"✅ Log level: {settings.LOG_LEVEL}")
        
        return True
        
    except Exception as e:
        print(f"❌ Settings test failed: {e}")
        return False

def test_middleware_creation():
    """Test middleware can be created"""
    print("\n🔧 Testing middleware creation...")
    
    try:
        from src.bot.middlewares.enhanced_rate_limit import FastRateLimit
        rate_limit = FastRateLimit()
        print("✅ FastRateLimit created")
        
        from src.bot.middlewares.error_handler import GlobalErrorHandler
        error_handler = GlobalErrorHandler()
        print("✅ GlobalErrorHandler created")
        
        from src.bot.middlewares.fast_auth import FastAuthMiddleware
        auth = FastAuthMiddleware()
        print("✅ FastAuthMiddleware created")
        
        from src.bot.middlewares.audit_middleware import AuditMiddleware
        audit = AuditMiddleware()
        print("✅ AuditMiddleware created")
        
        return True
        
    except Exception as e:
        print(f"❌ Middleware creation failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Windows Compatibility Test")
    print("=" * 40)
    
    # Set minimal environment for testing
    os.environ.setdefault('BOT_TOKEN', 'test_token_123')
    os.environ.setdefault('ALLOWED_USERS', '123456789')
    os.environ.setdefault('SERVER_IP', '127.0.0.1')
    
    tests = [
        test_imports,
        test_settings,
        test_middleware_creation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print(f"❌ {test.__name__} failed")
        except Exception as e:
            print(f"❌ {test.__name__} crashed: {e}")
    
    print("\n" + "=" * 40)
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Windows compatibility OK")
        return True
    else:
        print("⚠️ Some tests failed. Check errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
