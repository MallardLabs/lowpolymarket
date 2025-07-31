"""
Comprehensive Error Handler for the Discord Prediction Market Bot.

This module provides:
- Discord interaction error handling with user-friendly messages
- Structured error logging with unique IDs
- Retry logic with exponential backoff
- Circuit breaker pattern for external service calls
- Error recovery and graceful degradation
"""

import asyncio
import logging
import time
import traceback
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union
from weakref import WeakSet

import discord
from discord.ext import commands

from .exceptions import (
    PredictionMarketError, ErrorSeverity, DatabaseError, ExternalAPIError,
    RateLimitExceededError, ValidationError, ConfigurationError
)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class RetryStrategy(Enum):
    """Retry strategy types."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"


class CircuitBreaker:
    """
    Circuit breaker implementation for external service calls.
    
    Prevents cascade failures by temporarily blocking calls to failing services
    and allowing them to recover.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitBreakerState.CLOSED
        
        self._logger = logging.getLogger(f"{__name__}.CircuitBreaker")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            ExternalAPIError: When circuit is open or function fails
        """
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                self._logger.info("Circuit breaker transitioning to HALF_OPEN")
            else:
                raise ExternalAPIError(
                    service=func.__name__,
                    details={"circuit_breaker_state": "open", "timeout_remaining": self._get_timeout_remaining()}
                )
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise ExternalAPIError(
                service=func.__name__,
                details={"original_error": str(e), "circuit_breaker_state": self.state.value}
            ) from e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.timeout_seconds
    
    def _get_timeout_remaining(self) -> float:
        """Get remaining timeout seconds."""
        if self.last_failure_time is None:
            return 0.0
        return max(0.0, self.timeout_seconds - (time.time() - self.last_failure_time))
    
    def _on_success(self) -> None:
        """Handle successful call."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self._logger.info("Circuit breaker reset to CLOSED after successful call")
        
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
    
    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            self._logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures. "
                f"Timeout: {self.timeout_seconds}s"
            )


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    Decorator for retry logic with configurable backoff strategies.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        strategy: Retry strategy to use
        exceptions: Tuple of exceptions to retry on
        on_retry: Optional callback function called on each retry
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                        
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        # Final attempt failed
                        break
                    
                    # Calculate delay
                    if strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                    elif strategy == RetryStrategy.LINEAR_BACKOFF:
                        delay = min(base_delay * (attempt + 1), max_delay)
                    else:  # FIXED_DELAY
                        delay = base_delay
                    
                    # Call retry callback if provided
                    if on_retry:
                        try:
                            if asyncio.iscoroutinefunction(on_retry):
                                await on_retry(attempt + 1, e, delay)
                            else:
                                on_retry(attempt + 1, e, delay)
                        except Exception as callback_error:
                            logging.getLogger(__name__).warning(
                                f"Retry callback failed: {callback_error}"
                            )
                    
                    await asyncio.sleep(delay)
            
            # All retries exhausted
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, create an event loop if needed
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(async_wrapper(*args, **kwargs))
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class ErrorHandler:
    """
    Comprehensive error handler for Discord interactions and system operations.
    
    Provides centralized error handling with:
    - User-friendly Discord error messages
    - Structured logging with unique error IDs
    - Error recovery and graceful degradation
    - Integration with circuit breakers and retry logic
    """
    
    def __init__(self, bot: Optional[commands.Bot] = None):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.error_stats: Dict[str, int] = {}
        self.recent_errors: List[Dict[str, Any]] = []
        self.max_recent_errors = 100
        
        # Error message templates
        self.error_templates = {
            ValidationError: "❌ **Input Error**\n{user_message}",
            DatabaseError: "🔧 **Database Issue**\n{user_message}\n*Error ID: {error_id}*",
            ExternalAPIError: "🌐 **Service Unavailable**\n{user_message}\n*Error ID: {error_id}*",
            RateLimitExceededError: "🚦 **Rate Limited**\n{user_message}",
            ConfigurationError: "⚙️ **System Error**\n{user_message}\n*Please contact an administrator.*",
            PredictionMarketError: "⚠️ **Error**\n{user_message}\n*Error ID: {error_id}*"
        }
    
    def get_circuit_breaker(
        self,
        service_name: str,
        failure_threshold: int = 5,
        timeout_seconds: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ) -> CircuitBreaker:
        """
        Get or create a circuit breaker for a service.
        
        Args:
            service_name: Name of the service
            failure_threshold: Number of failures before opening circuit
            timeout_seconds: Timeout before attempting reset
            expected_exception: Exception type to catch
            
        Returns:
            Circuit breaker instance
        """
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker(
                failure_threshold=failure_threshold,
                timeout_seconds=timeout_seconds,
                expected_exception=expected_exception
            )
        
        return self.circuit_breakers[service_name]
    
    async def handle_discord_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        ephemeral: bool = True
    ) -> None:
        """
        Handle Discord interaction errors with user-friendly messages.
        
        Args:
            interaction: Discord interaction that caused the error
            error: Exception that occurred
            ephemeral: Whether the error message should be ephemeral
        """
        # Log the error with full context
        error_context = await self._create_error_context(interaction, error)
        logged_error = self._log_error(error, error_context)
        
        # Create user-friendly message
        user_message = self._create_user_message(error, logged_error['error_id'])
        
        # Send error message to user
        try:
            if interaction.response.is_done():
                await interaction.followup.send(user_message, ephemeral=ephemeral)
            else:
                await interaction.response.send_message(user_message, ephemeral=ephemeral)
        except discord.HTTPException as send_error:
            self.logger.error(f"Failed to send error message to user: {send_error}")
    
    async def handle_command_error(
        self,
        ctx: commands.Context,
        error: Exception
    ) -> None:
        """
        Handle traditional command errors.
        
        Args:
            ctx: Command context
            error: Exception that occurred
        """
        # Log the error
        error_context = {
            'command': ctx.command.name if ctx.command else 'unknown',
            'guild_id': ctx.guild.id if ctx.guild else None,
            'channel_id': ctx.channel.id,
            'user_id': ctx.author.id,
            'message_content': ctx.message.content[:500]  # Truncate for privacy
        }
        
        logged_error = self._log_error(error, error_context)
        
        # Create user-friendly message
        user_message = self._create_user_message(error, logged_error['error_id'])
        
        # Send error message
        try:
            await ctx.send(user_message)
        except discord.HTTPException as send_error:
            self.logger.error(f"Failed to send error message to user: {send_error}")
    
    def handle_background_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle errors in background tasks and operations.
        
        Args:
            error: Exception that occurred
            context: Additional context information
            
        Returns:
            Dictionary with error information
        """
        return self._log_error(error, context or {})
    
    async def execute_with_circuit_breaker(
        self,
        service_name: str,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            service_name: Name of the service
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        circuit_breaker = self.get_circuit_breaker(service_name)
        return await circuit_breaker.call(func, *args, **kwargs)
    
    def _log_error(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Log error with structured format and unique ID.
        
        Args:
            error: Exception that occurred
            context: Additional context information
            
        Returns:
            Dictionary with logged error information
        """
        # Create error info
        if isinstance(error, PredictionMarketError):
            error_info = error.to_dict()
        else:
            # Create error info for non-PredictionMarketError exceptions
            error_info = {
                'error_id': self._generate_error_id(),
                'error_code': type(error).__name__,
                'message': str(error),
                'user_message': 'An unexpected error occurred.',
                'details': {},
                'severity': ErrorSeverity.MEDIUM.value,
                'timestamp': datetime.utcnow().isoformat(),
                'type': type(error).__name__
            }
        
        # Add context
        error_info['context'] = context
        error_info['traceback'] = traceback.format_exc()
        
        # Update statistics
        error_type = error_info['error_code']
        self.error_stats[error_type] = self.error_stats.get(error_type, 0) + 1
        
        # Add to recent errors (with size limit)
        self.recent_errors.append(error_info)
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors.pop(0)
        
        # Log with appropriate level
        severity = ErrorSeverity(error_info['severity'])
        log_level = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }.get(severity, logging.ERROR)
        
        self.logger.log(
            log_level,
            f"Error {error_info['error_id']}: {error_info['message']}",
            extra={
                'error_id': error_info['error_id'],
                'error_code': error_info['error_code'],
                'context': context,
                'severity': severity.value
            }
        )
        
        return error_info
    
    def _create_user_message(self, error: Exception, error_id: str) -> str:
        """
        Create user-friendly error message for Discord.
        
        Args:
            error: Exception that occurred
            error_id: Unique error identifier
            
        Returns:
            Formatted error message for users
        """
        # Get appropriate template
        error_type = type(error)
        template = self.error_templates.get(error_type)
        
        if template is None:
            # Find parent class template
            for exc_type, tmpl in self.error_templates.items():
                if isinstance(error, exc_type):
                    template = tmpl
                    break
        
        if template is None:
            template = "⚠️ **Unexpected Error**\nSomething went wrong. Please try again.\n*Error ID: {error_id}*"
        
        # Get user message
        if isinstance(error, PredictionMarketError):
            user_message = error.user_message
        else:
            user_message = "An unexpected error occurred. Please try again."
        
        # Format template
        return template.format(
            user_message=user_message,
            error_id=error_id
        )
    
    async def _create_error_context(
        self,
        interaction: discord.Interaction,
        error: Exception
    ) -> Dict[str, Any]:
        """
        Create error context from Discord interaction.
        
        Args:
            interaction: Discord interaction
            error: Exception that occurred
            
        Returns:
            Dictionary with context information
        """
        context = {
            'interaction_type': interaction.type.name if interaction.type else 'unknown',
            'guild_id': interaction.guild.id if interaction.guild else None,
            'guild_name': interaction.guild.name if interaction.guild else None,
            'channel_id': interaction.channel.id if interaction.channel else None,
            'user_id': interaction.user.id,
            'user_name': str(interaction.user),
            'command': None,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Add command information if available
        if hasattr(interaction, 'command') and interaction.command:
            context['command'] = interaction.command.name
            
            # Add command parameters if available
            if hasattr(interaction, 'namespace') and interaction.namespace:
                context['parameters'] = {
                    key: str(value)[:100]  # Truncate for privacy
                    for key, value in vars(interaction.namespace).items()
                    if not key.startswith('_')
                }
        
        return context
    
    def _generate_error_id(self) -> str:
        """Generate a unique error ID."""
        import uuid
        return str(uuid.uuid4())[:8].upper()
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get error statistics for monitoring.
        
        Returns:
            Dictionary with error statistics
        """
        return {
            'total_errors': sum(self.error_stats.values()),
            'error_counts_by_type': self.error_stats.copy(),
            'recent_errors_count': len(self.recent_errors),
            'circuit_breaker_states': {
                name: breaker.state.value
                for name, breaker in self.circuit_breakers.items()
            }
        }
    
    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent errors for debugging.
        
        Args:
            limit: Maximum number of errors to return
            
        Returns:
            List of recent error dictionaries
        """
        return self.recent_errors[-limit:] if self.recent_errors else []


# Global error handler instance
_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """
    Get the global error handler instance.
    
    Returns:
        The global error handler
    """
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler


def set_error_handler(error_handler: ErrorHandler) -> None:
    """
    Set the global error handler instance.
    
    Args:
        error_handler: The error handler to set as global
    """
    global _error_handler
    _error_handler = error_handler


# Convenience decorators
def handle_errors(
    interaction_error: bool = True,
    log_errors: bool = True,
    reraise: bool = False
):
    """
    Decorator to automatically handle errors in Discord commands.
    
    Args:
        interaction_error: Whether to handle as Discord interaction error
        log_errors: Whether to log errors
        reraise: Whether to reraise the exception after handling
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_handler = get_error_handler()
                
                if log_errors:
                    error_handler.handle_background_error(e, {'function': func.__name__})
                
                if interaction_error and len(args) > 0:
                    # Try to find Discord interaction in arguments
                    interaction = None
                    for arg in args:
                        if isinstance(arg, discord.Interaction):
                            interaction = arg
                            break
                    
                    if interaction:
                        await error_handler.handle_discord_error(interaction, e)
                
                if reraise:
                    raise
        
        return wrapper
    return decorator