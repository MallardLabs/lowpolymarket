"""
Rate limiting middleware for Discord commands.

This module provides decorators and middleware for applying rate limits
to Discord commands and interactions.
"""

import asyncio
import functools
from typing import Callable, Optional, List, Union, Any
import logging

import discord
from discord.ext import commands

from core.rate_limiter import get_rate_limiter, RateLimitType, RateLimitInfo
from core.exceptions import RateLimitExceededError


logger = logging.getLogger(__name__)


def rate_limit(
    limit_type: RateLimitType = RateLimitType.USER_REQUESTS,
    error_message: Optional[str] = None,
    include_guild_limit: bool = True
):
    """
    Decorator to apply rate limiting to Discord commands.
    
    Args:
        limit_type: Type of rate limit to apply
        error_message: Custom error message for rate limit exceeded
        include_guild_limit: Whether to also check guild-level limits
        
    Usage:
        @rate_limit(RateLimitType.USER_BETS)
        async def place_bet(ctx, ...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract context from arguments
            ctx = None
            interaction = None
            
            # Handle different command types
            if args and isinstance(args[0], commands.Context):
                ctx = args[0]
            elif args and hasattr(args[0], 'interaction'):
                # Cog method with self as first argument
                if len(args) > 1 and isinstance(args[1], commands.Context):
                    ctx = args[1]
                elif len(args) > 1 and isinstance(args[1], discord.Interaction):
                    interaction = args[1]
            elif args and isinstance(args[0], discord.Interaction):
                interaction = args[0]
            
            # Get user and guild information
            if ctx:
                user_id = ctx.author.id
                guild_id = ctx.guild.id if ctx.guild else None
                user_roles = [role.id for role in ctx.author.roles] if hasattr(ctx.author, 'roles') else None
            elif interaction:
                user_id = interaction.user.id
                guild_id = interaction.guild.id if interaction.guild else None
                user_roles = [role.id for role in interaction.user.roles] if hasattr(interaction.user, 'roles') else None
            else:
                logger.error(f"Could not extract user/guild info from command arguments in {func.__name__}")
                return await func(*args, **kwargs)
            
            # Check rate limit
            rate_limiter = get_rate_limiter()
            
            try:
                # Check user rate limit
                rate_limit_info = await rate_limiter.consume_rate_limit(
                    user_id=user_id,
                    guild_id=guild_id if include_guild_limit else None,
                    limit_type=limit_type,
                    user_roles=user_roles
                )
                
                if rate_limit_info.is_exceeded:
                    # Create error message
                    if error_message:
                        message = error_message
                    else:
                        message = _create_rate_limit_message(limit_type, rate_limit_info)
                    
                    # Send error response
                    if ctx:
                        await ctx.send(message, ephemeral=True)
                    elif interaction:
                        if interaction.response.is_done():
                            await interaction.followup.send(message, ephemeral=True)
                        else:
                            await interaction.response.send_message(message, ephemeral=True)
                    
                    # Log rate limit violation
                    logger.warning(
                        f"Rate limit exceeded for user {user_id} in guild {guild_id} "
                        f"for command {func.__name__} (type: {limit_type})"
                    )
                    
                    # Raise exception for programmatic handling
                    raise RateLimitExceededError(
                        f"Rate limit exceeded for {limit_type}",
                        rate_limit_info=rate_limit_info
                    )
                
                # Execute the original function
                return await func(*args, **kwargs)
                
            except RateLimitExceededError:
                # Re-raise rate limit errors
                raise
            except Exception as e:
                logger.error(f"Error in rate limit middleware for {func.__name__}: {e}")
                # Continue with original function if rate limiting fails
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def _create_rate_limit_message(limit_type: RateLimitType, rate_limit_info: RateLimitInfo) -> str:
    """Create a user-friendly rate limit error message."""
    type_messages = {
        RateLimitType.USER_REQUESTS: "You're making requests too quickly",
        RateLimitType.USER_BETS: "You're placing bets too quickly",
        RateLimitType.USER_PREDICTIONS: "You're creating predictions too quickly",
        RateLimitType.GUILD_REQUESTS: "This server is making requests too quickly",
        RateLimitType.GUILD_PREDICTIONS: "This server is creating predictions too quickly"
    }
    
    base_message = type_messages.get(limit_type, "Rate limit exceeded")
    
    if rate_limit_info.seconds_until_reset > 0:
        if rate_limit_info.seconds_until_reset < 60:
            time_str = f"{rate_limit_info.seconds_until_reset} seconds"
        elif rate_limit_info.seconds_until_reset < 3600:
            time_str = f"{rate_limit_info.seconds_until_reset // 60} minutes"
        else:
            time_str = f"{rate_limit_info.seconds_until_reset // 3600} hours"
        
        return f"⏰ {base_message}. Please try again in {time_str}."
    else:
        return f"⏰ {base_message}. Please try again in a moment."


class RateLimitMiddleware:
    """
    Middleware class for applying rate limits to Discord commands.
    
    This class can be used to add rate limiting to existing commands
    or to create custom rate limiting logic.
    """
    
    def __init__(self):
        self.rate_limiter = get_rate_limiter()
        self.logger = logging.getLogger(__name__)
    
    async def check_rate_limit(
        self,
        user_id: int,
        guild_id: Optional[int] = None,
        limit_type: RateLimitType = RateLimitType.USER_REQUESTS,
        user_roles: Optional[List[int]] = None
    ) -> RateLimitInfo:
        """
        Check rate limit for a user/guild combination.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID (optional)
            limit_type: Type of rate limit to check
            user_roles: List of user role IDs for admin bypass
            
        Returns:
            RateLimitInfo: Rate limit status information
        """
        return await self.rate_limiter.check_rate_limit(
            user_id=user_id,
            guild_id=guild_id,
            limit_type=limit_type,
            user_roles=user_roles
        )
    
    async def consume_rate_limit(
        self,
        user_id: int,
        guild_id: Optional[int] = None,
        limit_type: RateLimitType = RateLimitType.USER_REQUESTS,
        user_roles: Optional[List[int]] = None
    ) -> RateLimitInfo:
        """
        Consume a rate limit slot and return status.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID (optional)
            limit_type: Type of rate limit to consume
            user_roles: List of user role IDs for admin bypass
            
        Returns:
            RateLimitInfo: Rate limit status information after consumption
        """
        return await self.rate_limiter.consume_rate_limit(
            user_id=user_id,
            guild_id=guild_id,
            limit_type=limit_type,
            user_roles=user_roles
        )
    
    async def handle_rate_limit_exceeded(
        self,
        ctx_or_interaction: Union[commands.Context, discord.Interaction],
        limit_type: RateLimitType,
        rate_limit_info: RateLimitInfo,
        custom_message: Optional[str] = None
    ) -> None:
        """
        Handle rate limit exceeded by sending appropriate error message.
        
        Args:
            ctx_or_interaction: Discord context or interaction
            limit_type: Type of rate limit that was exceeded
            rate_limit_info: Rate limit information
            custom_message: Custom error message (optional)
        """
        message = custom_message or _create_rate_limit_message(limit_type, rate_limit_info)
        
        if isinstance(ctx_or_interaction, commands.Context):
            await ctx_or_interaction.send(message, ephemeral=True)
        elif isinstance(ctx_or_interaction, discord.Interaction):
            if ctx_or_interaction.response.is_done():
                await ctx_or_interaction.followup.send(message, ephemeral=True)
            else:
                await ctx_or_interaction.response.send_message(message, ephemeral=True)
    
    def add_admin_user(self, user_id: int) -> None:
        """Add a user to the admin bypass list."""
        self.rate_limiter.add_admin_user(user_id)
    
    def remove_admin_user(self, user_id: int) -> None:
        """Remove a user from the admin bypass list."""
        self.rate_limiter.remove_admin_user(user_id)
    
    def add_admin_role(self, role_id: int) -> None:
        """Add a role to the admin bypass list."""
        self.rate_limiter.add_admin_role(role_id)
    
    def remove_admin_role(self, role_id: int) -> None:
        """Remove a role from the admin bypass list."""
        self.rate_limiter.remove_admin_role(role_id)
    
    def get_statistics(self) -> dict:
        """Get rate limiter statistics."""
        return self.rate_limiter.get_statistics()


# Convenience decorators for common rate limit types
def user_request_limit(error_message: Optional[str] = None):
    """Decorator for general user request rate limiting."""
    return rate_limit(RateLimitType.USER_REQUESTS, error_message)


def user_bet_limit(error_message: Optional[str] = None):
    """Decorator for user bet rate limiting."""
    return rate_limit(RateLimitType.USER_BETS, error_message)


def user_prediction_limit(error_message: Optional[str] = None):
    """Decorator for user prediction creation rate limiting."""
    return rate_limit(RateLimitType.USER_PREDICTIONS, error_message)


def guild_request_limit(error_message: Optional[str] = None):
    """Decorator for guild request rate limiting."""
    return rate_limit(RateLimitType.GUILD_REQUESTS, error_message, include_guild_limit=True)


def guild_prediction_limit(error_message: Optional[str] = None):
    """Decorator for guild prediction creation rate limiting."""
    return rate_limit(RateLimitType.GUILD_PREDICTIONS, error_message, include_guild_limit=True)


# Global middleware instance
_rate_limit_middleware: Optional[RateLimitMiddleware] = None


def get_rate_limit_middleware() -> RateLimitMiddleware:
    """Get the global rate limit middleware instance."""
    global _rate_limit_middleware
    if _rate_limit_middleware is None:
        _rate_limit_middleware = RateLimitMiddleware()
    return _rate_limit_middleware