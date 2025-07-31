"""
Test commands demonstrating the complete architecture.

This module shows how to use:
- Dependency injection
- Structured logging with correlation IDs
- Error handling
- Input validation
- Rate limiting
- Security checks
"""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from core.container import get_container
from core.logging_manager import get_logger, set_correlation_id, log_function_call
from core.error_handler import get_error_handler, handle_errors
from core.rate_limiter import RateLimiter
from core.security import SecurityManager
from core.validation import validate_input, ValidationRule
from core.exceptions import ValidationError, RateLimitExceededError
from models.schemas import UserBalanceRequest, UserBalanceResponse
from helpers.SimplePointsManager import PointsManagerSingleton


class TestCommands(commands.Cog):
    """Test commands showcasing the complete architecture."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_logger("TestCommands")
        
        # Get services from DI container
        self.container = get_container()
        
        # These will be resolved when first accessed
        self._rate_limiter: Optional[RateLimiter] = None
        self._security_manager: Optional[SecurityManager] = None
        self._points_manager: Optional[PointsManagerSingleton] = None
        self._error_handler = get_error_handler()
    
    @property
    async def rate_limiter(self) -> RateLimiter:
        """Get rate limiter from DI container."""
        if self._rate_limiter is None:
            self._rate_limiter = await self.container.get_service(RateLimiter)
        return self._rate_limiter
    
    @property
    async def security_manager(self) -> SecurityManager:
        """Get security manager from DI container."""
        if self._security_manager is None:
            self._security_manager = await self.container.get_service(SecurityManager)
        return self._security_manager
    
    @property
    async def points_manager(self) -> PointsManagerSingleton:
        """Get points manager from DI container."""
        if self._points_manager is None:
            self._points_manager = await self.container.get_service(PointsManagerSingleton)
        return self._points_manager
    
    @app_commands.command(
        name="test-balance",
        description="Test command to check your balance (demonstrates full architecture)"
    )
    @handle_errors(interaction_error=True, log_errors=True)
    @log_function_call(include_args=True, include_result=True)
    async def test_balance(self, interaction: discord.Interaction) -> None:
        """
        Test command that demonstrates:
        - Correlation ID tracking
        - Rate limiting
        - Input validation
        - Security checks
        - Error handling
        - Structured logging
        - Service injection
        """
        # Set correlation ID for this interaction
        correlation_id = set_correlation_id()
        
        self.logger.info(
            f"Balance check requested by {interaction.user}",
            extra={
                'user_id': interaction.user.id,
                'guild_id': interaction.guild.id if interaction.guild else None,
                'correlation_id': correlation_id
            }
        )
        
        try:
            # 1. Rate limiting check
            rate_limiter = await self.rate_limiter
            if not await rate_limiter.check_rate_limit(f"user:{interaction.user.id}", "balance_check"):
                raise RateLimitExceededError(
                    resource="balance_check",
                    user_message="You're checking your balance too frequently. Please wait a moment."
                )
            
            # 2. Security validation
            security_manager = await self.security_manager
            if not await security_manager.validate_user_interaction(interaction):
                self.logger.warning(
                    f"Security validation failed for user {interaction.user.id}",
                    extra={'user_id': interaction.user.id, 'correlation_id': correlation_id}
                )
                await interaction.response.send_message(
                    "❌ Security validation failed. Please try again.",
                    ephemeral=True
                )
                return
            
            # 3. Input validation using Pydantic
            try:
                balance_request = UserBalanceRequest(
                    user_id=str(interaction.user.id),
                    guild_id=str(interaction.guild.id) if interaction.guild else None
                )
                
                # Additional validation rules
                validate_input(
                    balance_request.user_id,
                    [
                        ValidationRule.required(),
                        ValidationRule.min_length(1),
                        ValidationRule.max_length(20),
                        ValidationRule.pattern(r'^\d+$', "User ID must be numeric")
                    ]
                )
                
            except Exception as e:
                raise ValidationError(
                    field="user_id",
                    message="Invalid user ID format",
                    user_message="There was an issue with your request. Please try again."
                )
            
            # 4. Business logic - get balance from points manager
            await interaction.response.defer(ephemeral=True)
            
            points_manager = await self.points_manager
            
            try:
                balance_data = await points_manager.get_user_balance(interaction.user.id)
                
                # Create response model
                balance_response = UserBalanceResponse(
                    user_id=str(interaction.user.id),
                    balance=balance_data.get('balance', 0),
                    currency_name=balance_data.get('currency', 'points'),
                    last_updated=balance_data.get('last_updated')
                )
                
                # 5. Create success response
                embed = discord.Embed(
                    title="💰 Your Balance",
                    description=f"You have **{balance_response.balance:,}** {balance_response.currency_name}",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="📊 Details",
                    value=f"User ID: `{balance_response.user_id}`\nCorrelation ID: `{correlation_id}`",
                    inline=False
                )
                
                if balance_response.last_updated:
                    embed.add_field(
                        name="🕒 Last Updated",
                        value=balance_response.last_updated,
                        inline=True
                    )
                
                embed.set_footer(text="✅ All systems operational")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                self.logger.info(
                    f"Balance check completed successfully for user {interaction.user.id}",
                    extra={
                        'user_id': interaction.user.id,
                        'balance': balance_response.balance,
                        'correlation_id': correlation_id
                    }
                )
                
            except Exception as e:
                self.logger.error(
                    f"Failed to fetch balance for user {interaction.user.id}: {e}",
                    extra={'user_id': interaction.user.id, 'correlation_id': correlation_id}
                )
                
                # Fallback response
                embed = discord.Embed(
                    title="💰 Your Balance",
                    description="**1,000** points (demo mode)",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name="ℹ️ Note",
                    value="This is a demo response. The points system is not fully configured yet.",
                    inline=False
                )
                
                embed.add_field(
                    name="🔧 Debug Info",
                    value=f"Correlation ID: `{correlation_id}`",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            # This will be handled by the @handle_errors decorator
            raise
    
    @app_commands.command(
        name="test-error",
        description="Test command that intentionally triggers an error (for testing error handling)"
    )
    @handle_errors(interaction_error=True, log_errors=True)
    async def test_error(self, interaction: discord.Interaction, error_type: str = "validation") -> None:
        """Test different types of errors."""
        correlation_id = set_correlation_id()
        
        self.logger.info(
            f"Error test requested by {interaction.user} (type: {error_type})",
            extra={
                'user_id': interaction.user.id,
                'error_type': error_type,
                'correlation_id': correlation_id
            }
        )
        
        if error_type == "validation":
            raise ValidationError(
                field="test_field",
                message="This is a test validation error",
                user_message="❌ Invalid input provided. This is just a test!"
            )
        elif error_type == "rate_limit":
            raise RateLimitExceededError(
                resource="test_command",
                user_message="🚦 You're using test commands too quickly!"
            )
        else:
            # Generic error
            raise Exception("This is a test exception to demonstrate error handling")
    
    @app_commands.command(
        name="test-logs",
        description="Test command to demonstrate structured logging"
    )
    async def test_logs(self, interaction: discord.Interaction) -> None:
        """Demonstrate different log levels and structured logging."""
        correlation_id = set_correlation_id()
        
        # Log at different levels
        self.logger.debug("Debug message", extra={'correlation_id': correlation_id})
        self.logger.info("Info message", extra={'correlation_id': correlation_id})
        self.logger.warning("Warning message", extra={'correlation_id': correlation_id})
        
        # Log with structured data
        self.logger.info(
            "Structured log example",
            extra={
                'user_id': interaction.user.id,
                'guild_id': interaction.guild.id if interaction.guild else None,
                'command': 'test-logs',
                'correlation_id': correlation_id,
                'custom_data': {
                    'test_field': 'test_value',
                    'number_field': 42,
                    'boolean_field': True
                }
            }
        )
        
        await interaction.response.send_message(
            f"✅ Logs generated! Check your log files or console.\n"
            f"🔍 Correlation ID: `{correlation_id}`",
            ephemeral=True
        )
    
    @app_commands.command(
        name="system-status",
        description="Check the status of all bot systems"
    )
    async def system_status(self, interaction: discord.Interaction) -> None:
        """Show system status and health checks."""
        correlation_id = set_correlation_id()
        
        await interaction.response.defer(ephemeral=True)
        
        # Check various systems
        embed = discord.Embed(
            title="🔧 System Status",
            color=discord.Color.blue()
        )
        
        # DI Container status
        try:
            container = get_container()
            services = container.get_registered_services()
            embed.add_field(
                name="📦 Dependency Injection",
                value=f"✅ Active ({len(services)} services registered)",
                inline=True
            )
        except Exception as e:
            embed.add_field(
                name="📦 Dependency Injection",
                value=f"❌ Error: {str(e)[:50]}...",
                inline=True
            )
        
        # Rate Limiter status
        try:
            rate_limiter = await self.rate_limiter
            embed.add_field(
                name="🚦 Rate Limiter",
                value="✅ Active",
                inline=True
            )
        except Exception as e:
            embed.add_field(
                name="🚦 Rate Limiter",
                value=f"❌ Error: {str(e)[:50]}...",
                inline=True
            )
        
        # Security Manager status
        try:
            security_manager = await self.security_manager
            embed.add_field(
                name="🔒 Security Manager",
                value="✅ Active",
                inline=True
            )
        except Exception as e:
            embed.add_field(
                name="🔒 Security Manager",
                value=f"❌ Error: {str(e)[:50]}...",
                inline=True
            )
        
        # Error Handler status
        try:
            error_stats = self._error_handler.get_error_statistics()
            embed.add_field(
                name="⚠️ Error Handler",
                value=f"✅ Active ({error_stats['total_errors']} total errors)",
                inline=True
            )
        except Exception as e:
            embed.add_field(
                name="⚠️ Error Handler",
                value=f"❌ Error: {str(e)[:50]}...",
                inline=True
            )
        
        # Logging status
        embed.add_field(
            name="📝 Logging System",
            value="✅ Active",
            inline=True
        )
        
        embed.add_field(
            name="🔍 Correlation ID",
            value=f"`{correlation_id}`",
            inline=False
        )
        
        embed.set_footer(text="System health check completed")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        self.logger.info(
            "System status check completed",
            extra={
                'user_id': interaction.user.id,
                'correlation_id': correlation_id
            }
        )


async def setup(bot: commands.Bot) -> None:
    """Set up the cog."""
    await bot.add_cog(TestCommands(bot))