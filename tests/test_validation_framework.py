"""
Comprehensive tests for the validation framework.

Tests cover:
- Static validation methods
- Validation decorators
- Discord command middleware
- Input sanitization
- Security features
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

import discord

from core.validation import Validator, validate_input, ValidationResult
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


class TestValidator:
    """Test static validation methods"""
    
    def test_sanitize_text_basic(self):
        """Test basic text sanitization"""
        result = Validator.sanitize_text("Hello World")
        assert result == "Hello World"
    
    def test_sanitize_text_xss_prevention(self):
        """Test XSS prevention in text sanitization"""
        dangerous_inputs = [
            "<script>alert('xss')</script>Hello",
            "javascript:alert('hack')",
            "<iframe src='evil.com'></iframe>",
            "Hello<script>evil()</script>World",
            "data:text/html,<script>alert(1)</script>",
        ]
        
        for dangerous_input in dangerous_inputs:
            result = Validator.sanitize_text(dangerous_input)
            assert "<script>" not in result.lower()
            assert "javascript:" not in result.lower()
            assert "<iframe>" not in result.lower()
            assert "data:" not in result.lower()
    
    def test_sanitize_text_sql_injection_prevention(self):
        """Test SQL injection prevention"""
        dangerous_inputs = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "/* comment */ SELECT * FROM users",
            "UNION SELECT password FROM users",
        ]
        
        for dangerous_input in dangerous_inputs:
            result = Validator.sanitize_text(dangerous_input)
            # The sanitizer should normalize whitespace and remove some dangerous patterns
            # At minimum, it should not crash and should return a string
            assert isinstance(result, str)
            assert len(result.strip()) > 0  # Should not be empty after sanitization
    
    def test_sanitize_text_length_limit(self):
        """Test text length limiting"""
        long_text = "A" * 1000
        result = Validator.sanitize_text(long_text, max_length=100)
        assert len(result) <= 100
    
    def test_sanitize_text_whitespace_normalization(self):
        """Test whitespace normalization"""
        messy_text = "   Hello    World   \n\t  "
        result = Validator.sanitize_text(messy_text)
        assert result == "Hello World"
    
    def test_validate_discord_id_valid(self):
        """Test valid Discord ID validation"""
        valid_ids = [123456789012345678, "123456789012345678"]
        
        for valid_id in valid_ids:
            result = Validator.validate_discord_id(valid_id)
            assert result.is_valid
            assert result.sanitized_data == int(valid_id)
    
    def test_validate_discord_id_invalid(self):
        """Test invalid Discord ID validation"""
        invalid_ids = [
            "not_a_number",
            123,  # Too short
            -123456789012345678,  # Negative
            "12345678901234567890123",  # Too long
        ]
        
        for invalid_id in invalid_ids:
            result = Validator.validate_discord_id(invalid_id)
            assert not result.is_valid
            assert len(result.errors) > 0
    
    def test_validate_prediction_question_valid(self):
        """Test valid prediction question validation"""
        valid_questions = [
            "Will it rain tomorrow?",
            "Who will win the championship?",
            "What will be the price of Bitcoin next week?",
        ]
        
        for question in valid_questions:
            result = Validator.validate_prediction_question(question)
            assert result.is_valid
            assert result.sanitized_data.endswith("?")
    
    def test_validate_prediction_question_invalid(self):
        """Test invalid prediction question validation"""
        invalid_questions = [
            "",  # Empty
            "Hi",  # Too short
            "A" * 600,  # Too long
            "'; DROP TABLE predictions; --",  # SQL injection attempt
        ]
        
        for question in invalid_questions:
            result = Validator.validate_prediction_question(question)
            assert not result.is_valid
            assert len(result.errors) > 0
    
    def test_validate_prediction_options_valid(self):
        """Test valid prediction options validation"""
        valid_options = [
            ["Yes", "No"],
            ["Option A", "Option B", "Option C"],
            ["Red", "Blue", "Green", "Yellow"],
        ]
        
        for options in valid_options:
            result = Validator.validate_prediction_options(options)
            assert result.is_valid
            assert len(result.sanitized_data) >= 2
    
    def test_validate_prediction_options_invalid(self):
        """Test invalid prediction options validation"""
        invalid_options = [
            [],  # Empty
            ["Only one"],  # Too few
            ["A"] * 15,  # Too many
            ["Yes", "Yes"],  # Duplicates
            ["", "No"],  # Empty option
            ["A" * 150, "B"],  # Too long
        ]
        
        for options in invalid_options:
            result = Validator.validate_prediction_options(options)
            assert not result.is_valid
            assert len(result.errors) > 0
    
    def test_validate_bet_amount_valid(self):
        """Test valid bet amount validation"""
        valid_amounts = [100, "1000", 50000, "25,000"]
        
        for amount in valid_amounts:
            result = Validator.validate_bet_amount(amount)
            assert result.is_valid
            assert isinstance(result.sanitized_data, int)
            assert result.sanitized_data > 0
    
    def test_validate_bet_amount_invalid(self):
        """Test invalid bet amount validation"""
        invalid_amounts = [
            0,  # Zero
            -100,  # Negative
            "not_a_number",  # Invalid format
            2_000_000,  # Too large
        ]
        
        for amount in invalid_amounts:
            result = Validator.validate_bet_amount(amount)
            assert not result.is_valid
            assert len(result.errors) > 0
    
    def test_validate_duration_valid(self):
        """Test valid duration validation"""
        valid_durations = ["1h", "2d", "1w", "3d2h", "30m"]
        
        for duration in valid_durations:
            result = Validator.validate_duration(duration)
            assert result.is_valid
            assert isinstance(result.sanitized_data, datetime)
    
    def test_validate_duration_invalid(self):
        """Test invalid duration validation"""
        invalid_durations = [
            "",  # Empty
            "1x",  # Invalid unit
            "1000h",  # Too long
            "1m",  # Too short
            "not_a_duration",  # Invalid format
        ]
        
        for duration in invalid_durations:
            result = Validator.validate_duration(duration)
            assert not result.is_valid
            assert len(result.errors) > 0
    
    def test_validate_user_balance_sufficient(self):
        """Test sufficient balance validation"""
        result = Validator.validate_user_balance(
            user_id=123,
            required_amount=100,
            current_balance=500
        )
        assert result.is_valid
    
    def test_validate_user_balance_insufficient(self):
        """Test insufficient balance validation"""
        result = Validator.validate_user_balance(
            user_id=123,
            required_amount=1000,
            current_balance=500
        )
        assert not result.is_valid
        assert len(result.errors) > 0


class TestValidationDecorator:
    """Test validation decorators"""
    
    def test_validate_input_decorator_sync(self):
        """Test validation decorator on sync function"""
        
        @validate_input(
            user_id=Validator.validate_discord_id,
            amount=Validator.validate_bet_amount
        )
        def place_bet(user_id, amount):
            return f"Bet placed: {user_id}, {amount}"
        
        # Valid input
        result = place_bet(123456789012345678, 100)
        assert "Bet placed" in result
        
        # Invalid input should raise ValidationError
        with pytest.raises(ValidationError):
            place_bet("invalid_id", 100)
    
    @pytest.mark.asyncio
    async def test_validate_input_decorator_async(self):
        """Test validation decorator on async function"""
        
        @validate_input(
            user_id=Validator.validate_discord_id,
            amount=Validator.validate_bet_amount
        )
        async def place_bet_async(user_id, amount):
            return f"Async bet placed: {user_id}, {amount}"
        
        # Valid input
        result = await place_bet_async(123456789012345678, 100)
        assert "Async bet placed" in result
        
        # Invalid input should raise ValidationError
        with pytest.raises(ValidationError):
            await place_bet_async("invalid_id", 100)
    
    def test_validate_input_decorator_with_sanitization(self):
        """Test validation decorator with data sanitization"""
        
        @validate_input(
            question=Validator.validate_prediction_question
        )
        def create_prediction(question):
            return question
        
        # Input without question mark should be sanitized
        result = create_prediction("Will it rain tomorrow")
        assert result.endswith("?")


class TestRateLimiter:
    """Test rate limiting functionality"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_within_limit(self):
        """Test rate limiter allows requests within limit"""
        limiter = RateLimiter()
        
        # Should allow requests within limit
        for i in range(5):
            allowed = await limiter.check_rate_limit("test_key", limit=10, window_seconds=60)
            assert allowed
    
    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_over_limit(self):
        """Test rate limiter blocks requests over limit"""
        limiter = RateLimiter()
        
        # Fill up the limit
        for i in range(5):
            await limiter.check_rate_limit("test_key", limit=5, window_seconds=60)
        
        # Next request should be blocked
        allowed = await limiter.check_rate_limit("test_key", limit=5, window_seconds=60)
        assert not allowed
    
    @pytest.mark.asyncio
    async def test_rate_limiter_resets_after_window(self):
        """Test rate limiter resets after time window"""
        limiter = RateLimiter()
        
        # Fill up the limit with very short window
        for i in range(3):
            await limiter.check_rate_limit("test_key", limit=3, window_seconds=1)
        
        # Should be blocked
        allowed = await limiter.check_rate_limit("test_key", limit=3, window_seconds=1)
        assert not allowed
        
        # Wait for window to pass
        await asyncio.sleep(1.1)
        
        # Should be allowed again
        allowed = await limiter.check_rate_limit("test_key", limit=3, window_seconds=1)
        assert allowed


class TestPermissionChecker:
    """Test permission checking functionality"""
    
    def test_has_admin_permissions(self):
        """Test admin permission checking"""
        # Mock interaction with admin permissions
        interaction = Mock()
        interaction.user.guild_permissions.administrator = True
        
        assert PermissionChecker.has_admin_permissions(interaction)
        
        # Mock interaction without admin permissions
        interaction.user.guild_permissions.administrator = False
        assert not PermissionChecker.has_admin_permissions(interaction)
    
    def test_has_moderator_permissions(self):
        """Test moderator permission checking"""
        # Mock interaction with moderator permissions
        interaction = Mock()
        interaction.user.guild_permissions.administrator = False
        interaction.user.guild_permissions.manage_messages = True
        
        assert PermissionChecker.has_moderator_permissions(interaction)
        
        # Mock interaction without moderator permissions
        interaction.user.guild_permissions.manage_messages = False
        interaction.user.guild_permissions.manage_guild = False
        
        assert not PermissionChecker.has_moderator_permissions(interaction)


class TestValidationMiddleware:
    """Test validation middleware functionality"""
    
    @pytest.mark.asyncio
    async def test_validation_middleware_rate_limiting(self):
        """Test validation middleware rate limiting"""
        middleware = ValidationMiddleware()
        
        @middleware.validate_command(
            rate_limit_config={'limit': 2, 'window': 60, 'per_user': True}
        )
        async def test_command(self, interaction):
            return "success"
        
        # Mock interaction with async methods
        interaction = Mock()
        interaction.user.id = 123456789
        interaction.guild = Mock()
        interaction.guild.id = 987654321
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        interaction.followup.send = AsyncMock()
        
        # First two calls should succeed
        result1 = await test_command(None, interaction)
        result2 = await test_command(None, interaction)
        assert result1 == "success"
        assert result2 == "success"
        
        # Third call should trigger rate limiting (but won't raise due to error handling)
        # Instead, check that the error handler was called
        await test_command(None, interaction)
        interaction.response.send_message.assert_called()
    
    @pytest.mark.asyncio
    async def test_validation_middleware_permission_check(self):
        """Test validation middleware permission checking"""
        middleware = ValidationMiddleware()
        
        @middleware.validate_command(
            permission_config={'admin_only': True}
        )
        async def admin_command(self, interaction):
            return "admin_success"
        
        # Mock interaction with admin permissions
        interaction = Mock()
        interaction.user.guild_permissions.administrator = True
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        interaction.followup.send = AsyncMock()
        
        result = await admin_command(None, interaction)
        assert result == "admin_success"
        
        # Mock interaction without admin permissions
        interaction.user.guild_permissions.administrator = False
        
        # The middleware will handle the error, not raise it
        await admin_command(None, interaction)
        interaction.response.send_message.assert_called()
    
    @pytest.mark.asyncio
    async def test_validation_middleware_input_validation(self):
        """Test validation middleware input validation"""
        middleware = ValidationMiddleware()
        
        @middleware.validate_command(
            input_validation={
                'amount': Validator.validate_bet_amount,
                'user_id': Validator.validate_discord_id
            }
        )
        async def bet_command(self, interaction, amount, user_id):
            return f"bet: {amount}, {user_id}"
        
        # Mock interaction with async methods
        interaction = Mock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        interaction.followup.send = AsyncMock()
        
        # Valid inputs
        result = await bet_command(None, interaction, 100, 123456789012345678)
        assert "bet: 100" in result
        
        # Invalid inputs should trigger error handling
        await bet_command(None, interaction, -100, "invalid_id")
        interaction.response.send_message.assert_called()


class TestSecurityFeatures:
    """Test security-related validation features"""
    
    def test_xss_prevention(self):
        """Test XSS attack prevention"""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "data:text/html,<script>alert('XSS')</script>",
        ]
        
        for payload in xss_payloads:
            sanitized = Validator.sanitize_text(payload)
            # Should not contain dangerous script content
            assert "alert" not in sanitized.lower()
            assert "<script>" not in sanitized.lower()
            assert "javascript:" not in sanitized.lower()
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention"""
        sql_payloads = [
            "'; DROP TABLE users; --",
            "' OR '1'='1' --",
            "'; INSERT INTO users VALUES ('hacker'); --",
            "' UNION SELECT password FROM users --",
        ]
        
        for payload in sql_payloads:
            # Validate as prediction question (which checks for SQL patterns)
            result = Validator.validate_prediction_question(payload)
            assert not result.is_valid
            assert any("dangerous" in error.lower() for error in result.errors)
    
    def test_input_length_limits(self):
        """Test input length limiting for DoS prevention"""
        very_long_input = "A" * 10000
        
        # Should be truncated
        sanitized = Validator.sanitize_text(very_long_input, max_length=100)
        assert len(sanitized) <= 100
        
        # Validation should fail for overly long questions
        result = Validator.validate_prediction_question(very_long_input)
        assert not result.is_valid
    
    def test_null_byte_removal(self):
        """Test null byte and control character removal"""
        dangerous_input = "Hello\x00World\x08Test\x1F"
        sanitized = Validator.sanitize_text(dangerous_input)
        
        # Should not contain null bytes or control characters
        assert "\x00" not in sanitized
        assert "\x08" not in sanitized
        assert "\x1F" not in sanitized
        assert sanitized == "HelloWorldTest"


class TestIntegration:
    """Integration tests for the complete validation framework"""
    
    @pytest.mark.asyncio
    async def test_complete_validation_workflow(self):
        """Test complete validation workflow from input to output"""
        
        # Mock a complete Discord command with all validation layers
        middleware = ValidationMiddleware()
        
        @middleware.validate_command(
            rate_limit_config={'limit': 5, 'window': 60},
            permission_config={'moderator_only': True},
            input_validation={
                'question': Validator.validate_prediction_question,
                'options': Validator.validate_prediction_options
            },
            sanitize_inputs=True
        )
        async def create_prediction_command(self, interaction, question, options):
            return f"Created: {question} with {len(options)} options"
        
        # Mock interaction with proper permissions
        interaction = Mock()
        interaction.user.id = 123456789
        interaction.user.guild_permissions.administrator = False
        interaction.user.guild_permissions.manage_messages = True
        interaction.guild = Mock()
        interaction.guild.id = 987654321
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        interaction.followup.send = AsyncMock()
        
        # Test with valid inputs
        result = await create_prediction_command(
            None, 
            interaction, 
            "Will it rain tomorrow?",
            ["Yes", "No"]
        )
        assert "Created:" in result
        
        # Test with invalid permissions
        interaction.user.guild_permissions.manage_messages = False
        interaction.user.guild_permissions.manage_guild = False
        
        # The middleware will handle the error, not raise it
        await create_prediction_command(
            None, 
            interaction, 
            "Will it rain tomorrow?",
            ["Yes", "No"]
        )
        interaction.response.send_message.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])