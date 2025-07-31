"""
Core module for the Discord Prediction Market Bot.

This module provides the foundational components for dependency injection,
service management, rate limiting, and application lifecycle.
"""

from .container import DIContainer, ServiceLifecycle
from .exceptions import (
    DIContainerError,
    ServiceNotFoundError,
    ServiceRegistrationError,
    CircularDependencyError,
    RateLimitExceededError
)
from .rate_limiter import (
    RateLimiter,
    RateLimitType,
    RateLimitInfo,
    get_rate_limiter,
    shutdown_rate_limiter
)
from .rate_limit_middleware import (
    rate_limit,
    user_request_limit,
    user_bet_limit,
    user_prediction_limit,
    guild_request_limit,
    guild_prediction_limit,
    get_rate_limit_middleware
)

__all__ = [
    # Dependency Injection
    "DIContainer",
    "ServiceLifecycle",
    
    # Exceptions
    "DIContainerError",
    "ServiceNotFoundError",
    "ServiceRegistrationError",
    "CircularDependencyError",
    "RateLimitExceededError",
    
    # Rate Limiting
    "RateLimiter",
    "RateLimitType",
    "RateLimitInfo",
    "get_rate_limiter",
    "shutdown_rate_limiter",
    
    # Rate Limiting Middleware
    "rate_limit",
    "user_request_limit",
    "user_bet_limit",
    "user_prediction_limit",
    "guild_request_limit",
    "guild_prediction_limit",
    "get_rate_limit_middleware"
]