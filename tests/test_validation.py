"""
Comprehensive tests for the validation framework.

Tests cover:
- Core validation methods
- Input sanitization
- Validation decorators
- Discord command middleware
- Custom validators
- Error handling
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

import discord

from core.validation import Validator, ValidationResult, validate_input
from core.validation_middleware import (
    ValidationMiddleware, 
    RateLimiter, 
    PermissionChecker,
    rate_limit,
    admin_only,
    moderator_only,
    validate_inputs
)
from core.exceptions import (
    ValidationError,
    RateLimitExceededError,
    InsufficientPermissionsError
)
from models.schemas import CreatePredictionRequest, PlaceBetRequest


class TestValidator:
    """Test the core Validator class"""
    
    def test_sanitize_text_basic(self):
        """Test basic text sanitization"""
        # Normal text
        result = Validator.sanitize_text("Hello World!")
        assert result == "Hello World!"
        
        # Text with extra whitespace
        result = Validator.sanitize_text("  Hello   World  ")
        assert result == "Hello World"
        
        # Text with max length
        result = Validator.sanitize_text("Hello World", max_length=5)
        assert result == "Hello"
    
    def test_sanitize_text_injection_prevention(self):
        """Test injection attack prevention"""
        # Script injection
        result = Validator.sanitize_text("<script>alert('xss')</script>Hello")
        assert "script" not in result.lower()
        assert "alert" not in result.lower()
        
        # HTML tags
        result = Validator.sanitize_text("<div>Hello</div>")
        assert result == "Hello"
        
        # JavaScript protocol
        result = Validator.sanitize_text("javascript:alert('xss')")
        assert "javascript:" not in result.lower()
    
    def test_validate_discord_id(self):
        """Test Discord ID validation"""
        # Valid Discord ID
        result = Validator.validate_discord_id("123456789012345678")
        assert result.is_valid
        assert result.sanitized_data == 123456789012345678
        
        # Valid Discord ID as int
        result = Validator.validate_discord_id(123456789012345678)
        assert result.is_valid
        assert result.sanitized_data == 123456789012345678
        
        # Invalid format
        result = Validator.validate_discord_id("invalid")
        assert not result.is_valid
        assert "Invalid Discord ID" in result.errors[0]
        
        # Too short
        result = Validator.validate_discord_id("12345")
        assert not result.is_valid
        
        # Negative number
        result = Validator.validate_discord_id(-123)
        assert not result.is_valid
    
    def test_validate_prediction_question(self):
        """Test prediction question validation"""
        # Valid question
        result = Validator.validate_prediction_question("Will it rain tomorrow?")
        assert result.is_valid
        assert result.sanitized_data == "Will it rain tomorrow?"
        
        # Question without question mark
        result = Validator.validate_prediction_question("Will it rain tomorrow")
        assert result.is_valid
        assert result.sanitized_data == "Will it rain tomorrow?"
        assert "Added question mark" in result.warnings[0]
        
        # Empty question
        result = Validator.validate_prediction_question("")
        assert not result.is_valid
        assert "cannot be empty" in result.errors[0]
        
        # Too short
        result = Validator.validate_prediction_question("Short?")
        assert not result.is_valid
        assert "at least 10 characters" in result.errors[0]
        
        # Too long
        long_question = "A" * 501
        result = Validator.validate_prediction_question(long_question)
        assert not result.is_valid
        assert "cannot exceed 500 characters" in result.errors[0]
        
        # Potential injection
        result = Validator.validate_prediction_question("Will there be a SELECT * FROM users?")
        assert not result.is_valid
        assert "dangerous content" in result.errors[0]
    
    def test_validate_prediction_options(self):
        """Test prediction options validation"""
        # Valid options
        result = Validator.validate_prediction_options(["Yes", "No"])
        assert result.is_valid
        assert result.sanitized_data == ["Yes", "No"]
        
        # Valid options with more variety
        result = Validator.validate_prediction_options(["Option A", "Option B", "Option C"])
        assert result.is_valid
        assert len(result.sanitized_data) == 3
        
        # Too few options
        result = Validator.validate_prediction_options(["Yes"])
        assert not result.is_valid
        assert "At least 2 options" in result.errors[0]
        
        # Empty options list
        result = Validator.validate_prediction_options([])
        assert not result.is_valid
        
        # Duplicate options
        result = Validator.validate_prediction_options(["Yes", "No", "yes"])
        assert not result.is_valid  # Should flag duplicates as error
        assert "Duplicate option" in result.errors[0]
        
        # Too many options
        many_options = [f"Option {i}" for i in range(15)]
        result = Validator.validate_prediction_options(many_options)
        assert not result.is_valid
        assert "Maximum 10 options" in result.errors[0]
        
        # Empty option
        result = Validator.validate_prediction_options(["Yes", "", "No"])
        assert not result.is_valid
        assert "cannot be empty" in result.errors[0]
        
        # Option too long
        long_option = "A" * 101
        result = Validator.validate_prediction_options(["Yes", long_option])
        assert not result.is_valid
        assert "cannot exceed 100 characters" in result.errors[0]
    
    def test_validate_bet_amount(self):
        """Test bet amount validation"""
        # Valid amount
        result = Validator.validate_bet_amount(100)
        assert result.is_valid
        assert result.sanitized_data == 100
        
        # Valid amount as string
        result = Validator.validate_bet_amount("100")
        assert result.is_valid
        assert result.sanitized_data == 100
        
        # Amount with formatting
        result = Validator.validate_bet_amount("1,000")
        assert result.is_valid
        assert result.sanitized_data == 1000
        
        # Float amount
        result = Validator.validate_bet_amount(100.5)
        assert result.is_valid
        assert result.sanitized_data == 100
        
        # Zero amount
        result = Validator.validate_bet_amount(0)
        assert not result.is_valid
        assert "must be positive" in result.errors[0]
        
        # Negative amount
        result = Validator.validate_bet_amount(-100)
        assert not result.is_valid
        assert "must be positive" in result.errors[0]
        
        # Below minimum
        result = Validator.validate_bet_amount(5, min_amount=10)
        assert not result.is_valid
        assert "Minimum bet amount is 10" in result.errors[0]
        
        # Above maximum
        result = Validator.validate_bet_amount(2000000, max_amount=1000000)
        assert not result.is_valid
        assert "Maximum bet amount is 1,000,000" in result.errors[0]
        
        # Invalid format
        result = Validator.validate_bet_amount("invalid")
        assert not result.is_valid
        assert "valid number" in result.errors[0]
    
    def test_validate_duration(self):
        """Test duration validation"""
        # Valid durations
        result = Validator.validate_duration("1h")
        assert result.is_valid
        assert isinstance(result.sanitized_data, datetime)
        
        result = Validator.validate_duration("2d")
        assert result.is_valid
        
        result = Validator.validate_duration("1w")
        assert result.is_valid
        
        result = Validator.validate_duration("30m")
        assert result.is_valid
        
        # Complex duration
        result = Validator.validate_duration("1d2h30m")
        assert result.is_valid
        
        # Too short
        result = Validator.validate_duration("2m", min_minutes=5)
        assert not result.is_valid
        assert "at least 5 minutes" in result.errors[0]
        
        # Too long
        result = Validator.validate_duration("1000h", max_hours=720)
        assert not result.is_valid
        assert "cannot exceed 720 hours" in result.errors[0]
        
        # Invalid format
        result = Validator.validate_duration("invalid")
        assert not result.is_valid
        assert ("Invalid character in duration" in result.errors[0] or 
                "Invalid duration format" in result.errors[0])
        
        # Empty duration
        result = Validator.validate_duration("")
        assert not result.is_valid
        assert "cannot be empty" in result.errors[0]
    
    def test_validate_category(self):
        """Test category validation"""
        # Valid category
        result = Validator.validate_category("sports")
        assert result.is_valid
        assert result.sanitized_data == "sports"
        
        # Empty category (should default)
        result = Validator.validate_category("")
        assert result.is_valid
        assert result.sanitized_data == "general"
        
        # None category
        result = Validator.validate_category(None)
        assert result.is_valid
        assert result.sanitized_data == "general"
        
        # Category with mixed case
        result = Validator.validate_category("SPORTS")
        assert result.is_valid
        assert result.sanitized_data == "sports"
        
        # Custom category (not in predefined list)
        result = Validator.validate_category("custom")
        assert result.is_valid
        assert result.sanitized_data == "custom"
        assert "not in predefined list" in result.warnings[0]
        
        # Too long category
        long_category = "A" * 51
        result = Validator.validate_category(long_category)
        assert not result.is_valid
        assert "cannot exceed 50 characters" in result.errors[0]
    
    def test_validate_user_balance(self):
        """Test user balance validation"""
        # Sufficient balance
        result = Validator.validate_user_balance(123, 100, 500)
        assert result.is_valid
        
        # Insufficient balance
        result = Validator.validate_user_balance(123, 600, 500)
        assert not result.is_valid
        assert "Insufficient balance" in result.errors[0]
        assert "Required: 600" in result.errors[0]
        assert "Available: 500" in result.errors[0]
    
    def test_validate_prediction_id(self):
        """Test prediction ID validation"""
        # Valid ID
        result = Validator.validate_prediction_id("pred-123")
        assert result.is_valid
        assert result.sanitized_data == "pred-123"
        
        # Valid ID with underscores
        result = Validator.validate_prediction_id("pred_123_test")
        assert result.is_valid
        
        # Empty ID
        result = Validator.validate_prediction_id("")
        assert not result.is_valid
        assert "cannot be empty" in result.errors[0]
        
        # Invalid characters
        result = Validator.validate_prediction_id("pred@123")
        assert not result.is_valid
        assert "Invalid prediction ID format" in result.errors[0]
        
        # Too long
        long_id = "A" * 51
        result = Validator.validate_prediction_id(long_id)
        assert not result.is_valid
    
    def test_validate_pydantic_model(self):
        """Test Pydantic model validation"""
        # Valid data
        data = {
            "question": "Will it rain tomorrow?",
            "options": ["Yes", "No"],
            "duration_minutes": 1440
        }
        result = Validator.validate_pydantic_model(CreatePredictionRequest, data)
        assert result.is_valid
        assert isinstance(result.sanitized_data, CreatePredictionRequest)
        
        # Invalid data
        invalid_data = {
            "question": "Short",  # Too short
            "options": ["Yes"],   # Too few options
            "duration_minutes": -1  # Invalid duration
        }
        result = Validator.validate_pydantic_model(CreatePredictionRequest, invalid_data)
        assert not result.is_valid
        assert len(result.errors) > 0


class TestValidationDecorator:
    """Test the validation decorator"""
    
    @pytest.mark.asyncio
    async def test_validate_input_decorator_async(self):
        """Test validation decorator with async function"""
        
        @validate_input(
            user_id=Validator.validate_discord_id,
            amount=lambda x: Validator.validate_bet_amount(x, min_amount=10)
        )
        async def test_function(user_id: int, amount: int):
            return f"User {user_id} bet {amount}"
        
        # Valid inputs
        result = await test_function("123456789012345678", 100)
        assert "User 123456789012345678 bet 100" in result
        
        # Invalid user ID
        with pytest.raises(ValidationError) as exc_info:
            await test_function("invalid", 100)
        assert "validation failed" in str(exc_info.value).lower()
        
        # Invalid amount
        with pytest.raises(ValidationError) as exc_info:
            await test_function("123456789012345678", 5)
        assert "validation failed" in str(exc_info.value).lower()
    
    def test_validate_input_decorator_sync(self):
        """Test validation decorator with sync function"""
        
        @validate_input(
            text=lambda x: Validator.validate_prediction_question(x)
        )
        def test_function(text: str):
            return f"Question: {text}"
        
        # Valid input
        result = test_function("Will it rain tomorrow?")
        assert "Will it rain tomorrow?" in result
        
        # Invalid input
        with pytest.raises(ValidationError):
            test_function("Short")


class TestRateLimiter:
    """Test the rate limiter"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_basic(self):
        """Test basic rate limiting functionality"""
        limiter = RateLimiter()
        
        # First request should pass
        result = await limiter.check_rate_limit("test_key", 2, 60)
        assert result is True
        
        # Second request should pass
        result = await limiter.check_rate_limit("test_key", 2, 60)
        assert result is True
        
        # Third request should fail
        result = await limiter.check_rate_limit("test_key", 2, 60)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_rate_limiter_window_reset(self):
        """Test rate limiter window reset"""
        limiter = RateLimiter()
        
        # Fill up the limit
        await limiter.check_rate_limit("test_key", 1, 1)
        
        # Should be rate limited
        result = await limiter.check_rate_limit("test_key", 1, 1)
        assert result is False
        
        # Wait for window to reset
        await asyncio.sleep(1.1)
        
        # Should work again
        result = await limiter.check_rate_limit("test_key", 1, 1)
        assert result is True
    
    def test_rate_limiter_remaining_time(self):
        """Test remaining time calculation"""
        limiter = RateLimiter()
        
        # No requests yet
        remaining = limiter.get_remaining_time("test_key", 60)
        assert remaining == 0


class TestPermissionChecker:
    """Test the permission checker"""
    
    def test_has_admin_permissions(self):
        """Test admin permission checking"""
        # Mock interaction with admin permissions
        interaction = Mock()
        interaction.user.guild_permissions.administrator = True
        
        result = PermissionChecker.has_admin_permissions(interaction)
        assert result is True
        
        # Mock interaction without admin permissions
        interaction.user.guild_permissions.administrator = False
        result = PermissionChecker.has_admin_permissions(interaction)
        assert result is False
    
    def test_has_moderator_permissions(self):
        """Test moderator permission checking"""
        # Mock interaction with admin (should pass)
        interaction = Mock()
        interaction.user.guild_permissions.administrator = True
        
        result = PermissionChecker.has_moderator_permissions(interaction)
        assert result is True
        
        # Mock interaction with moderator role
        interaction.user.guild_permissions.administrator = False
        interaction.user.guild_permissions.manage_messages = True
        
        result = PermissionChecker.has_moderator_permissions(interaction)
        assert result is True
        
        # Mock interaction without permissions
        interaction.user.guild_permissions.manage_messages = False
        interaction.user.guild_permissions.manage_guild = False
        
        result = PermissionChecker.has_moderator_permissions(interaction)
        assert result is False
    
    def test_has_creator_permissions(self):
        """Test creator permission checking"""
        # Mock interaction with admin (should pass)
        interaction = Mock()
        interaction.user.guild_permissions.administrator = True
        
        result = PermissionChecker.has_creator_permissions(interaction)
        assert result is True
        
        # Mock interaction with custom creator roles
        interaction.user.guild_permissions.administrator = False
        role_mock = Mock()
        role_mock.id = 123456
        interaction.user.roles = [role_mock]
        
        result = PermissionChecker.has_creator_permissions(interaction, creator_roles=[123456])
        assert result is True
        
        result = PermissionChecker.has_creator_permissions(interaction, creator_roles=[999999])
        assert result is False


class TestValidationMiddleware:
    """Test the validation middleware"""
    
    @pytest.mark.asyncio
    async def test_validation_middleware_rate_limiting(self):
        """Test middleware rate limiting"""
        middleware = ValidationMiddleware()
        
        # Mock interaction
        interaction = Mock()
        interaction.user.id = 123456
        interaction.guild.id = 789012
        interaction.response.send_message = AsyncMock()
        interaction.response.is_done.return_value = False
        interaction.followup.send = AsyncMock()
        
        # Mock function with proper code attributes
        mock_func = AsyncMock(return_value="success")
        mock_func.__name__ = "test_command"
        mock_func.__code__ = Mock()
        mock_func.__code__.co_varnames = ['self', 'interaction']
        mock_func.__code__.co_argcount = 2
        
        # Create decorated function
        decorated = middleware.validate_command(
            rate_limit_config={'limit': 1, 'window': 60, 'per_user': True}
        )(mock_func)
        
        # First call should succeed
        await decorated(None, interaction)
        mock_func.assert_called_once()
        
        # Second call should be rate limited
        mock_func.reset_mock()
        await decorated(None, interaction)
        mock_func.assert_not_called()
        interaction.response.send_message.assert_called()
    
    @pytest.mark.asyncio
    async def test_validation_middleware_permissions(self):
        """Test middleware permission checking"""
        middleware = ValidationMiddleware()
        
        # Mock interaction without admin permissions
        interaction = Mock()
        interaction.user.guild_permissions.administrator = False
        interaction.response.send_message = AsyncMock()
        interaction.response.is_done.return_value = False
        interaction.followup.send = AsyncMock()
        
        # Mock function with proper code attributes
        mock_func = AsyncMock()
        mock_func.__name__ = "test_command"
        mock_func.__code__ = Mock()
        mock_func.__code__.co_varnames = ['self', 'interaction']
        mock_func.__code__.co_argcount = 2
        
        # Create decorated function requiring admin
        decorated = middleware.validate_command(
            permission_config={'admin_only': True}
        )(mock_func)
        
        # Should fail permission check
        await decorated(None, interaction)
        mock_func.assert_not_called()
        interaction.response.send_message.assert_called()
    
    @pytest.mark.asyncio
    async def test_validation_middleware_input_sanitization(self):
        """Test middleware input sanitization"""
        middleware = ValidationMiddleware()
        
        # Mock interaction
        interaction = Mock()
        interaction.response.send_message = AsyncMock()
        interaction.response.is_done.return_value = False
        interaction.followup.send = AsyncMock()
        
        # Mock function that captures arguments
        captured_args = []
        
        # Create a mock function with proper attributes
        mock_func = AsyncMock()
        mock_func.__name__ = "test_command"
        mock_func.__code__ = Mock()
        mock_func.__code__.co_varnames = ('self', 'interaction', 'text_arg')
        mock_func.__code__.co_argcount = 3
        
        # Override the mock to capture arguments
        async def capture_args(cog_self, interaction, text_arg):
            captured_args.append(text_arg)
            return "success"
        
        mock_func.side_effect = capture_args
        
        # Create decorated function with sanitization
        decorated = middleware.validate_command(sanitize_inputs=True)(mock_func)
        
        # Call with potentially dangerous input
        dangerous_input = "<script>alert('xss')</script>Hello"
        await decorated(None, interaction, dangerous_input)
        
        # Check that input was sanitized
        assert len(captured_args) == 1
        assert "script" not in captured_args[0].lower()
        assert "Hello" in captured_args[0]


class TestConvenienceDecorators:
    """Test convenience decorators"""
    
    @pytest.mark.asyncio
    async def test_rate_limit_decorator(self):
        """Test rate limit convenience decorator"""
        
        @rate_limit(limit=1, window=60)
        async def test_command(self, interaction):
            return "success"
        
        # Mock interaction
        interaction = Mock()
        interaction.user.id = 123456
        interaction.response.send_message = AsyncMock()
        interaction.response.is_done.return_value = False
        interaction.followup.send = AsyncMock()
        
        # First call should work
        result = await test_command(None, interaction)
        assert result == "success"
        
        # Second call should be rate limited
        await test_command(None, interaction)
        interaction.response.send_message.assert_called()
    
    @pytest.mark.asyncio
    async def test_admin_only_decorator(self):
        """Test admin only convenience decorator"""
        
        @admin_only()
        async def test_command(self, interaction):
            return "admin success"
        
        # Mock admin interaction
        interaction = Mock()
        interaction.user.id = 123456
        interaction.user.guild_permissions.administrator = True
        
        result = await test_command(None, interaction)
        assert result == "admin success"
        
        # Mock non-admin interaction
        interaction.user.guild_permissions.administrator = False
        interaction.response.send_message = AsyncMock()
        interaction.response.is_done.return_value = False
        interaction.followup.send = AsyncMock()
        
        await test_command(None, interaction)
        interaction.response.send_message.assert_called()


# Integration tests
class TestValidationIntegration:
    """Integration tests combining multiple validation components"""
    
    @pytest.mark.asyncio
    async def test_full_validation_pipeline(self):
        """Test complete validation pipeline"""
        
        class TestService:
            @validate_input(
                user_id=Validator.validate_discord_id,
                question=Validator.validate_prediction_question,
                options=Validator.validate_prediction_options
            )
            async def create_prediction(self, user_id: int, question: str, options: list):
                return {
                    'user_id': user_id,
                    'question': question,
                    'options': options
                }
        
        service = TestService()
        
        # Valid inputs
        result = await service.create_prediction(
            user_id="123456789012345678",
            question="Will it rain tomorrow?",
            options=["Yes", "No"]
        )
        
        assert result['user_id'] == 123456789012345678
        assert result['question'] == "Will it rain tomorrow?"
        assert result['options'] == ["Yes", "No"]
        
        # Invalid inputs should raise ValidationError
        with pytest.raises(ValidationError):
            await service.create_prediction(
                user_id="invalid",
                question="Short",
                options=["Yes"]
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])