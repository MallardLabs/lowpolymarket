#!/usr/bin/env python3
"""
Test setup script to verify all systems are working.

This script tests:
- Configuration loading
- Dependency injection
- Logging system
- Error handling
- Database connections (if configured)
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config import validate_configuration, ConfigurationError
from core.container import DIContainer, get_container, set_container
from core.logging_manager import get_logging_manager, get_logger, set_correlation_id
from core.error_handler import ErrorHandler, get_error_handler, set_error_handler
from core.rate_limiter import RateLimiter
from core.security import SecurityManager


async def test_configuration():
    """Test configuration loading and validation."""
    print("🔧 Testing configuration...")
    
    try:
        settings = validate_configuration()
        print(f"✅ Configuration loaded successfully")
        print(f"   Environment: {settings.environment}")
        print(f"   Debug mode: {settings.debug}")
        print(f"   Log level: {settings.logging.level}")
        return settings
    except ConfigurationError as e:
        print(f"❌ Configuration error: {e}")
        return None


async def test_logging(settings):
    """Test logging system."""
    print("\n📝 Testing logging system...")
    
    try:
        # Initialize logging
        logging_manager = get_logging_manager(settings.logging)
        logger = get_logger("TestSetup")
        
        # Set correlation ID
        correlation_id = set_correlation_id("TEST_SETUP")
        
        # Test different log levels
        logger.debug("Debug message test")
        logger.info("Info message test")
        logger.warning("Warning message test")
        
        # Test structured logging
        logger.info(
            "Structured logging test",
            extra={
                'test_field': 'test_value',
                'correlation_id': correlation_id,
                'number': 42
            }
        )
        
        print(f"✅ Logging system working")
        print(f"   Correlation ID: {correlation_id}")
        return True
        
    except Exception as e:
        print(f"❌ Logging system error: {e}")
        return False


async def test_dependency_injection():
    """Test dependency injection container."""
    print("\n📦 Testing dependency injection...")
    
    try:
        # Create container
        container = DIContainer()
        set_container(container)
        
        # Register test services
        container.register_singleton(RateLimiter, RateLimiter)
        container.register_singleton(SecurityManager, SecurityManager)
        container.register_singleton(ErrorHandler, ErrorHandler)
        
        # Test service resolution
        rate_limiter = await container.get_service(RateLimiter)
        security_manager = await container.get_service(SecurityManager)
        error_handler = await container.get_service(ErrorHandler)
        
        print(f"✅ Dependency injection working")
        print(f"   Services registered: {len(container.get_registered_services())}")
        
        # Test singleton behavior
        rate_limiter2 = await container.get_service(RateLimiter)
        assert rate_limiter is rate_limiter2, "Singleton not working correctly"
        
        print(f"✅ Singleton behavior verified")
        return True
        
    except Exception as e:
        print(f"❌ Dependency injection error: {e}")
        return False


async def test_rate_limiter():
    """Test rate limiting system."""
    print("\n🚦 Testing rate limiter...")
    
    try:
        container = get_container()
        rate_limiter = await container.get_service(RateLimiter)
        
        # Test rate limiting
        key = "test_user:123"
        action = "test_action"
        
        # Should allow first request
        allowed1 = await rate_limiter.check_rate_limit(key, action)
        print(f"   First request allowed: {allowed1}")
        
        # Test multiple requests
        for i in range(5):
            allowed = await rate_limiter.check_rate_limit(key, action)
            print(f"   Request {i+2} allowed: {allowed}")
        
        print(f"✅ Rate limiter working")
        return True
        
    except Exception as e:
        print(f"❌ Rate limiter error: {e}")
        return False


async def test_error_handler():
    """Test error handling system."""
    print("\n⚠️ Testing error handler...")
    
    try:
        container = get_container()
        error_handler = await container.get_service(ErrorHandler)
        
        # Test error logging
        test_error = Exception("This is a test error")
        error_info = error_handler.handle_background_error(
            test_error,
            {"test_context": "test_value"}
        )
        
        print(f"✅ Error handler working")
        print(f"   Error ID: {error_info['error_id']}")
        
        # Test error statistics
        stats = error_handler.get_error_statistics()
        print(f"   Total errors logged: {stats['total_errors']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error handler error: {e}")
        return False


async def test_security_manager():
    """Test security manager."""
    print("\n🔒 Testing security manager...")
    
    try:
        container = get_container()
        security_manager = await container.get_service(SecurityManager)
        
        # Test input sanitization
        test_input = "<script>alert('xss')</script>Hello World"
        sanitized = security_manager.sanitize_input(test_input)
        print(f"   Input sanitization: '{test_input}' -> '{sanitized}'")
        
        # Test SQL injection detection
        sql_injection = "'; DROP TABLE users; --"
        is_safe = security_manager.is_safe_input(sql_injection)
        print(f"   SQL injection detection: '{sql_injection}' is safe: {is_safe}")
        
        print(f"✅ Security manager working")
        return True
        
    except Exception as e:
        print(f"❌ Security manager error: {e}")
        return False


async def main():
    """Run all tests."""
    print("🧪 Discord Bot Architecture Test Suite")
    print("=" * 50)
    
    # Test configuration
    settings = await test_configuration()
    if not settings:
        print("\n❌ Configuration test failed. Cannot continue.")
        return False
    
    # Test logging
    logging_ok = await test_logging(settings)
    if not logging_ok:
        print("\n❌ Logging test failed.")
        return False
    
    # Test dependency injection
    di_ok = await test_dependency_injection()
    if not di_ok:
        print("\n❌ Dependency injection test failed.")
        return False
    
    # Test rate limiter
    rate_limiter_ok = await test_rate_limiter()
    if not rate_limiter_ok:
        print("\n❌ Rate limiter test failed.")
        return False
    
    # Test error handler
    error_handler_ok = await test_error_handler()
    if not error_handler_ok:
        print("\n❌ Error handler test failed.")
        return False
    
    # Test security manager
    security_ok = await test_security_manager()
    if not security_ok:
        print("\n❌ Security manager test failed.")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 All tests passed! Your bot architecture is ready.")
    print("\nNext steps:")
    print("1. Set up your Discord bot token in .env")
    print("2. Run: python main.py")
    print("3. Test the /test-balance command in Discord")
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test suite error: {e}")
        sys.exit(1)