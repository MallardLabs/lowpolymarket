"""
Discord command validation middleware.

This module provides middleware components for validating Discord interactions,
implementing rate limiting, permission checks, and input sanitization.
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable, Any, Union
from collections import defaultdict, deque
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from .validation import Validator, ValidationResult
from .exceptions import (
    ValidationError,
    RateLimitExceededError,
    InsufficientPermissionsError
)


class RateLimiter:
    """Rate limiting implementation with sliding window algorithm"""
    
    def __init__(self):
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
    
    async def check_rate_limit(self, key: str, limit: int, window_seconds: int) -> bool:
        """
        Check if request is within rate limit
        
        Args:
            key: Unique identifier for rate limiting (e.g., user_id:command)
            limit: Maximum requests allowed
            window_seconds: Time window in seconds
            
        Returns:
            True if request is allowed, False if rate limited
        """
        now = time.time()
        
        # Cleanup old entries periodically
        if now - self.last_cleanup > self.cleanup_interval:
            await self._cleanup_old_entries()
            self.last_cleanup = now
        
        # Get request history for this key
        request_times = self.requests[key]
        
        # Remove requests outside the window
        cutoff_time = now - window_seconds
        while request_times and request_times[0] < cutoff_time:
            request_times.popleft()
        
        # Check if limit exceeded
        if len(request_times) >= limit:
            return False
        
        # Add current request
        request_times.append(now)
        return True
    
    async def _cleanup_old_entries(self):
        """Remove old rate limit entries to prevent memory leaks"""
        now = time.time()
        keys_to_remove = []
        
        for key, request_times in self.requests.items():
            # Remove requests older than 1 hour
            cutoff_time = now - 3600
            while request_times and request_times[0] < cutoff_time:
                request_times.popleft()
            
            # Remove empty entries
            if not request_times:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.requests[key]
    
    def get_remaining_time(self, key: str, window_seconds: int) -> int:
        """Get remaining time until rate limit resets"""
        request_times = self.requests.get(key, deque())
        if not request_times:
            return 0
        
        oldest_request = request_times[0]
        reset_time = oldest_request + window_seconds
        remaining = max(0, reset_time - time.time())
        return int(remaining)


class PermissionChecker:
    """Permission validation for Discord commands"""
    
    @staticmethod
    def has_admin_permissions(interaction: discord.Interaction) -> bool:
        """Check if user has administrator permissions"""
        return interaction.user.guild_permissions.administrator
    
    @staticmethod
    def has_moderator_permissions(interaction: discord.Interaction, 
                                moderator_roles: List[int] = None) -> bool:
        """Check if user has moderator permissions"""
        if PermissionChecker.has_admin_permissions(interaction):
            return True
        
        if moderator_roles:
            user_roles = {role.id for role in interaction.user.roles}
            return bool(user_roles.intersection(set(moderator_roles)))
        
        # Default moderator permissions
        return (interaction.user.guild_permissions.manage_messages or
                interaction.user.guild_permissions.manage_guild)
    
    @staticmethod
    def has_creator_permissions(interaction: discord.Interaction,
                              creator_roles: List[int] = None) -> bool:
        """Check if user can create predictions"""
        if PermissionChecker.has_admin_permissions(interaction):
            return True
        
        if creator_roles:
            user_roles = {role.id for role in interaction.user.roles}
            return bool(user_roles.intersection(set(creator_roles)))
        
        # Default: moderators can create
        return PermissionChecker.has_moderator_permissions(interaction)
    
    @staticmethod
    def can_use_command(interaction: discord.Interaction, 
                       required_permissions: List[str] = None) -> bool:
        """Check if user can use a specific command"""
        if not interaction.guild:
            return False
        
        if PermissionChecker.has_admin_permissions(interaction):
            return True
        
        if not required_permissions:
            return True
        
        user_perms = interaction.user.guild_permissions
        for perm_name in required_permissions:
            if not hasattr(user_perms, perm_name) or not getattr(user_perms, perm_name):
                return False
        
        return True


class ValidationMiddleware:
    """Main validation middleware for Discord commands"""
    
    def __init__(self, rate_limiter: RateLimiter = None):
        self.rate_limiter = rate_limiter or RateLimiter()
        self.validator = Validator()
        self.permission_checker = PermissionChecker()
    
    def validate_command(
        self,
        rate_limit_config: Dict[str, Any] = None,
        permission_config: Dict[str, Any] = None,
        input_validation: Dict[str, Callable] = None,
        sanitize_inputs: bool = True
    ):
        """
        Comprehensive command validation decorator
        
        Args:
            rate_limit_config: Rate limiting configuration
                - limit: Maximum requests per window
                - window: Time window in seconds
                - per_user: Whether to apply per user (default: True)
                - per_guild: Whether to apply per guild (default: False)
            
            permission_config: Permission configuration
                - required_permissions: List of required Discord permissions
                - admin_only: Whether command is admin only
                - moderator_only: Whether command is moderator only
                - creator_only: Whether command is creator only
                - custom_check: Custom permission check function
            
            input_validation: Dictionary mapping parameter names to validation functions
            sanitize_inputs: Whether to sanitize string inputs
        """
        def decorator(func):
            async def wrapper(cog_self, interaction: discord.Interaction, *args, **kwargs):
                try:
                    # 1. Rate Limiting
                    if rate_limit_config:
                        await self._check_rate_limits(interaction, func.__name__, rate_limit_config)
                    
                    # 2. Permission Validation
                    if permission_config:
                        await self._check_permissions(interaction, permission_config)
                    
                    # 3. Input Validation and Sanitization
                    if input_validation or sanitize_inputs:
                        args, kwargs = await self._validate_inputs(
                            func, args, kwargs, input_validation, sanitize_inputs
                        )
                    
                    # 4. Execute the command
                    return await func(cog_self, interaction, *args, **kwargs)
                
                except ValidationError as e:
                    await self._handle_validation_error(interaction, e)
                except RateLimitExceededError as e:
                    await self._handle_rate_limit_error(interaction, e)
                except InsufficientPermissionsError as e:
                    await self._handle_permission_error(interaction, e)
                except Exception as e:
                    await self._handle_generic_error(interaction, e)
            
            return wrapper
        return decorator
    
    async def _check_rate_limits(self, interaction: discord.Interaction, 
                               command_name: str, config: Dict[str, Any]):
        """Check rate limits for the command"""
        limit = config.get('limit', 10)
        window = config.get('window', 60)
        per_user = config.get('per_user', True)
        per_guild = config.get('per_guild', False)
        
        if per_user:
            key = f"{command_name}:user:{interaction.user.id}"
            if not await self.rate_limiter.check_rate_limit(key, limit, window):
                remaining = self.rate_limiter.get_remaining_time(key, window)
                raise RateLimitExceededError(
                    user_id=interaction.user.id,
                    limit=limit,
                    window_seconds=window,
                    details={"remaining_seconds": remaining}
                )
        
        if per_guild and interaction.guild:
            key = f"{command_name}:guild:{interaction.guild.id}"
            guild_limit = config.get('guild_limit', limit * 10)
            if not await self.rate_limiter.check_rate_limit(key, guild_limit, window):
                remaining = self.rate_limiter.get_remaining_time(key, window)
                raise RateLimitExceededError(
                    user_id=interaction.user.id,
                    limit=guild_limit,
                    window_seconds=window,
                    details={"remaining_seconds": remaining, "type": "guild_limit"}
                )
    
    async def _check_permissions(self, interaction: discord.Interaction, 
                               config: Dict[str, Any]):
        """Check user permissions for the command"""
        if config.get('admin_only') and not self.permission_checker.has_admin_permissions(interaction):
            raise InsufficientPermissionsError(
                user_id=interaction.user.id,
                required_permission="administrator"
            )
        
        if config.get('moderator_only') and not self.permission_checker.has_moderator_permissions(interaction):
            raise InsufficientPermissionsError(
                user_id=interaction.user.id,
                required_permission="moderator"
            )
        
        if config.get('creator_only') and not self.permission_checker.has_creator_permissions(interaction):
            raise InsufficientPermissionsError(
                user_id=interaction.user.id,
                required_permission="creator"
            )
        
        required_perms = config.get('required_permissions', [])
        if required_perms and not self.permission_checker.can_use_command(interaction, required_perms):
            raise InsufficientPermissionsError(
                user_id=interaction.user.id,
                required_permission=', '.join(required_perms)
            )
        
        custom_check = config.get('custom_check')
        if custom_check and not await custom_check(interaction):
            raise InsufficientPermissionsError(
                user_id=interaction.user.id,
                required_permission="custom_check"
            )
    
    async def _validate_inputs(self, func: Callable, args: tuple, kwargs: dict,
                             validation_config: Dict[str, Callable] = None,
                             sanitize_inputs: bool = True) -> tuple:
        """Validate and sanitize function inputs"""
        # Get parameter names
        param_names = list(func.__code__.co_varnames[:func.__code__.co_argcount])
        
        # Skip 'self' and 'interaction' parameters
        if param_names and param_names[0] == 'self':
            param_names = param_names[1:]
        if param_names and param_names[0] == 'interaction':
            param_names = param_names[1:]
        
        # Create parameter mapping
        params = dict(zip(param_names, args))
        params.update(kwargs)
        
        validation_errors = []
        sanitized_params = {}
        
        # Apply custom validation
        if validation_config:
            for param_name, validator_func in validation_config.items():
                if param_name in params:
                    try:
                        result = validator_func(params[param_name])
                        if isinstance(result, ValidationResult):
                            if result.has_errors():
                                validation_errors.extend([
                                    f"{param_name}: {error}" for error in result.errors
                                ])
                            else:
                                sanitized_params[param_name] = (
                                    result.sanitized_data 
                                    if result.sanitized_data is not None 
                                    else params[param_name]
                                )
                        else:
                            sanitized_params[param_name] = result
                    except Exception as e:
                        validation_errors.append(f"{param_name}: {str(e)}")
        
        # Apply input sanitization
        if sanitize_inputs:
            for param_name, value in params.items():
                if param_name not in sanitized_params and isinstance(value, str):
                    sanitized_params[param_name] = self.validator.sanitize_text(value)
        
        if validation_errors:
            raise ValidationError(
                "Input validation failed",
                details={"validation_errors": validation_errors}
            )
        
        # Update args and kwargs with sanitized values
        new_args = list(args)
        for i, param_name in enumerate(param_names[:len(args)]):
            if param_name in sanitized_params:
                new_args[i] = sanitized_params[param_name]
        
        new_kwargs = kwargs.copy()
        for param_name, value in sanitized_params.items():
            if param_name in kwargs:
                new_kwargs[param_name] = value
        
        return tuple(new_args), new_kwargs
    
    async def _handle_validation_error(self, interaction: discord.Interaction, 
                                     error: ValidationError):
        """Handle validation errors"""
        message = f"❌ **Validation Error**\n{str(error)}"
        
        if error.details and 'validation_errors' in error.details:
            errors = error.details['validation_errors'][:5]  # Limit to 5 errors
            message += "\n\n**Issues:**\n" + "\n".join(f"• {err}" for err in errors)
        
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    
    async def _handle_rate_limit_error(self, interaction: discord.Interaction,
                                     error: RateLimitExceededError):
        """Handle rate limit errors"""
        message = f"⏰ **Rate Limited**\n{error.user_message}"
        
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    
    async def _handle_permission_error(self, interaction: discord.Interaction,
                                     error: InsufficientPermissionsError):
        """Handle permission errors"""
        message = f"🔒 **Insufficient Permissions**\n{error.user_message}"
        
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    
    async def _handle_generic_error(self, interaction: discord.Interaction, error: Exception):
        """Handle generic errors"""
        message = "❌ An unexpected error occurred while processing your command."
        
        # Log the error if logger is available
        if hasattr(self, 'logger'):
            self.logger.error(f"Command error in {interaction.command}: {str(error)}")
        
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


# Convenience decorators for common validation patterns
def rate_limit(limit: int = 10, window: int = 60, per_user: bool = True, per_guild: bool = False):
    """Rate limiting decorator"""
    middleware = ValidationMiddleware()
    return middleware.validate_command(
        rate_limit_config={
            'limit': limit,
            'window': window,
            'per_user': per_user,
            'per_guild': per_guild
        }
    )


def require_permissions(*permissions):
    """Permission requirement decorator"""
    middleware = ValidationMiddleware()
    return middleware.validate_command(
        permission_config={'required_permissions': list(permissions)}
    )


def admin_only():
    """Admin only decorator"""
    middleware = ValidationMiddleware()
    return middleware.validate_command(
        permission_config={'admin_only': True}
    )


def moderator_only():
    """Moderator only decorator"""
    middleware = ValidationMiddleware()
    return middleware.validate_command(
        permission_config={'moderator_only': True}
    )


def creator_only():
    """Creator only decorator"""
    middleware = ValidationMiddleware()
    return middleware.validate_command(
        permission_config={'creator_only': True}
    )


def validate_inputs(**validators):
    """Input validation decorator"""
    middleware = ValidationMiddleware()
    return middleware.validate_command(
        input_validation=validators,
        sanitize_inputs=True
    )


def sanitize_all_inputs():
    """Sanitize all string inputs decorator"""
    middleware = ValidationMiddleware()
    return middleware.validate_command(sanitize_inputs=True)