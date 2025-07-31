#!/usr/bin/env python3
"""
Main entry point for the Discord Prediction Market Bot.

This script initializes the complete architecture including:
- Dependency injection container
- Logging system with correlation IDs
- Error handling and recovery
- Configuration validation
- Security middleware
- Rate limiting
- Database connections
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

import discord
from discord.ext import commands

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import validate_configuration, print_configuration_summary, ConfigurationError
from core.container import DIContainer, get_container, set_container
from core.logging_manager import get_logging_manager, get_logger, set_correlation_id
from core.error_handler import ErrorHandler, get_error_handler, set_error_handler
from core.rate_limiter import RateLimiter
from core.security import SecurityManager
from database.supabase_client import SupabaseClient
from helpers.SimplePointsManager import PointsManagerSingleton


class PredictionMarketBot(commands.Bot):
    """Enhanced Discord bot with full architecture integration."""
    
    def __init__(self, settings, container: DIContainer):
        # Configure intents
        intents = discord.Intents.default()
        intents.message_content = True  # Required for message commands
        
        super().__init__(
            command_prefix=settings.discord.command_prefix,
            intents=intents,
            help_command=None  # We'll create a custom help command
        )
        
        self.settings = settings
        self.container = container
        self.logger = get_logger("PredictionMarketBot")
        self._ready = False
        
        # Set up error handling
        self.error_handler = get_error_handler()
        self.error_handler.bot = self
    
    async def setup_hook(self) -> None:
        """Initialize bot services and load cogs."""
        self.logger.info("🚀 Starting bot setup...")
        
        # Set correlation ID for startup
        startup_id = set_correlation_id("STARTUP")
        self.logger.info(f"Bot startup correlation ID: {startup_id}")
        
        try:
            # Initialize all singleton services
            await self.container.initialize_all_singletons()
            self.logger.info("✅ All services initialized")
            
            # Load cogs
            await self._load_cogs()
            self.logger.info("✅ All cogs loaded")
            
            # Sync commands if enabled
            if self.settings.discord.sync_commands:
                await self.tree.sync()
                self.logger.info("✅ Slash commands synced")
            
            self.logger.info("🎉 Bot setup completed successfully!")
            
        except Exception as e:
            self.logger.critical(f"❌ Failed to setup bot: {e}", exc_info=True)
            raise
    
    async def on_ready(self) -> None:
        """Called when bot is ready."""
        if not self._ready:
            self.logger.info(f"🤖 {self.user.name} is ready!")
            self.logger.info(f"📊 Connected to {len(self.guilds)} guilds")
            self.logger.info(f"👥 Serving {sum(guild.member_count for guild in self.guilds)} users")
            self._ready = True
        else:
            self.logger.info("🔄 Bot reconnected")
    
    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        """Handle command errors."""
        await self.error_handler.handle_command_error(ctx, error)
    
    async def on_application_command_error(
        self, 
        interaction: discord.Interaction, 
        error: Exception
    ) -> None:
        """Handle slash command errors."""
        await self.error_handler.handle_discord_error(interaction, error)
    
    async def _load_cogs(self) -> None:
        """Load all cogs from the cogs directory."""
        cogs_dir = project_root / "cogs"
        
        # Load cogs from subdirectories
        for cog_file in cogs_dir.rglob("*.py"):
            if cog_file.name.startswith("_"):
                continue
            
            # Convert file path to module path
            relative_path = cog_file.relative_to(project_root)
            module_path = str(relative_path.with_suffix("")).replace(os.sep, ".")
            
            try:
                await self.load_extension(module_path)
                self.logger.info(f"✅ Loaded cog: {module_path}")
            except Exception as e:
                self.logger.error(f"❌ Failed to load cog {module_path}: {e}")
    
    async def close(self) -> None:
        """Clean shutdown of bot and services."""
        self.logger.info("🛑 Shutting down bot...")
        
        try:
            # Dispose of container and all services
            await self.container.dispose_async()
            self.logger.info("✅ Services disposed")
        except Exception as e:
            self.logger.error(f"❌ Error during shutdown: {e}")
        
        await super().close()
        self.logger.info("👋 Bot shutdown complete")


async def setup_services(settings, container: DIContainer) -> None:
    """Set up all application services in the DI container."""
    logger = get_logger("ServiceSetup")
    logger.info("🔧 Setting up services...")
    
    # Register logging manager
    logging_manager = get_logging_manager(settings.logging)
    container.register_instance(type(logging_manager), logging_manager)
    
    # Register error handler
    error_handler = ErrorHandler()
    set_error_handler(error_handler)
    container.register_instance(ErrorHandler, error_handler)
    
    # Register rate limiter
    rate_limiter = RateLimiter(
        default_requests_per_minute=settings.rate_limit.user_requests_per_minute,
        cleanup_interval=settings.rate_limit.cleanup_interval
    )
    container.register_instance(RateLimiter, rate_limiter)
    
    # Register security manager
    security_manager = SecurityManager()
    container.register_instance(SecurityManager, security_manager)
    
    # Register database client
    db_client = SupabaseClient(
        url=settings.database.supabase_url,
        key=settings.database.supabase_publishable_key,
        secret_key=settings.database.supabase_secret_key
    )
    container.register_instance(SupabaseClient, db_client)
    
    # Register points manager (existing system)
    points_manager = PointsManagerSingleton(
        base_url=settings.drip_api.base_url,
        api_key=settings.drip_api.api_key,
        realm_id=settings.drip_api.realm_id
    )
    container.register_instance(PointsManagerSingleton, points_manager)
    
    logger.info("✅ All services registered")


async def main() -> None:
    """Main application entry point."""
    print("🎯 Discord Prediction Market Bot")
    print("=" * 50)
    
    try:
        # Load and validate configuration
        print("📋 Loading configuration...")
        settings = validate_configuration()
        print_configuration_summary(settings)
        
        # Initialize logging
        print("📝 Initializing logging system...")
        logging_manager = get_logging_manager(settings.logging)
        logger = get_logger("Main")
        
        # Set startup correlation ID
        startup_id = set_correlation_id("MAIN_STARTUP")
        logger.info(f"🚀 Starting application with correlation ID: {startup_id}")
        
        # Create and configure DI container
        logger.info("🏗️ Setting up dependency injection container...")
        container = DIContainer()
        set_container(container)
        
        # Register all services
        await setup_services(settings, container)
        
        # Create and run bot
        logger.info("🤖 Creating bot instance...")
        bot = PredictionMarketBot(settings, container)
        
        # Register bot in container for other services to use
        container.register_instance(PredictionMarketBot, bot)
        
        logger.info("🚀 Starting bot...")
        await bot.start(settings.discord.token)
        
    except ConfigurationError as e:
        print(f"❌ Configuration Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Received interrupt signal, shutting down...")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        if 'logger' in locals():
            logger.critical(f"Fatal error during startup: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")