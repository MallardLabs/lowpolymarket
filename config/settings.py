"""
Centralized configuration management using Pydantic BaseSettings.

This module provides type-safe configuration loading with validation
and support for different environments (dev, staging, prod).
"""

import os
from enum import Enum
from functools import lru_cache
from typing import Optional, List
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Supported environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class DiscordSettings(BaseSettings):
    """Discord bot configuration settings."""
    
    token: str = Field(..., description="Discord bot token")
    command_prefix: str = Field("!", description="Bot command prefix")
    sync_commands: bool = Field(True, description="Whether to sync slash commands on startup")
    
    @field_validator('token')
    @classmethod
    def validate_token(cls, v):
        if not v or len(v) < 50:
            raise ValueError("Discord token must be provided and be at least 50 characters long")
        return v
    
    model_config = SettingsConfigDict(env_prefix="DISCORD_")


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    url: str = Field(..., description="Database connection URL")
    supabase_url: str = Field(..., description="Supabase project URL")
    
    # Supabase API Keys (New format - June 2025+)
    supabase_publishable_key: str = Field(..., description="Supabase publishable key (sb_publishable_...)")
    supabase_secret_key: str = Field(..., description="Supabase secret key (sb_secret_...)")
    
    # JWT Secret (optional for enhanced security)
    supabase_jwt_secret: Optional[str] = Field(None, description="Supabase JWT secret for enhanced security")
    
    # Connection pool settings
    min_connections: int = Field(5, description="Minimum database connections in pool")
    max_connections: int = Field(20, description="Maximum database connections in pool")
    connection_timeout: int = Field(30, description="Database connection timeout in seconds")
    query_timeout: int = Field(30, description="Database query timeout in seconds")
    
    @field_validator('url')
    @classmethod
    def validate_database_url(cls, v):
        if not v.startswith(('postgresql://', 'postgres://')):
            raise ValueError("Database URL must be a valid PostgreSQL connection string")
        return v
    
    @field_validator('supabase_url')
    @classmethod
    def validate_supabase_url(cls, v):
        if not v.startswith('https://'):
            raise ValueError("Supabase URL must be a valid HTTPS URL")
        return v
    
    @field_validator('supabase_publishable_key')
    @classmethod
    def validate_publishable_key(cls, v):
        if not v.startswith('sb_publishable_'):
            raise ValueError("Supabase publishable key must start with 'sb_publishable_'")
        return v
    
    @field_validator('supabase_secret_key')
    @classmethod
    def validate_secret_key(cls, v):
        if not v.startswith('sb_secret_'):
            raise ValueError("Supabase secret key must start with 'sb_secret_'")
        return v
    
    model_config = SettingsConfigDict(env_prefix="DATABASE_")


class CacheSettings(BaseSettings):
    """Cache configuration settings."""
    
    # Redis settings
    redis_url: Optional[str] = Field(None, description="Redis connection URL for distributed caching")
    redis_password: Optional[str] = Field(None, description="Redis password")
    redis_db: int = Field(0, description="Redis database number")
    
    # Cache TTL settings (in seconds)
    default_ttl: int = Field(300, description="Default cache TTL in seconds")
    prediction_ttl: int = Field(300, description="Prediction data cache TTL")
    market_data_ttl: int = Field(60, description="Market data cache TTL")
    user_balance_ttl: int = Field(180, description="User balance cache TTL")
    
    # Memory cache settings
    max_memory_cache_size: int = Field(1000, description="Maximum number of items in memory cache")
    memory_cache_ttl: int = Field(60, description="Memory cache TTL in seconds")
    
    @field_validator('redis_url')
    @classmethod
    def validate_redis_url(cls, v):
        if v and not v.startswith(('redis://', 'rediss://')):
            raise ValueError("Redis URL must be a valid Redis connection string")
        return v
    
    model_config = SettingsConfigDict(env_prefix="CACHE_")


class BusinessLogicSettings(BaseSettings):
    """Business logic configuration settings."""
    
    # Betting limits
    max_bet_amount: int = Field(1_000_000, description="Maximum bet amount in points")
    min_bet_amount: int = Field(1, description="Minimum bet amount in points")
    
    # Prediction settings
    max_prediction_duration_hours: int = Field(720, description="Maximum prediction duration in hours (30 days)")
    min_prediction_duration_minutes: int = Field(5, description="Minimum prediction duration in minutes")
    auto_refund_hours: int = Field(120, description="Hours after which unresolved predictions are auto-refunded")
    
    # Resolution settings
    min_resolution_votes: int = Field(2, description="Minimum votes required to resolve a prediction")
    resolution_timeout_hours: int = Field(24, description="Hours to wait for resolution votes")
    
    # Market maker settings
    initial_liquidity: int = Field(1000, description="Initial liquidity for new predictions")
    k_constant: int = Field(1000000, description="Constant product AMM k value")
    
    # Limits
    max_concurrent_bets: int = Field(50, description="Maximum concurrent bet operations")
    max_predictions_per_guild: int = Field(100, description="Maximum active predictions per guild")
    max_options_per_prediction: int = Field(10, description="Maximum options per prediction")
    
    @field_validator('max_bet_amount')
    @classmethod
    def validate_max_bet_amount(cls, v):
        if v <= 0:
            raise ValueError("Maximum bet amount must be positive")
        return v
    
    @field_validator('min_bet_amount')
    @classmethod
    def validate_min_bet_amount(cls, v):
        if v <= 0:
            raise ValueError("Minimum bet amount must be positive")
        return v
    
    @model_validator(mode='after')
    def validate_bet_amounts(self):
        if self.min_bet_amount >= self.max_bet_amount:
            raise ValueError("Minimum bet amount must be less than maximum bet amount")
        return self
    
    model_config = SettingsConfigDict(env_prefix="BUSINESS_")


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration settings."""
    
    # Per-user rate limits
    user_requests_per_minute: int = Field(10, description="Requests per user per minute")
    user_bets_per_minute: int = Field(5, description="Bets per user per minute")
    user_predictions_per_hour: int = Field(3, description="Predictions per user per hour")
    
    # Per-guild rate limits
    guild_requests_per_minute: int = Field(100, description="Requests per guild per minute")
    guild_predictions_per_hour: int = Field(10, description="Predictions per guild per hour")
    
    # Rate limit window settings
    rate_limit_window_seconds: int = Field(60, description="Rate limit window in seconds")
    rate_limit_cleanup_interval: int = Field(300, description="Rate limit cleanup interval in seconds")
    
    # Bypass settings
    admin_bypass_enabled: bool = Field(True, description="Allow admins to bypass rate limits")
    
    model_config = SettingsConfigDict(env_prefix="RATE_LIMIT_")


class DripApiSettings(BaseSettings):
    """DRIP API configuration settings (existing points system)."""
    
    base_url: str = Field("https://api.drip.re", description="DRIP API base URL")
    api_key: str = Field(..., description="DRIP API key")
    realm_id: str = Field(..., description="DRIP realm ID")
    
    # API settings
    timeout: int = Field(30, description="API request timeout in seconds")
    max_retries: int = Field(3, description="Maximum API request retries")
    retry_delay: float = Field(1.0, description="Base delay between retries in seconds")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v):
        if not v:
            raise ValueError("DRIP API key must be provided")
        return v
    
    @field_validator('realm_id')
    @classmethod
    def validate_realm_id(cls, v):
        if not v:
            raise ValueError("DRIP realm ID must be provided")
        return v
    
    model_config = SettingsConfigDict(env_prefix="API_")


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""
    
    level: str = Field("INFO", description="Logging level")
    format: str = Field(
        "[{asctime}] [{levelname:<8}] {name}: {message}",
        description="Log message format"
    )
    date_format: str = Field("%Y-%m-%d %H:%M:%S", description="Log date format")
    
    # File logging
    file_enabled: bool = Field(True, description="Enable file logging")
    file_path: str = Field("logs/discord.log", description="Log file path")
    file_max_bytes: int = Field(10_000_000, description="Maximum log file size in bytes")
    file_backup_count: int = Field(5, description="Number of backup log files to keep")
    
    # Console logging
    console_enabled: bool = Field(True, description="Enable console logging")
    console_colors: bool = Field(True, description="Enable colored console output")
    
    # Structured logging
    json_format: bool = Field(False, description="Use JSON format for logs")
    include_extra_fields: bool = Field(True, description="Include extra fields in logs")
    
    # Correlation ID settings
    auto_correlation_id: bool = Field(True, description="Automatically generate correlation IDs")
    correlation_id_header: str = Field("X-Correlation-ID", description="HTTP header for correlation ID")
    
    # Performance logging
    log_slow_queries: bool = Field(True, description="Log slow database queries")
    slow_query_threshold: float = Field(1.0, description="Threshold in seconds for slow query logging")
    log_function_calls: bool = Field(False, description="Log function entry/exit (debug mode)")
    
    # Log rotation settings
    rotation_when: str = Field("midnight", description="When to rotate logs (midnight, H, D, W0-W6)")
    rotation_interval: int = Field(1, description="Rotation interval")
    rotation_backup_count: int = Field(30, description="Number of rotated log files to keep")
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v.upper()
    
    model_config = SettingsConfigDict(env_prefix="LOG_")


class Settings(BaseSettings):
    """Main application settings combining all configuration sections."""
    
    # Environment
    environment: Environment = Field(Environment.DEVELOPMENT, description="Application environment")
    debug: bool = Field(False, description="Enable debug mode")
    
    # Component settings
    discord: DiscordSettings = Field(default_factory=DiscordSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    business: BusinessLogicSettings = Field(default_factory=BusinessLogicSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    drip_api: DripApiSettings = Field(default_factory=DripApiSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    
    # Application metadata
    app_name: str = Field("Discord Prediction Market Bot", description="Application name")
    app_version: str = Field("2.0.0", description="Application version")
    
    @field_validator('environment', mode='before')
    @classmethod
    def validate_environment(cls, v):
        if isinstance(v, str):
            try:
                return Environment(v.lower())
            except ValueError:
                raise ValueError(f"Environment must be one of: {', '.join([e.value for e in Environment])}")
        return v
    
    @model_validator(mode='after')
    def validate_production_settings(self):
        """Additional validation for production environment."""
        if self.environment == Environment.PRODUCTION:
            # Ensure debug is disabled in production
            if self.debug:
                raise ValueError("Debug mode must be disabled in production")
            
            # Ensure secure settings in production
            if len(self.discord.token) < 50:
                raise ValueError("Production requires a valid Discord token")
        
        return self
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings with caching.
    
    This function creates and caches the Settings instance to avoid
    repeated environment variable parsing and validation.
    
    Returns:
        Settings: The application settings instance
        
    Raises:
        ValidationError: If configuration validation fails
    """
    try:
        return Settings()
    except Exception as e:
        # Provide clear error messages for configuration issues
        error_msg = f"Configuration validation failed: {str(e)}"
        
        # Add helpful hints for common issues
        if "DISCORD_TOKEN" in str(e):
            error_msg += "\nHint: Make sure DISCORD_TOKEN is set in your .env file"
        elif "DATABASE_URL" in str(e):
            error_msg += "\nHint: Make sure DATABASE_URL is set with a valid PostgreSQL connection string"
        elif "API_KEY" in str(e):
            error_msg += "\nHint: Make sure API_KEY and REALM_ID are set for DRIP API integration"
        
        raise ValueError(error_msg) from e


# Settings instance will be created when needed
# Use get_settings() to access the settings instance