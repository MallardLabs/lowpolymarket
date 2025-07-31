#!/usr/bin/env python3
"""
Configuration validation script for the Discord Prediction Market Bot.

This script validates the configuration setup and provides helpful feedback
for any configuration issues.

Usage:
    python scripts/validate_config.py
    python scripts/validate_config.py --environment production
    python scripts/validate_config.py --show-summary
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
load_dotenv(project_root / ".env", override=True)

def main():
    parser = argparse.ArgumentParser(description="Validate bot configuration")
    parser.add_argument(
        "--environment", 
        choices=["development", "staging", "production"],
        help="Set the environment to validate"
    )
    parser.add_argument(
        "--show-summary", 
        action="store_true",
        help="Show detailed configuration summary"
    )
    parser.add_argument(
        "--check-env-vars",
        action="store_true", 
        help="Check for missing required environment variables"
    )
    
    args = parser.parse_args()
    
    # Set environment if specified
    if args.environment:
        os.environ["ENVIRONMENT"] = args.environment
        print(f"🔧 Validating configuration for {args.environment} environment")
    
    try:
        from config import (
            validate_configuration, 
            print_configuration_summary,
            check_required_environment_variables
        )
        
        # Check for missing environment variables first
        if args.check_env_vars:
            print("🔍 Checking required environment variables...")
            missing_vars = check_required_environment_variables()
            if missing_vars:
                print("❌ Missing required environment variables:")
                for var in missing_vars:
                    print(f"   • {var}")
                print("\nPlease set these variables in your .env file or environment.")
                return False
            else:
                print("✅ All required environment variables are set")
        
        # Validate configuration
        print("🔍 Validating configuration...")
        settings = validate_configuration()
        print("✅ Configuration validation successful!")
        
        # Show summary if requested
        if args.show_summary:
            print_configuration_summary(settings)
        else:
            print(f"Environment: {settings.environment.value}")
            print(f"Debug Mode: {settings.debug}")
            print(f"Discord Token: {'Set' if settings.discord.token else 'Missing'}")
            print(f"Database URL: {'Set' if settings.database.url else 'Missing'}")
            print(f"Cache Type: {'Redis' if settings.cache.redis_url else 'Memory Only'}")
        
        print("\n🎉 Configuration is ready for use!")
        return True
        
    except Exception as e:
        print(f"❌ Configuration validation failed:")
        print(f"   {e}")
        
        # Provide helpful hints
        if "DISCORD_TOKEN" in str(e):
            print("\n💡 Hint: Make sure to set DISCORD_TOKEN in your .env file")
        elif "DATABASE_URL" in str(e):
            print("\n💡 Hint: Make sure to set DATABASE_URL with a valid PostgreSQL connection")
        elif "API_KEY" in str(e):
            print("\n💡 Hint: Make sure to set API_API_KEY and API_REALM_ID for DRIP integration")
        
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)