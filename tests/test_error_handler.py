"""
Comprehensive tests for the error handler system.

Tests cover:
- Discord interaction error handling
- Circuit breaker functionality
- Retry logic with different strategies
- Error logging and statistics
- Background error handling
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Dict, Any

import discord
from discord.ext import commands

from core.error_handler import (
    ErrorHandler, CircuitBreaker, CircuitBreakerState, RetryStrategy,
    retry_with_backoff, handle_errors, get_error_handler
)
from core.exceptions import (
    PredictionMarketError, ValidationError, DatabaseError, ExternalAPIError,
    InsufficientBalanceError, ErrorSeverity
)


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create a circuit breaker for testing."""
        return CircuitBreaker(
            failure_threshold=3,
            timeout_seconds=1.0,
            expected_exception=Exception
        )
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self, circuit_breaker):
        """Test circuit breaker in closed state (normal operation)."""
        async def successful_operation():
            return "success"
        
        result = await circuit_breaker.call(successful_operation)
        assert result == "success"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_counting(self, circuit_breaker):
        """Test circuit breaker failure counting."""
        async def failing_operation():
            raise Exception("Test failure")
        
        # First two failures should not open circuit
        for i in range(2):
            with pytest.raises(ExternalAPIError):
                await circuit_breaker.call(failing_operation)
            assert circuit_breaker.state == CircuitBreakerState.CLOSED
            assert circuit_breaker.failure_count == i + 1
        
        # Third failure should open circuit
        with pytest.raises(ExternalAPIError):
            await circuit_breaker.call(failing_operation)
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.failure_count == 3
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_open_state(self, circuit_breaker):
        """Test circuit breaker in open state (blocking calls)."""
        async def failing_operation():
            raise Exception("Test failure")
        
        # Trigger circuit breaker to open
        for _ in range(3):
            with pytest.raises(ExternalAPIError):
                await circuit_breaker.call(failing_operation)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Further calls should be blocked immediately
        with pytest.raises(ExternalAPIError) as exc_info:
            await circuit_breaker.call(failing_operation)
        
        # Check that the error contains circuit breaker information
        error = exc_info.value
        assert error.details["circuit_breaker_state"] == "open"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self, circuit_breaker):
        """Test circuit breaker recovery through half-open state."""
        async def failing_operation():
            raise Exception("Test failure")
        
        async def successful_operation():
            return "success"
        
        # Open the circuit
        for _ in range(3):
            with pytest.raises(ExternalAPIError):
                await circuit_breaker.call(failing_operation)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Wait for timeout
        await asyncio.sleep(1.1)
        
        # Next call should transition to half-open and succeed
        result = await circuit_breaker.call(successful_operation)
        assert result == "success"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0


class TestRetryLogic:
    """Test retry logic with different strategies."""
    
    @pytest.mark.asyncio
    async def test_retry_exponential_backoff(self):
        """Test exponential backoff retry strategy."""
        call_count = 0
        delays = []
        
        @retry_with_backoff(
            max_retries=3,
            base_delay=0.1,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            exceptions=(ValueError,)
        )
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Attempt {call_count}")
            return "success"
        
        # Mock sleep to capture delays
        with patch('asyncio.sleep') as mock_sleep:
            result = await flaky_function()
            
            assert result == "success"
            assert call_count == 3
            
            # Check exponential backoff delays
            sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
            assert len(sleep_calls) == 2  # 2 retries
            assert sleep_calls[0] == 0.1  # First retry: base_delay * 2^0
            assert sleep_calls[1] == 0.2  # Second retry: base_delay * 2^1
    
    @pytest.mark.asyncio
    async def test_retry_linear_backoff(self):
        """Test linear backoff retry strategy."""
        call_count = 0
        
        @retry_with_backoff(
            max_retries=2,
            base_delay=0.1,
            strategy=RetryStrategy.LINEAR_BACKOFF,
            exceptions=(ValueError,)
        )
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Attempt {call_count}")
            return "success"
        
        with patch('asyncio.sleep') as mock_sleep:
            result = await flaky_function()
            
            assert result == "success"
            assert call_count == 3
            
            # Check linear backoff delays
            sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
            assert len(sleep_calls) == 2
            assert sleep_calls[0] == 0.1  # First retry: base_delay * 1
            assert sleep_calls[1] == 0.2  # Second retry: base_delay * 2
    
    @pytest.mark.asyncio
    async def test_retry_fixed_delay(self):
        """Test fixed delay retry strategy."""
        call_count = 0
        
        @retry_with_backoff(
            max_retries=2,
            base_delay=0.1,
            strategy=RetryStrategy.FIXED_DELAY,
            exceptions=(ValueError,)
        )
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Attempt {call_count}")
            return "success"
        
        with patch('asyncio.sleep') as mock_sleep:
            result = await flaky_function()
            
            assert result == "success"
            assert call_count == 3
            
            # Check fixed delays
            sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
            assert len(sleep_calls) == 2
            assert all(delay == 0.1 for delay in sleep_calls)
    
    @pytest.mark.asyncio
    async def test_retry_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded."""
        call_count = 0
        
        @retry_with_backoff(
            max_retries=2,
            base_delay=0.01,
            exceptions=(ValueError,)
        )
        async def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"Attempt {call_count}")
        
        with pytest.raises(ValueError) as exc_info:
            await always_failing_function()
        
        assert "Attempt 3" in str(exc_info.value)  # Should fail on 3rd attempt
        assert call_count == 3  # Initial call + 2 retries
    
    @pytest.mark.asyncio
    async def test_retry_with_callback(self):
        """Test retry logic with callback function."""
        retry_attempts = []
        
        async def retry_callback(attempt: int, error: Exception, delay: float):
            retry_attempts.append((attempt, str(error), delay))
        
        call_count = 0
        
        @retry_with_backoff(
            max_retries=2,
            base_delay=0.1,
            exceptions=(ValueError,),
            on_retry=retry_callback
        )
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Attempt {call_count}")
            return "success"
        
        with patch('asyncio.sleep'):
            result = await flaky_function()
            
            assert result == "success"
            assert len(retry_attempts) == 2
            
            # Check callback was called with correct parameters
            assert retry_attempts[0][0] == 1  # First retry attempt
            assert "Attempt 1" in retry_attempts[0][1]
            assert retry_attempts[0][2] == 0.1  # Delay
            
            assert retry_attempts[1][0] == 2  # Second retry attempt
            assert "Attempt 2" in retry_attempts[1][1]
            assert retry_attempts[1][2] == 0.2  # Delay


class TestErrorHandler:
    """Test error handler functionality."""
    
    @pytest.fixture
    def error_handler(self):
        """Create an error handler for testing."""
        return ErrorHandler()
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.id = 12345
        interaction.user.name = "TestUser"
        interaction.guild = MagicMock()
        interaction.guild.id = 67890
        interaction.guild.name = "TestGuild"
        interaction.channel = MagicMock()
        interaction.channel.id = 11111
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        # is_done() should be a regular method, not async
        interaction.response.is_done = MagicMock(return_value=False)
        return interaction
    
    @pytest.mark.asyncio
    async def test_handle_discord_error_validation(self, error_handler, mock_interaction):
        """Test Discord error handling for validation errors."""
        error = ValidationError("Invalid amount", field="amount", value=-100)
        
        await error_handler.handle_discord_error(mock_interaction, error)
        
        # Check that response was sent
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        message = call_args[0][0]
        
        assert "❌ **Input Error**" in message
        assert "Invalid amount" in message
    
    @pytest.mark.asyncio
    async def test_handle_discord_error_database(self, error_handler, mock_interaction):
        """Test Discord error handling for database errors."""
        error = DatabaseError("Connection failed", operation="get_balance")
        
        await error_handler.handle_discord_error(mock_interaction, error)
        
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        message = call_args[0][0]
        
        assert "🔧 **Database Issue**" in message
        assert "Error ID:" in message
    
    @pytest.mark.asyncio
    async def test_handle_discord_error_followup(self, error_handler, mock_interaction):
        """Test Discord error handling when response is already done."""
        mock_interaction.response.is_done.return_value = True
        error = ValidationError("Test error")
        
        await error_handler.handle_discord_error(mock_interaction, error)
        
        # Should use followup instead of response
        mock_interaction.followup.send.assert_called_once()
        mock_interaction.response.send_message.assert_not_called()
    
    def test_error_logging(self, error_handler):
        """Test error logging functionality."""
        error = ValidationError("Test validation error", field="test", value="invalid")
        context = {"test_context": "value"}
        
        logged_error = error_handler._log_error(error, context)
        
        assert logged_error['error_id'] is not None
        assert logged_error['error_code'] == "VALIDATION_ERROR"
        assert logged_error['message'] == "Test validation error"
        assert logged_error['context'] == context
        assert logged_error['severity'] == ErrorSeverity.LOW.value
    
    def test_error_statistics(self, error_handler):
        """Test error statistics tracking."""
        # Generate some errors
        errors = [
            ValidationError("Error 1"),
            DatabaseError("Error 2"),
            ValidationError("Error 3"),
            ExternalAPIError(service="test")
        ]
        
        for error in errors:
            error_handler._log_error(error, {})
        
        stats = error_handler.get_error_statistics()
        
        assert stats['total_errors'] == 4
        assert stats['error_counts_by_type']['VALIDATION_ERROR'] == 2
        assert stats['error_counts_by_type']['DATABASE_ERROR'] == 1
        assert stats['error_counts_by_type']['EXTERNAL_API_ERROR'] == 1
    
    def test_recent_errors(self, error_handler):
        """Test recent errors tracking."""
        # Generate some errors
        for i in range(5):
            error = ValidationError(f"Error {i}")
            error_handler._log_error(error, {"index": i})
        
        recent = error_handler.get_recent_errors(limit=3)
        
        assert len(recent) == 3
        # Should return most recent errors
        assert recent[-1]['context']['index'] == 4
        assert recent[-2]['context']['index'] == 3
        assert recent[-3]['context']['index'] == 2
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, error_handler):
        """Test circuit breaker integration with error handler."""
        call_count = 0
        
        async def failing_service():
            nonlocal call_count
            call_count += 1
            raise DatabaseError(f"Service failure {call_count}")
        
        # Get circuit breaker
        breaker = error_handler.get_circuit_breaker(
            "test_service",
            failure_threshold=2,
            timeout_seconds=0.1
        )
        
        # First two calls should fail but not open circuit
        for i in range(2):
            with pytest.raises(ExternalAPIError):
                await error_handler.execute_with_circuit_breaker(
                    "test_service", failing_service
                )
        
        assert breaker.state == CircuitBreakerState.OPEN
        
        # Next call should be blocked by circuit breaker
        with pytest.raises(ExternalAPIError) as exc_info:
            await error_handler.execute_with_circuit_breaker(
                "test_service", failing_service
            )
        
        # Should not have called the service (call_count should still be 2)
        assert call_count == 2
    
    def test_user_message_creation(self, error_handler):
        """Test user-friendly message creation."""
        # Test with PredictionMarketError
        error = InsufficientBalanceError(required=1000, available=500, user_id=12345)
        message = error_handler._create_user_message(error, "TEST123")
        
        assert "💰 You need 1,000 points but only have 500 available!" in message
        
        # Test with generic exception
        error = ValueError("Generic error")
        message = error_handler._create_user_message(error, "TEST456")
        
        assert "⚠️ **Unexpected Error**" in message
        assert "Error ID: TEST456" in message


class TestHandleErrorsDecorator:
    """Test the handle_errors decorator."""
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.id = 12345
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        # is_done() should be a regular method, not async
        interaction.response.is_done = MagicMock(return_value=False)
        return interaction
    
    @pytest.mark.asyncio
    async def test_handle_errors_decorator_success(self, mock_interaction):
        """Test decorator with successful function."""
        @handle_errors(interaction_error=True, log_errors=True)
        async def successful_function(interaction):
            return "success"
        
        result = await successful_function(mock_interaction)
        assert result == "success"
        
        # No error handling should have occurred
        mock_interaction.response.send_message.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_errors_decorator_with_error(self, mock_interaction):
        """Test decorator with function that raises error."""
        @handle_errors(interaction_error=True, log_errors=True)
        async def failing_function(interaction):
            raise ValidationError("Test error")
        
        # Should not raise exception due to decorator
        result = await failing_function(mock_interaction)
        assert result is None
        
        # Should have sent error message
        mock_interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_errors_decorator_reraise(self, mock_interaction):
        """Test decorator with reraise=True."""
        @handle_errors(interaction_error=True, log_errors=True, reraise=True)
        async def failing_function(interaction):
            raise ValidationError("Test error")
        
        # Should reraise the exception
        with pytest.raises(ValidationError):
            await failing_function(mock_interaction)
        
        # But should still handle the error
        mock_interaction.response.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_integration_scenario():
    """Test a complete integration scenario."""
    error_handler = ErrorHandler()
    
    # Simulate a complex operation with multiple failure points
    call_count = 0
    
    @retry_with_backoff(max_retries=2, base_delay=0.01, exceptions=(DatabaseError,))
    async def complex_operation(user_id: int, amount: int):
        nonlocal call_count
        call_count += 1
        
        # Validate input
        if amount <= 0:
            raise ValidationError("Amount must be positive", field="amount", value=amount)
        
        # Simulate database operation that might fail
        if call_count < 2:
            raise DatabaseError("Temporary connection issue", operation="complex_op")
        
        # Simulate external API call with circuit breaker
        return await error_handler.execute_with_circuit_breaker(
            "external_service",
            lambda: {"result": "success", "user_id": user_id, "amount": amount}
        )
    
    # Test successful scenario
    result = await complex_operation(12345, 1000)
    assert result["result"] == "success"
    assert result["user_id"] == 12345
    assert result["amount"] == 1000
    assert call_count == 2  # Should have retried once
    
    # Test validation error (should not retry)
    call_count = 0
    with pytest.raises(ValidationError):
        await complex_operation(12345, -100)
    assert call_count == 1  # Should not have retried validation error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])