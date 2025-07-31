"""
Examples demonstrating the comprehensive error handler usage.

This file shows how to use the error handler in various scenarios:
- Discord interaction error handling
- Circuit breaker pattern for external services
- Retry logic with exponential backoff
- Background error handling
"""

import asyncio
import discord
from discord.ext import commands
from typing import Optional

from core.error_handler import (
    ErrorHandler, get_error_handler, retry_with_backoff, 
    handle_errors, RetryStrategy
)
from core.exceptions import (
    ValidationError, DatabaseError, ExternalAPIError,
    InsufficientBalanceError, PredictionNotFoundError
)


class ExampleCog(commands.Cog):
    """Example cog demonstrating error handler integration."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.error_handler = get_error_handler()
        
        # Set up circuit breakers for external services
        self.database_breaker = self.error_handler.get_circuit_breaker(
            "database",
            failure_threshold=3,
            timeout_seconds=30.0,
            expected_exception=DatabaseError
        )
        
        self.api_breaker = self.error_handler.get_circuit_breaker(
            "external_api",
            failure_threshold=5,
            timeout_seconds=60.0,
            expected_exception=ExternalAPIError
        )
    
    @discord.app_commands.command(name="example_bet", description="Example betting command with error handling")
    async def example_bet(
        self,
        interaction: discord.Interaction,
        amount: int,
        prediction_id: str
    ):
        """Example command showing comprehensive error handling."""
        try:
            # Validate input
            if amount <= 0:
                raise ValidationError("Bet amount must be positive", field="amount", value=amount)
            
            if amount > 1000000:
                raise ValidationError("Bet amount too large", field="amount", value=amount)
            
            # Check user balance (with circuit breaker)
            balance = await self.error_handler.execute_with_circuit_breaker(
                "database",
                self._get_user_balance,
                interaction.user.id
            )
            
            if balance < amount:
                raise InsufficientBalanceError(
                    required=amount,
                    available=balance,
                    user_id=interaction.user.id
                )
            
            # Place bet (with retry logic)
            bet_result = await self._place_bet_with_retry(
                interaction.user.id,
                prediction_id,
                amount
            )
            
            # Success response
            embed = discord.Embed(
                title="✅ Bet Placed Successfully",
                description=f"Placed {amount:,} points on prediction {prediction_id}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            # Let the error handler manage the error
            await self.error_handler.handle_discord_error(interaction, e)
    
    @discord.app_commands.command(name="example_create", description="Example prediction creation with error handling")
    async def example_create(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str
    ):
        """Example command using the handle_errors decorator."""
        await self._create_prediction_internal(interaction, question, option1, option2)
    
    @handle_errors(interaction_error=True, log_errors=True)
    async def _create_prediction_internal(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str
    ):
        """Internal method with automatic error handling."""
        # Validate inputs
        if len(question) < 10:
            raise ValidationError("Question too short", field="question", value=question)
        
        if option1 == option2:
            raise ValidationError("Options must be different")
        
        # Create prediction (with circuit breaker)
        prediction_id = await self.error_handler.execute_with_circuit_breaker(
            "database",
            self._create_prediction_in_db,
            interaction.guild.id,
            question,
            [option1, option2],
            interaction.user.id
        )
        
        # Success response
        embed = discord.Embed(
            title="🎲 Prediction Created",
            description=f"**{question}**\n\nOptions: {option1}, {option2}",
            color=discord.Color.blue()
        )
        embed.add_field(name="ID", value=prediction_id, inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @retry_with_backoff(
        max_retries=3,
        base_delay=1.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        exceptions=(DatabaseError, ExternalAPIError)
    )
    async def _place_bet_with_retry(
        self,
        user_id: int,
        prediction_id: str,
        amount: int
    ) -> dict:
        """Place bet with automatic retry on transient failures."""
        # Simulate database operation that might fail
        if await self._simulate_transient_failure():
            raise DatabaseError("Temporary database connection issue", operation="place_bet")
        
        # Simulate successful bet placement
        return {
            "bet_id": f"bet_{user_id}_{prediction_id}",
            "amount": amount,
            "timestamp": "2024-01-01T12:00:00Z"
        }
    
    async def _get_user_balance(self, user_id: int) -> int:
        """Get user balance (might fail and trigger circuit breaker)."""
        # Simulate occasional database failures
        if await self._simulate_service_failure("database"):
            raise DatabaseError("Database connection failed", operation="get_balance")
        
        # Return mock balance
        return 5000
    
    async def _create_prediction_in_db(
        self,
        guild_id: int,
        question: str,
        options: list,
        creator_id: int
    ) -> str:
        """Create prediction in database (might fail and trigger circuit breaker)."""
        # Simulate occasional database failures
        if await self._simulate_service_failure("database"):
            raise DatabaseError("Failed to create prediction", operation="create_prediction")
        
        # Return mock prediction ID
        return f"pred_{guild_id}_{creator_id}"
    
    async def _simulate_transient_failure(self) -> bool:
        """Simulate transient failures for retry demonstration."""
        import random
        return random.random() < 0.3  # 30% chance of failure
    
    async def _simulate_service_failure(self, service: str) -> bool:
        """Simulate service failures for circuit breaker demonstration."""
        import random
        failure_rates = {
            "database": 0.1,  # 10% failure rate
            "external_api": 0.2  # 20% failure rate
        }
        return random.random() < failure_rates.get(service, 0.1)


class BackgroundTaskExample:
    """Example showing error handling in background tasks."""
    
    def __init__(self):
        self.error_handler = get_error_handler()
        self.running = False
    
    async def start_background_task(self):
        """Start a background task with error handling."""
        self.running = True
        while self.running:
            try:
                await self._process_expired_predictions()
                await asyncio.sleep(300)  # 5 minutes
                
            except Exception as e:
                # Handle background errors
                error_info = self.error_handler.handle_background_error(
                    e,
                    context={
                        "task": "process_expired_predictions",
                        "timestamp": "2024-01-01T12:00:00Z"
                    }
                )
                
                # Log error and continue (don't crash the task)
                print(f"Background task error {error_info['error_id']}: {error_info['message']}")
                
                # Wait before retrying
                await asyncio.sleep(60)
    
    @retry_with_backoff(
        max_retries=2,
        base_delay=5.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        exceptions=(DatabaseError,)
    )
    async def _process_expired_predictions(self):
        """Process expired predictions with retry logic."""
        # Simulate database operation
        if await self._simulate_database_issue():
            raise DatabaseError("Failed to query expired predictions", operation="query_expired")
        
        print("Processed expired predictions successfully")
    
    async def _simulate_database_issue(self) -> bool:
        """Simulate occasional database issues."""
        import random
        return random.random() < 0.2  # 20% chance of failure
    
    def stop(self):
        """Stop the background task."""
        self.running = False


class ExternalServiceExample:
    """Example showing circuit breaker usage with external services."""
    
    def __init__(self):
        self.error_handler = get_error_handler()
    
    async def fetch_market_data(self, symbol: str) -> dict:
        """Fetch market data with circuit breaker protection."""
        return await self.error_handler.execute_with_circuit_breaker(
            "market_api",
            self._fetch_from_api,
            symbol
        )
    
    async def _fetch_from_api(self, symbol: str) -> dict:
        """Simulate external API call that might fail."""
        import random
        
        # Simulate API failures
        if random.random() < 0.3:  # 30% failure rate
            raise ExternalAPIError(
                service="market_api",
                status_code=503,
                details={"symbol": symbol, "error": "Service temporarily unavailable"}
            )
        
        # Return mock data
        return {
            "symbol": symbol,
            "price": 100.0,
            "volume": 1000000,
            "timestamp": "2024-01-01T12:00:00Z"
        }


async def demonstrate_error_handling():
    """Demonstrate various error handling scenarios."""
    print("=== Error Handler Demonstration ===\n")
    
    # 1. Basic error logging
    print("1. Basic error logging:")
    error_handler = get_error_handler()
    
    try:
        raise ValidationError("Invalid input example", field="amount", value=-100)
    except Exception as e:
        error_info = error_handler.handle_background_error(e, {"demo": "basic_logging"})
        print(f"   Logged error {error_info['error_id']}: {error_info['message']}")
    
    print()
    
    # 2. Retry logic demonstration
    print("2. Retry logic demonstration:")
    
    @retry_with_backoff(max_retries=3, base_delay=0.1)
    async def flaky_operation():
        import random
        if random.random() < 0.7:  # 70% failure rate
            raise DatabaseError("Connection timeout", operation="test")
        return "Success!"
    
    try:
        result = await flaky_operation()
        print(f"   Operation succeeded: {result}")
    except Exception as e:
        print(f"   Operation failed after retries: {e}")
    
    print()
    
    # 3. Circuit breaker demonstration
    print("3. Circuit breaker demonstration:")
    
    external_service = ExternalServiceExample()
    
    # Make several calls to trigger circuit breaker
    for i in range(10):
        try:
            data = await external_service.fetch_market_data("BTCUSD")
            print(f"   Call {i+1}: Success - Price: ${data['price']}")
        except ExternalAPIError as e:
            print(f"   Call {i+1}: Failed - {e.user_message}")
        
        await asyncio.sleep(0.1)
    
    print()
    
    # 4. Error statistics
    print("4. Error statistics:")
    stats = error_handler.get_error_statistics()
    print(f"   Total errors: {stats['total_errors']}")
    print(f"   Error types: {stats['error_counts_by_type']}")
    print(f"   Circuit breaker states: {stats['circuit_breaker_states']}")
    
    print()
    
    # 5. Recent errors
    print("5. Recent errors:")
    recent = error_handler.get_recent_errors(limit=3)
    for error in recent:
        print(f"   {error['error_id']}: {error['error_code']} - {error['message'][:50]}...")


if __name__ == "__main__":
    # Run the demonstration
    asyncio.run(demonstrate_error_handling())