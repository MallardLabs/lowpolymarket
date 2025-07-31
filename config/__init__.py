"""
Configuration module for the Discord Prediction Market Bot.

This module provides centralized configuration management using Pydantic BaseSettings
with support for environment-specific configurations and validation.
"""

from .settings import (
    Settings, 
    get_settings,
    Environment,
    DiscordSettings,
    DatabaseSettings,
    CacheSettings,
    BusinessLogicSettings,
    RateLimitSettings,
    DripApiSettings,
    LoggingSettings
)
from .validation import (
    validate_configuration,
    ConfigurationError,
    check_required_environment_variables,
    print_configuration_summary
)

__all__ = [
    # Main settings
    "Settings", 
    "get_settings",
    "Environment",
    
    # Component settings
    "DiscordSettings",
    "DatabaseSettings", 
    "CacheSettings",
    "BusinessLogicSettings",
    "RateLimitSettings",
    "DripApiSettings",
    "LoggingSettings",
    
    # Validation utilities
    "validate_configuration",
    "ConfigurationError",
    "check_required_environment_variables",
    "print_configuration_summary"
]