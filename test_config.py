#!/usr/bin/env python3
"""
Test script for the configuration system.

This script validates that the configuration system works correctly
and can load settings from environment variables and files.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_configuration():
    """Test the configuration system."""
    print("Testing Configuration System")
    print("=" * 50)
    
    # Set up test environment
    os.environ.update({
        'DISCORD_TOKEN': 'test_token_that_is_long_enough_to_pass_validation_requirements_12345',
        'DATABASE_URL': 'postgresql://test:test@localhost:5432/test',
        'DATABASE_SUPABASE_URL': 'https://test.supabase.co',
        'DATABASE_SUPABASE_PUBLISHABLE_KEY': 'sb_publishable_test_key_12345',
        'DATABASE_SUPABASE_SECRET_KEY': 'sb_secret_test_key_12345',
        'API_API_KEY': 'test_api_key',
        'API_REALM_ID': 'test_realm_id',
        'ENVIRONMENT': 'development'
    })
    
    try:
        # Test importing the configuration module
        from config import validate_configuration, print_configuration_summary
        
        print("✅ Configuration module imported successfully")
        
        # Test configuration validation
        settings = validate_configuration()
        print("✅ Configuration validation successful")
        
        # Print configuration summary
        print_configuration_summary(settings)
        
        # Test accessing different configuration sections
        print("\nTesting Configuration Access:")
        print(f"  Environment: {settings.environment}")
        print(f"  Debug Mode: {settings.debug}")
        print(f"  Max Bet Amount: {settings.business.max_bet_amount:,}")
        print(f"  Cache TTL: {settings.cache.default_ttl}s")
        print(f"  Rate Limit: {settings.rate_limit.user_requests_per_minute}/min")
        
        print("\n✅ All configuration tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_configuration()
    sys.exit(0 if success else 1)