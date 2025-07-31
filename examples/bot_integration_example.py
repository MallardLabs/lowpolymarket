"""
Example of integrating the structured logging system with Discord bot components.

This example shows how to use the logging system in Discord cogs and commands.
"""

import asyncio
import discord
from discord.ext import commands
from typing import Optional

from core.logging_manager import (
    LoggingManager,
    get_logger,
    set_correlation_id,
    log_function_call,
    log_performance,
    LogContext
)
from config.settings import LoggingSettings


class ExampleCog(commands.Cog):
    """Example cog demonstrating structured logging usage."""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)
        
        # Initialize logging manager with settings
        self.logging_settings = LoggingSettings(
            level="INFO",
            file_enabled=True,
            file_path="logs/bot_example.log",
            console_enabled=True,
            json_format=True,
            include_extra_fields=True
        )
        self.logging_manager = LoggingManager(self.logging_settings)
    
    @commands.slash_command(name="create_prediction", description="Create a new prediction market")
    @log_function_call(include_args=True, include_duration=True)
    async def create_prediction(
        self,
        ctx: discord.ApplicationContext,
        question: str,
        option1: str,
        option2: str,
        duration_hours: Optional[int] = 24
    ):
        """Create a new prediction market with structured logging."""
        
        # Set correlation ID for this operation
        correlation_id = set_correlation_id(f"create-pred-{ctx.user.id}-{ctx.guild.id}")
        
        # Log the command invocation with context
        context = LogContext(
            correlation_id=correlation_id,
            user_id=ctx.user.id,
            guild_id=ctx.guild.id,
            operation="create_prediction",
            extra={
                "question": question,
                "options": [option1, option2],
                "duration_hours": duration_hours,
                "channel_id": ctx.channel.id
            }
        )
        
        self.logging_manager.log_with_context(
            self.logger,
            self.logger.info,
            "User initiated prediction creation",
            context
        )
        
        try:
            # Simulate prediction creation logic
            await self._create_prediction_logic(question, [option1, option2], duration_hours)
            
            # Log successful creation
            self.logger.info("Prediction created successfully", extra={
                'prediction_question': question,
                'options_count': 2,
                'duration_hours': duration_hours,
                'status': 'success'
            })
            
            await ctx.respond(f"✅ Created prediction: {question}")
            
        except Exception as e:
            # Log error with full context
            self.logger.error("Failed to create prediction", extra={
                'error_type': type(e).__name__,
                'error_message': str(e),
                'question': question,
                'user_id': ctx.user.id,
                'guild_id': ctx.guild.id
            }, exc_info=True)
            
            await ctx.respond("❌ Failed to create prediction. Please try again.")
    
    @commands.slash_command(name="place_bet", description="Place a bet on a prediction")
    @log_performance(threshold_seconds=2.0)  # Log if bet placement takes > 2 seconds
    async def place_bet(
        self,
        ctx: discord.ApplicationContext,
        prediction_id: str,
        option: str,
        amount: int
    ):
        """Place a bet with performance monitoring."""
        
        correlation_id = set_correlation_id(f"bet-{ctx.user.id}-{prediction_id}")
        
        self.logger.info("Processing bet placement", extra={
            'prediction_id': prediction_id,
            'user_id': ctx.user.id,
            'guild_id': ctx.guild.id,
            'option': option,
            'amount': amount,
            'operation': 'place_bet'
        })
        
        try:
            # Simulate bet placement logic (with artificial delay for demo)
            await asyncio.sleep(0.5)  # Simulate database operations
            
            # Validate bet
            if amount <= 0:
                raise ValueError("Bet amount must be positive")
            
            if amount > 1000000:
                # This will trigger performance warning due to additional processing
                await asyncio.sleep(2.5)  # Simulate slow validation for large bets
            
            # Simulate successful bet placement
            await self._place_bet_logic(prediction_id, ctx.user.id, option, amount)
            
            self.logger.info("Bet placed successfully", extra={
                'prediction_id': prediction_id,
                'user_id': ctx.user.id,
                'option': option,
                'amount': amount,
                'status': 'confirmed'
            })
            
            await ctx.respond(f"✅ Placed {amount} points on '{option}'")
            
        except ValueError as e:
            self.logger.warning("Invalid bet parameters", extra={
                'prediction_id': prediction_id,
                'user_id': ctx.user.id,
                'amount': amount,
                'error': str(e)
            })
            await ctx.respond(f"❌ {str(e)}")
            
        except Exception as e:
            self.logger.error("Bet placement failed", extra={
                'prediction_id': prediction_id,
                'user_id': ctx.user.id,
                'error_type': type(e).__name__,
                'error_message': str(e)
            }, exc_info=True)
            await ctx.respond("❌ Failed to place bet. Please try again.")
    
    @log_function_call(include_duration=True)
    async def _create_prediction_logic(self, question: str, options: list, duration_hours: int):
        """Simulate prediction creation business logic."""
        # Simulate database operations
        await asyncio.sleep(0.2)
        
        self.logger.debug("Prediction data validated", extra={
            'question_length': len(question),
            'options_count': len(options),
            'duration_hours': duration_hours
        })
        
        # Simulate more processing
        await asyncio.sleep(0.1)
        
        return f"pred-{hash(question) % 10000}"
    
    @log_function_call(include_duration=True)
    async def _place_bet_logic(self, prediction_id: str, user_id: int, option: str, amount: int):
        """Simulate bet placement business logic."""
        # Simulate balance check
        await asyncio.sleep(0.1)
        
        self.logger.debug("Balance validated", extra={
            'user_id': user_id,
            'bet_amount': amount,
            'prediction_id': prediction_id
        })
        
        # Simulate AMM calculations
        await asyncio.sleep(0.2)
        
        self.logger.debug("AMM calculations completed", extra={
            'prediction_id': prediction_id,
            'option': option,
            'amount': amount,
            'shares_calculated': amount * 0.95  # Example calculation
        })
        
        return True
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Log when the cog is ready."""
        self.logger.info("ExampleCog is ready", extra={
            'cog_name': self.__class__.__name__,
            'guild_count': len(self.bot.guilds) if hasattr(self.bot, 'guilds') else 0
        })


class ExampleBot(commands.Bot):
    """Example bot with structured logging integration."""
    
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        
        # Initialize logging
        self.logging_settings = LoggingSettings(
            level="INFO",
            file_enabled=True,
            file_path="logs/bot.log",
            console_enabled=True,
            json_format=True
        )
        self.logging_manager = LoggingManager(self.logging_settings)
        self.logger = get_logger(__name__)
    
    async def on_ready(self):
        """Log bot startup with correlation ID."""
        startup_correlation_id = set_correlation_id("bot-startup")
        
        self.logger.info("Bot is ready", extra={
            'bot_name': self.user.name,
            'bot_id': self.user.id,
            'guild_count': len(self.guilds),
            'startup_correlation_id': startup_correlation_id
        })
        
        # Log guild information
        for guild in self.guilds:
            self.logger.info("Connected to guild", extra={
                'guild_id': guild.id,
                'guild_name': guild.name,
                'member_count': guild.member_count
            })
    
    async def on_application_command_error(self, ctx, error):
        """Log command errors with full context."""
        error_correlation_id = set_correlation_id(f"error-{ctx.user.id}-{ctx.guild.id}")
        
        self.logger.error("Application command error", extra={
            'command_name': ctx.command.name if ctx.command else 'unknown',
            'user_id': ctx.user.id,
            'guild_id': ctx.guild.id,
            'channel_id': ctx.channel.id,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'error_correlation_id': error_correlation_id
        }, exc_info=True)


async def main():
    """Example main function showing bot setup with logging."""
    print("Starting Discord bot with structured logging...")
    
    # Create bot instance
    bot = ExampleBot()
    
    # Add the example cog
    await bot.add_cog(ExampleCog(bot))
    
    # In a real implementation, you would run the bot with:
    # await bot.start("YOUR_BOT_TOKEN")
    
    print("Bot setup complete. Logging system is configured.")
    print("Log files will be created in the 'logs/' directory.")
    print("\nExample log entries that would be generated:")
    print("- Bot startup with correlation IDs")
    print("- Command invocations with user context")
    print("- Performance monitoring for slow operations")
    print("- Error tracking with full stack traces")
    print("- Business logic debugging information")


if __name__ == "__main__":
    asyncio.run(main())