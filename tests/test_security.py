"""
Tests for security enhancements including input sanitization, audit logging,
token handling, and data encryption.
"""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from core.security import (
    InputSanitizer, TokenManager, DataEncryption, AuditLogger, SecurityMonitor,
    AuditEvent, AuditEventType, SecurityLevel, get_audit_logger, get_security_monitor
)
from core.security_middleware import SecurityMiddleware, CombinedSecurityMiddleware
from core.exceptions import SecurityError, ValidationError


class TestInputSanitizer:
    """Test input sanitization functionality."""
    
    def test_basic_text_sanitization(self):
        """Test basic text sanitization."""
        sanitizer = InputSanitizer()
        
        # Normal text should pass through
        result = sanitizer.sanitize_text("Hello world!")
        assert result == "Hello world!"
        
        # HTML should be removed
        result = sanitizer.sanitize_text("<script>alert('xss')</script>Hello")
        assert result == "Hello"
        
        # Multiple spaces should be normalized
        result = sanitizer.sanitize_text("Hello    world")
        assert result == "Hello world"
    
    def test_script_injection_detection(self):
        """Test detection of script injection attempts."""
        sanitizer = InputSanitizer()
        
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<iframe src='evil.com'></iframe>",
            "on click='alert(1)'",
            "<object data='evil.swf'></object>"
        ]
        
        for malicious_input in malicious_inputs:
            result = sanitizer.sanitize_text(malicious_input)
            # Should remove malicious content
            assert "<script>" not in result.lower()
            assert "javascript:" not in result.lower()
            assert "<iframe" not in result.lower()
    
    def test_sql_injection_detection(self):
        """Test detection of SQL injection attempts."""
        sanitizer = InputSanitizer()
        
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "UNION SELECT * FROM passwords",
            "/* comment */ SELECT",
            "admin'--"
        ]
        
        for malicious_input in malicious_inputs:
            result = sanitizer.sanitize_text(malicious_input)
            # Should remove SQL injection patterns
            assert "drop table" not in result.lower()
            assert "union select" not in result.lower()
            assert "or 1=1" not in result.lower()
    
    def test_strict_mode_security_error(self):
        """Test that strict mode raises SecurityError for malicious input."""
        sanitizer = InputSanitizer()
        
        with pytest.raises(SecurityError):
            sanitizer.sanitize_text("'; DROP TABLE users; --", strict_mode=True)
        
        with pytest.raises(SecurityError):
            sanitizer.sanitize_text("cat /etc/passwd", strict_mode=True)
    
    def test_max_length_truncation(self):
        """Test maximum length truncation."""
        sanitizer = InputSanitizer()
        
        long_text = "A" * 1000
        result = sanitizer.sanitize_text(long_text, max_length=100)
        assert len(result) == 100
    
    def test_discord_id_validation(self):
        """Test Discord ID validation."""
        sanitizer = InputSanitizer()
        
        # Valid Discord IDs
        valid_ids = [123456789012345678, "123456789012345678"]
        for valid_id in valid_ids:
            result = sanitizer.validate_discord_id(valid_id)
            assert isinstance(result, int)
            assert result > 0
        
        # Invalid Discord IDs
        invalid_ids = ["abc", "123", "", None, -1]
        for invalid_id in invalid_ids:
            with pytest.raises(SecurityError):
                sanitizer.validate_discord_id(invalid_id)
    
    def test_filename_validation(self):
        """Test filename validation."""
        sanitizer = InputSanitizer()
        
        # Valid filenames
        valid_names = ["test.txt", "file_name.py", "data-file.json"]
        for valid_name in valid_names:
            result = sanitizer.validate_filename(valid_name)
            assert result == valid_name
        
        # Invalid filenames (path traversal)
        invalid_names = ["../etc/passwd", "file/path.txt", "..\\windows\\system32"]
        for invalid_name in invalid_names:
            with pytest.raises(SecurityError):
                sanitizer.validate_filename(invalid_name)
    
    def test_url_validation(self):
        """Test URL validation."""
        sanitizer = InputSanitizer()
        
        # Valid URLs
        valid_urls = ["https://example.com", "http://api.service.com/endpoint"]
        for valid_url in valid_urls:
            result = sanitizer.validate_url(valid_url)
            assert result == valid_url
        
        # Invalid URLs
        invalid_urls = [
            "javascript:alert('xss')",
            "file:///etc/passwd",
            "http://localhost/admin",
            "https://127.0.0.1/secret"
        ]
        for invalid_url in invalid_urls:
            with pytest.raises(SecurityError):
                sanitizer.validate_url(invalid_url)


class TestTokenManager:
    """Test secure token handling."""
    
    def test_token_encryption_decryption(self):
        """Test token encryption and decryption."""
        token_manager = TokenManager()
        
        original_token = "secret_api_key_12345"
        encrypted_token = token_manager.encrypt_token(original_token)
        decrypted_token = token_manager.decrypt_token(encrypted_token)
        
        assert decrypted_token == original_token
        assert encrypted_token != original_token
    
    def test_secure_token_generation(self):
        """Test secure token generation."""
        token_manager = TokenManager()
        
        token1 = token_manager.generate_secure_token()
        token2 = token_manager.generate_secure_token()
        
        assert len(token1) > 0
        assert len(token2) > 0
        assert token1 != token2  # Should be unique
    
    def test_token_hashing_verification(self):
        """Test token hashing and verification."""
        token_manager = TokenManager()
        
        original_token = "test_token_123"
        token_hash, salt = token_manager.hash_token(original_token)
        
        # Correct token should verify
        assert token_manager.verify_token_hash(original_token, token_hash, salt)
        
        # Wrong token should not verify
        assert not token_manager.verify_token_hash("wrong_token", token_hash, salt)
    
    def test_encryption_with_custom_key(self):
        """Test encryption with custom key."""
        from cryptography.fernet import Fernet
        
        custom_key = Fernet.generate_key()
        token_manager = TokenManager(custom_key)
        
        token = "custom_key_token"
        encrypted = token_manager.encrypt_token(token)
        decrypted = token_manager.decrypt_token(encrypted)
        
        assert decrypted == token


class TestDataEncryption:
    """Test data encryption functionality."""
    
    def test_string_encryption_decryption(self):
        """Test string data encryption and decryption."""
        encryption = DataEncryption("test_password")
        
        original_data = "sensitive information"
        encrypted_data = encryption.encrypt_data(original_data)
        decrypted_data = encryption.decrypt_data(encrypted_data)
        
        assert decrypted_data == original_data
        assert encrypted_data != original_data
    
    def test_dict_encryption_decryption(self):
        """Test dictionary data encryption and decryption."""
        encryption = DataEncryption("test_password")
        
        original_data = {"username": "admin", "password": "secret123"}
        encrypted_data = encryption.encrypt_data(original_data)
        decrypted_data = encryption.decrypt_data(encrypted_data)
        
        # Parse back to dict
        decrypted_dict = json.loads(decrypted_data)
        assert decrypted_dict == original_data
    
    def test_sensitive_fields_encryption(self):
        """Test encryption of specific fields in a dictionary."""
        encryption = DataEncryption("test_password")
        
        data = {
            "user_id": 123,
            "username": "testuser",
            "password": "secret123",
            "api_key": "key_12345"
        }
        
        sensitive_fields = ["password", "api_key"]
        encrypted_data = encryption.encrypt_sensitive_fields(data, sensitive_fields)
        
        # Non-sensitive fields should remain unchanged
        assert encrypted_data["user_id"] == 123
        assert encrypted_data["username"] == "testuser"
        
        # Sensitive fields should be encrypted
        assert encrypted_data["password"] != "secret123"
        assert encrypted_data["api_key"] != "key_12345"
        
        # Decrypt sensitive fields
        decrypted_data = encryption.decrypt_sensitive_fields(encrypted_data, sensitive_fields)
        assert decrypted_data["password"] == "secret123"
        assert decrypted_data["api_key"] == "key_12345"


class TestAuditLogger:
    """Test audit logging functionality."""
    
    def test_audit_event_creation(self):
        """Test audit event creation."""
        event = AuditEvent(
            event_type=AuditEventType.BET_PLACED,
            user_id=123456789,
            guild_id=987654321,
            timestamp=datetime.utcnow(),
            details={"amount": 100, "option": "Yes"},
            success=True,
            security_level=SecurityLevel.MEDIUM
        )
        
        assert event.event_type == AuditEventType.BET_PLACED
        assert event.user_id == 123456789
        assert event.guild_id == 987654321
        assert event.success is True
        assert event.details["amount"] == 100
    
    @patch('core.security.get_logger')
    def test_audit_logging(self, mock_get_logger):
        """Test audit event logging."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        audit_logger = AuditLogger()
        
        event = AuditEvent(
            event_type=AuditEventType.PREDICTION_CREATED,
            user_id=123456789,
            guild_id=987654321,
            timestamp=datetime.utcnow(),
            details={"question": "Will it rain tomorrow?"},
            success=True
        )
        
        audit_logger.log_audit_event(event)
        
        # Verify logger was called
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "Audit Event: prediction_created" in call_args[0][0]
    
    @patch('core.security.get_logger')
    def test_security_violation_logging(self, mock_get_logger):
        """Test security violation logging."""
        mock_logger = Mock()
        mock_security_logger = Mock()
        mock_get_logger.side_effect = lambda name: mock_security_logger if name == "security" else mock_logger
        
        audit_logger = AuditLogger()
        
        audit_logger.log_security_violation(
            violation_type="sql_injection_attempt",
            user_id=123456789,
            details={"input": "'; DROP TABLE users; --"}
        )
        
        # Verify both loggers were called
        mock_logger.info.assert_called_once()
        mock_security_logger.warning.assert_called_once()


class TestSecurityMonitor:
    """Test security monitoring functionality."""
    
    def test_failed_attempt_tracking(self):
        """Test tracking of failed attempts."""
        monitor = SecurityMonitor()
        
        user_id = 123456789
        attempt_type = "login"
        
        # First few attempts should not trigger flag
        for i in range(3):
            result = monitor.track_failed_attempt(user_id, attempt_type)
            assert result is False
        
        # Many attempts should trigger flag
        for i in range(5):
            result = monitor.track_failed_attempt(user_id, attempt_type)
        
        # Last attempt should trigger flag
        assert result is True
    
    def test_rate_limit_abuse_detection(self):
        """Test rate limit abuse detection."""
        monitor = SecurityMonitor()
        
        with patch.object(monitor.audit_logger, 'log_security_violation') as mock_log:
            monitor.detect_rate_limit_abuse(
                user_id=123456789,
                command="bet",
                current_rate=15,
                limit=10
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args[1]
            assert call_args['violation_type'] == "rate_limit_abuse"
            assert call_args['user_id'] == 123456789
    
    def test_input_anomaly_detection(self):
        """Test input anomaly detection."""
        monitor = SecurityMonitor()
        
        with patch.object(monitor.audit_logger, 'log_security_violation') as mock_log:
            # Test with very long input
            long_input = "A" * 15000
            monitor.detect_input_anomalies(123456789, long_input, "question")
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args[1]
            assert call_args['violation_type'] == "input_anomaly"
            assert "excessive_length" in call_args['details']['anomalies']
    
    def test_entropy_calculation(self):
        """Test entropy calculation for detecting encoded data."""
        monitor = SecurityMonitor()
        
        # Low entropy text
        low_entropy = "aaaaaaaaaa"
        entropy = monitor._calculate_entropy(low_entropy)
        assert entropy < 2.0
        
        # High entropy text (random-looking)
        high_entropy = "x9K2mP8qL5nR7vW3jF6tY1sA4dG0hE"
        entropy = monitor._calculate_entropy(high_entropy)
        assert entropy > 4.0
    
    def test_repeated_pattern_detection(self):
        """Test detection of repeated patterns."""
        monitor = SecurityMonitor()
        
        # Text with repeated patterns
        repeated_text = "abcdefghij" * 10
        assert monitor._has_repeated_patterns(repeated_text) is True
        
        # Normal text without patterns
        normal_text = "This is a normal sentence without repeated patterns."
        assert monitor._has_repeated_patterns(normal_text) is False
    
    def test_binary_data_detection(self):
        """Test detection of binary data."""
        monitor = SecurityMonitor()
        
        # Normal text
        normal_text = "This is normal text"
        assert monitor._contains_binary_data(normal_text) is False
        
        # Text with many non-printable characters
        binary_text = "Normal text" + "\x00\x01\x02\x03\x04" * 10
        assert monitor._contains_binary_data(binary_text) is True


class TestSecurityMiddleware:
    """Test security middleware functionality."""
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = Mock()
        interaction.user.id = 123456789
        interaction.guild.id = 987654321
        interaction.channel.id = 555666777
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        interaction.followup.send = AsyncMock()
        return interaction
    
    @pytest.fixture
    def security_middleware(self):
        """Create security middleware instance."""
        return SecurityMiddleware()
    
    @pytest.mark.asyncio
    async def test_secure_command_decorator(self, security_middleware, mock_interaction):
        """Test secure command decorator."""
        
        @security_middleware.secure_command(
            audit_event_type=AuditEventType.BET_PLACED,
            security_level=SecurityLevel.HIGH
        )
        async def test_command(self, interaction, amount: str):
            return f"Bet placed: {amount}"
        
        # Mock self object
        mock_self = Mock()
        
        with patch('core.security_middleware.set_correlation_id') as mock_set_corr_id:
            mock_set_corr_id.return_value = "test-correlation-id"
            
            result = await test_command(mock_self, mock_interaction, "100")
            assert result == "Bet placed: 100"
    
    @pytest.mark.asyncio
    async def test_security_error_handling(self, security_middleware, mock_interaction):
        """Test security error handling in middleware."""
        
        @security_middleware.secure_command()
        async def failing_command(self, interaction, malicious_input: str):
            # Simulate security error
            raise SecurityError("Malicious input detected")
        
        mock_self = Mock()
        
        with patch('core.security_middleware.set_correlation_id'):
            await failing_command(mock_self, mock_interaction, "'; DROP TABLE users; --")
            
            # Should send security error message
            mock_interaction.response.send_message.assert_called_once()
            call_args = mock_interaction.response.send_message.call_args[0][0]
            assert "Security Error" in call_args
    
    @pytest.mark.asyncio
    async def test_input_sanitization_in_middleware(self, security_middleware, mock_interaction):
        """Test input sanitization in middleware."""
        
        @security_middleware.secure_command(sanitize_inputs=True)
        async def test_command(self, interaction, user_input: str):
            return user_input
        
        mock_self = Mock()
        
        with patch('core.security_middleware.set_correlation_id'):
            result = await test_command(mock_self, mock_interaction, "<script>alert('xss')</script>Hello")
            
            # Input should be sanitized
            assert "<script>" not in result
            assert "Hello" in result


class TestCombinedSecurityMiddleware:
    """Test combined security and validation middleware."""
    
    @pytest.fixture
    def combined_middleware(self):
        """Create combined middleware instance."""
        return CombinedSecurityMiddleware()
    
    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = Mock()
        interaction.user.id = 123456789
        interaction.guild.id = 987654321
        interaction.user.guild_permissions.administrator = False
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        return interaction
    
    @pytest.mark.asyncio
    async def test_combined_middleware_decorator(self, combined_middleware, mock_interaction):
        """Test combined middleware decorator."""
        
        @combined_middleware.secure_and_validate(
            audit_event_type=AuditEventType.PREDICTION_CREATED,
            security_level=SecurityLevel.HIGH,
            rate_limit_config={'limit': 5, 'window': 60}
        )
        async def test_command(self, interaction, question: str):
            return f"Prediction created: {question}"
        
        mock_self = Mock()
        mock_self.rate_limiter = Mock()
        mock_self.rate_limiter.check_rate_limit = AsyncMock(return_value=True)
        
        with patch('core.security_middleware.set_correlation_id'):
            result = await test_command(mock_self, mock_interaction, "Will it rain?")
            assert result == "Prediction created: Will it rain?"


if __name__ == "__main__":
    pytest.main([__file__])