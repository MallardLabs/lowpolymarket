"""
Example of integrating the DI Container with the Discord Prediction Market Bot.

This example shows how to:
1. Set up the DI container with all necessary services
2. Register services with proper lifecycles
3. Use dependency injection in Discord cogs
4. Handle async initialization and cleanup
"""

import asyncio
import logging
from typing import Protocol

import discord
from discord.ext import commands

from core.container import DIContainer, get_container
from config import get_settings, Settings
from database.supabase_client import SupabaseManager, PredictionDatabase
from helpers.SimplePointsManager import PointsManagerSingleton


# Define service interfaces for better testability
class IPointsManager(Protocol):
    async def get_balance(self, user_id: int) -> int:
        ...
    
    async def add_points(self, user_id: int, amount: int) -> bool:
        ...
    
    async def subtract_points(self, user_id: int, amount: int) -> bool:
        ...


class IPredictionDatabase(Protocol):
    async def create_prediction(self, **kwargs) -> str:
        ...
    
    async def get_active_predictions(self, guild_id: int) -> list:
        ...


class ISupabaseManager(Protocol):
    async def initialize(self) -> None:
        ...
    
    async def cleanup(self) -> None:
        ...


# Service implementations
class PredictionService:
    """Business logic service for predictions."""
    
    def __init__(self, database: IPredictionDatabase, points_manager: IPointsManager):
        self.database = database
        self.points_manager = points_manager
        self.logger = logging.getLogger(__name__)
    
    async def create_prediction(self, guild_id: int, question: str, options: list, 
                              creator_id: int, end_time, category: str = None) -> str:
        """Create a new prediction with business logic validation."""
        # Validate inputs
        if len(options) < 2:
            raise ValueError("Prediction must have at least 2 options")
        
        if len(question) > 500:
            raise ValueError("Question too long")
        
        # Create prediction
        prediction_id = await self.database.create_prediction(
            guild_id=guild_id,
            question=question,
            options=options,
            creator_id=creator_id,
            end_time=end_time,
            category=category
        )
        
        self.logger.info(f"Created prediction {prediction_id} for guild {guild_id}")
        return prediction_id
    
    async def get_active_predictions(self, guild_id: int) -> list:
        """Get active predictions for a guild."""
        return await self.database.get_active_predictions(guild_id)


class BettingService:
    """Business logic service for betting operations."""
    
    def __init__(self, database: IPredictionDatabase, points_manager: IPointsManager):
        self.database = database
        self.points_manager = points_manager
        self.logger = logging.getLogger(__name__)
    
    async def place_bet(self, user_id: int, prediction_id: str, option: str, amount: int) -> bool:
        """Place a bet with validation and atomic operations."""
        # Check user balance
        balance = await self.points_manager.get_balance(user_id)
        if balance < amount:
            raise ValueError(f"Insufficient balance. Required: {amount}, Available: {balance}")
        
        # Deduct points first (atomic operation)
        if not await self.points_manager.subtract_points(user_id, amount):
            raise RuntimeError("Failed to deduct points")
        
        try:
            # Place bet in database
            # This would be implemented based on your existing logic
            success = True  # Placeholder
            
            if not success:
                # Refund points if bet placement failed
                await self.points_manager.add_points(user_id, amount)
                return False
            
            self.logger.info(f"User {user_id} placed bet of {amount} on {prediction_id}")
            return True
            
        except Exception as e:
            # Refund points on any error
            await self.points_manager.add_points(user_id, amount)
            self.logger.error(f"Error placing bet: {e}")
            raise


class EnhancedDiscordBot(commands.Bot):
    """Enhanced Discord bot with dependency injection."""
    
    def __init__(self, settings: Settings, container: DIContainer):
        super().__init__(
            command_prefix=settings.discord.command_prefix,
            intents=discord.Intents.default()
        )
        self.settings = settings
        self.container = container
        self.logger = logging.getLogger(__name__)
    
    async def setup_hook(self) -> None:
        """Initialize the bot with dependency injection."""
        self.logger.info("Setting up bot with DI container...")
        
        # Initialize all singleton services
        await self.container.initialize_all_singletons()
        
        # Load cogs with dependency injection
        await self.load_extension("examples.enhanced_cog")
        
        self.logger.info("Bot setup complete")
    
    async def close(self) -> None:
        """Clean shutdown with proper disposal."""
        self.logger.info("Shutting down bot...")
        
        # Dispose of the DI container
        await self.container.dispose_async()
        
        await super().close()


# Factory functions for complex service creation
async def create_supabase_manager(settings: Settings) -> SupabaseManager:
    """Factory function to create and initialize SupabaseManager."""
    manager = SupabaseManager(
        url=settings.database.supabase_url,
        key=settings.database.supabase_publishable_key,
        db_url=settings.database.url
    )
    await manager.initialize()
    return manager


def create_points_manager(settings: Settings) -> PointsManagerSingleton:
    """Factory function to create PointsManager."""
    return PointsManagerSingleton(
        base_url=settings.drip_api.base_url,
        api_key=settings.drip_api.api_key,
        realm_id=settings.drip_api.realm_id
    )


def create_prediction_database(supabase_manager: SupabaseManager) -> PredictionDatabase:
    """Factory function to create PredictionDatabase."""
    return PredictionDatabase(supabase_manager)


def setup_di_container() -> DIContainer:
    """Set up the dependency injection container with all services."""
    container = DIContainer()
    settings = get_settings()
    
    # Register configuration as singleton instance
    container.register_instance(Settings, settings)
    
    # Register infrastructure services
    container.register_factory(
        SupabaseManager, 
        lambda settings: create_supabase_manager(settings),
        lifecycle=ServiceLifecycle.SINGLETON
    )
    
    container.register_factory(
        PointsManagerSingleton,
        lambda settings: create_points_manager(settings),
        lifecycle=ServiceLifecycle.SINGLETON
    )
    
    container.register_factory(
        PredictionDatabase,
        lambda supabase_manager: create_prediction_database(supabase_manager),
        lifecycle=ServiceLifecycle.SINGLETON
    )
    
    # Register business logic services
    container.register_singleton(PredictionService)
    container.register_singleton(BettingService)
    
    # Register the bot itself
    container.register_factory(
        EnhancedDiscordBot,
        lambda settings, container: EnhancedDiscordBot(settings, container),
        lifecycle=ServiceLifecycle.SINGLETON
    )
    
    return container


async def main():
    """Main entry point with dependency injection setup."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Set up DI container
    container = setup_di_container()
    
    # Get the bot instance from the container
    bot = await container.get_service(EnhancedDiscordBot)
    
    try:
        # Get settings for the token
        settings = await container.get_service(Settings)
        
        # Run the bot
        await bot.start(settings.discord.token)
        
    except KeyboardInterrupt:
        logging.info("Received shutdown signal")
    finally:
        # Clean shutdown
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())