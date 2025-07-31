"""
Configuration validation utilities.

This module provides utilities for validating configuration settings
and providing helpful error messages for common configuration issues.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any

from pydantic import ValidationError

from .settings import Settings, Environment


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""
    
    def __init__(self, message: str, errors: List[Dict[str, Any]] = None):
        super().__init__(message)
        self.errors = errors or []


def validate_configuration() -> Settings:
    """
    Validate the application configuration and provide helpful error messages.
    
    Returns:
        Settings: The validated settings instance
        
    Raises:
        ConfigurationError: If configuration validation fails
    """
    try:
        settings = Settings()
        
        # Additional runtime validations
        _validate_file_paths(settings)
        _validate_environment_consistency(settings)
        
        return settings
        
    except ValidationError as e:
        error_messages = []
        
        for error in e.errors():
            field_path = " -> ".join(str(loc) for loc in error['loc'])
            error_msg = f"{field_path}: {error['msg']}"
            
            # Add helpful hints for common errors
            if 'discord' in field_path.lower() and 'token' in field_path.lower():
                error_msg += "\n  Hint: Set DISCORD_TOKEN in your .env file"
            elif 'database' in field_path.lower() and 'url' in field_path.lower():
                error_msg += "\n  Hint: Set DATABASE_URL with a valid PostgreSQL connection string"
            elif 'api' in field_path.lower() and ('key' in field_path.lower() or 'realm' in field_path.lower()):
                error_msg += "\n  Hint: Set API_KEY and API_REALM_ID for DRIP API integration"
            
            error_messages.append(error_msg)
        
        raise ConfigurationError(
            f"Configuration validation failed:\n" + "\n".join(f"  • {msg}" for msg in error_messages),
            e.errors()
        )


def _validate_file_paths(settings: Settings) -> None:
    """Validate that required file paths exist or can be created."""
    
    # Ensure log directory exists
    log_path = Path(settings.logging.file_path)
    if settings.logging.file_enabled:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if .env file exists
    env_file = Path(".env")
    if not env_file.exists():
        print("Warning: .env file not found. Using environment variables and defaults.")


def _validate_environment_consistency(settings: Settings) -> None:
    """Validate that environment-specific settings are consistent."""
    
    if settings.environment == Environment.PRODUCTION:
        # Production-specific validations
        if settings.debug:
            raise ConfigurationError("Debug mode must be disabled in production")
        
        if settings.logging.level == "DEBUG":
            print("Warning: DEBUG logging level in production may impact performance")
        
        if not settings.cache.redis_url and settings.environment == Environment.PRODUCTION:
            print("Warning: Redis cache not configured for production environment")


def check_required_environment_variables() -> List[str]:
    """
    Check for required environment variables and return missing ones.
    
    Returns:
        List[str]: List of missing required environment variables
    """
    required_vars = [
        "DISCORD_TOKEN",
        "DATABASE_URL",
        "DATABASE_SUPABASE_URL", 
        "DATABASE_SUPABASE_PUBLISHABLE_KEY",
        "DATABASE_SUPABASE_SECRET_KEY",
        "API_API_KEY",
        "API_REALM_ID"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    return missing_vars


def print_configuration_summary(settings: Settings) -> None:
    """Print a summary of the current configuration."""
    
    print("=" * 60)
    print("CONFIGURATION SUMMARY")
    print("=" * 60)
    print(f"Environment: {settings.environment.value}")
    print(f"Debug Mode: {settings.debug}")
    print(f"App Version: {settings.app_version}")
    print()
    
    print("Discord Configuration:")
    print(f"  Command Prefix: {settings.discord.command_prefix}")
    print(f"  Sync Commands: {settings.discord.sync_commands}")
    print()
    
    print("Database Configuration:")
    print(f"  Connection Pool: {settings.database.min_connections}-{settings.database.max_connections}")
    print(f"  Timeouts: {settings.database.connection_timeout}s connection, {settings.database.query_timeout}s query")
    print()
    
    print("Cache Configuration:")
    cache_type = "Redis" if settings.cache.redis_url else "Memory Only"
    print(f"  Type: {cache_type}")
    print(f"  Default TTL: {settings.cache.default_ttl}s")
    print()
    
    print("Business Logic:")
    print(f"  Bet Limits: {settings.business.min_bet_amount:,} - {settings.business.max_bet_amount:,} points")
    print(f"  Max Concurrent Bets: {settings.business.max_concurrent_bets}")
    print()
    
    print("Rate Limiting:")
    print(f"  User Requests: {settings.rate_limit.user_requests_per_minute}/min")
    print(f"  User Bets: {settings.rate_limit.user_bets_per_minute}/min")
    print()
    
    print("Logging:")
    print(f"  Level: {settings.logging.level}")
    print(f"  File Logging: {'Enabled' if settings.logging.file_enabled else 'Disabled'}")
    print(f"  JSON Format: {'Enabled' if settings.logging.json_format else 'Disabled'}")
    print("=" * 60)


if __name__ == "__main__":
    """Allow running this module directly to validate configuration."""
    try:
        settings = validate_configuration()
        print("✅ Configuration validation successful!")
        print_configuration_summary(settings)
    except ConfigurationError as e:
        print(f"❌ Configuration validation failed:")
        print(e)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error during configuration validation:")
        print(f"   {e}")
        sys.exit(1)