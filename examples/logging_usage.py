"""
Example usage of the structured logging system.

This module demonstrates how to use the logging manager with:
- Correlation IDs
- Contextual logging
- Function decorators
- Performance monitoring
"""

import asyncio
import time
from typing import Optional

from core.logging_manager import (
    get_logger,
    set_correlation_id,
    get_correlation_id,
    log_function_call,
    log_performance,
    LogContext,
    get_logging_manager
)


# Get a logger for this module
logger = get_logger(__name__)


@log_function_call(include_args=True, include_result=True, include_duration=True)
def create_prediction(question: str, options: list, duration_minutes: int) -> str:
    """Example function with automatic logging."""
    logger.info("Creating new prediction", extra={
        'question': question,
        'options_count': len(options),
        'duration_minutes': duration_minutes
    })
    
    # Simulate some processing time
    time.sleep(0.1)
    
    prediction_id = f"pred-{int(time.time())}"
    
    logger.info("Prediction created successfully", extra={
        'prediction_id': prediction_id,
        'status': 'active'
    })
    
    return prediction_id


@log_function_call(include_args=True, include_duration=True)
@log_performance(threshold_seconds=0.5)
async def place_bet(prediction_id: str, user_id: int, option: str, amount: int) -> bool:
    """Example async function with performance monitoring."""
    logger.info("Processing bet placement", extra={
        'prediction_id': prediction_id,
        'user_id': user_id,
        'option': option,
        'amount': amount
    })
    
    # Simulate async database operation
    await asyncio.sleep(0.2)
    
    # Simulate validation
    if amount <= 0:
        logger.error("Invalid bet amount", extra={
            'prediction_id': prediction_id,
            'user_id': user_id,
            'amount': amount,
            'error': 'amount_must_be_positive'
        })
        return False
    
    # Simulate slow operation that triggers performance warning
    if amount > 100000:
        await asyncio.sleep(0.6)  # This will trigger the performance warning
    
    logger.info("Bet placed successfully", extra={
        'prediction_id': prediction_id,
        'user_id': user_id,
        'option': option,
        'amount': amount,
        'status': 'confirmed'
    })
    
    return True


def demonstrate_correlation_ids():
    """Demonstrate correlation ID usage across function calls."""
    print("\n=== Correlation ID Demo ===")
    
    # Set a correlation ID for this operation
    corr_id = set_correlation_id("demo-operation-123")
    logger.info("Starting demo operation", extra={'operation': 'demo'})
    
    # Create a prediction - correlation ID will be automatically included
    prediction_id = create_prediction(
        question="Will it rain tomorrow?",
        options=["Yes", "No"],
        duration_minutes=1440
    )
    
    # The correlation ID persists across function calls
    logger.info("Demo operation completed", extra={
        'operation': 'demo',
        'prediction_id': prediction_id
    })
    
    print(f"Correlation ID used: {corr_id}")


async def demonstrate_async_logging():
    """Demonstrate async function logging."""
    print("\n=== Async Logging Demo ===")
    
    # Set correlation ID for async operations
    set_correlation_id("async-demo-456")
    
    # Place some bets
    await place_bet("pred-123", 12345, "Yes", 100)
    await place_bet("pred-123", 67890, "No", 150000)  # This will be slow
    
    # Try an invalid bet
    await place_bet("pred-123", 11111, "Yes", -50)


def demonstrate_contextual_logging():
    """Demonstrate contextual logging with LogContext."""
    print("\n=== Contextual Logging Demo ===")
    
    logging_manager = get_logging_manager()
    
    # Create a context with multiple fields
    context = LogContext(
        correlation_id="context-demo-789",
        user_id=12345,
        guild_id=98765,
        prediction_id="pred-456",
        operation="resolve_prediction",
        extra={
            'resolution_type': 'manual',
            'resolver_role': 'admin'
        }
    )
    
    # Log with context
    logging_manager.log_with_context(
        logger,
        logger.info,
        "Resolving prediction with admin override",
        context,
        winning_option="Yes",
        total_volume=50000
    )


def demonstrate_error_logging():
    """Demonstrate error logging with context."""
    print("\n=== Error Logging Demo ===")
    
    set_correlation_id("error-demo-999")
    
    try:
        # Simulate an error
        raise ValueError("Invalid prediction state: already resolved")
    except Exception as e:
        logger.error("Failed to process prediction", extra={
            'prediction_id': 'pred-789',
            'user_id': 12345,
            'operation': 'place_bet',
            'error_type': type(e).__name__,
            'error_message': str(e)
        }, exc_info=True)


def demonstrate_performance_logging():
    """Demonstrate performance logging."""
    print("\n=== Performance Logging Demo ===")
    
    @log_performance(threshold_seconds=0.1)
    def slow_operation():
        """A function that will trigger performance warning."""
        time.sleep(0.2)
        return "completed"
    
    @log_performance(threshold_seconds=0.1)
    def fast_operation():
        """A function that won't trigger performance warning."""
        time.sleep(0.05)
        return "completed"
    
    set_correlation_id("perf-demo-111")
    
    logger.info("Testing performance monitoring")
    
    # This will trigger a performance warning
    slow_operation()
    
    # This won't trigger a warning
    fast_operation()


async def main():
    """Main demo function."""
    print("Structured Logging System Demo")
    print("=" * 40)
    
    # Demonstrate different logging features
    demonstrate_correlation_ids()
    await demonstrate_async_logging()
    demonstrate_contextual_logging()
    demonstrate_error_logging()
    demonstrate_performance_logging()
    
    print("\n=== Demo Complete ===")
    print("Check the log files to see the structured output!")


if __name__ == "__main__":
    asyncio.run(main())