"""
Unit tests for the custom exception hierarchy.
"""

import pytest
from datetime import datetime
from core.exceptions import (
    ErrorSeverity,
    PredictionMarketError,
    ValidationError,
    InsufficientBalanceError,
    PredictionNotFoundError,
    PredictionClosedError,
    PredictionAlreadyResolvedError,
    InvalidOptionError,
    DatabaseError,
    DatabaseConnectionError,
    DatabaseTimeoutError,
    ExternalAPIError,
    RateLimitExceededError,
    ConfigurationError,
    InsufficientLiquidityError,
    BetTooSmallError,
    BetTooLargeError,
    InsufficientPermissionsError,
    DIContainerError,
    ServiceNotFoundError,
    ServiceRegistrationError,
    CircularDependencyError
)


class TestPredictionMarketError:
    """Test the base PredictionMarketError class."""
    
    def test_basic_error_creation(self):
        """Test basic error creation with minimal parameters."""
        error = PredictionMarketError("Test error message")
        
        assert str(error) == "Test error message"
        assert error.error_code == "PredictionMarketError"
        assert error.user_message == "An error occurred while processing your request."
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.details == {}
        assert len(error.error_id) == 8
        assert isinstance(error.timestamp, datetime)
    
    def test_error_with_all_parameters(self):
        """Test error creation with all parameters."""
        details = {"key": "value", "number": 42}
        error = PredictionMarketError(
            message="Custom error",
            error_code="CUSTOM_ERROR",
            details=details,
            user_message="Custom user message",
            severity=ErrorSeverity.HIGH
        )
        
        assert str(error) == "Custom error"
        assert error.error_code == "CUSTOM_ERROR"
        assert error.user_message == "Custom user message"
        assert error.severity == ErrorSeverity.HIGH
        assert error.details == details
    
    def test_error_id_uniqueness(self):
        """Test that error IDs are unique."""
        error1 = PredictionMarketError("Error 1")
        error2 = PredictionMarketError("Error 2")
        
        assert error1.error_id != error2.error_id
        assert len(error1.error_id) == 8
        assert len(error2.error_id) == 8
    
    def test_to_dict_method(self):
        """Test the to_dict method for serialization."""
        details = {"test": "data"}
        error = PredictionMarketError(
            message="Test message",
            error_code="TEST_ERROR",
            details=details,
            user_message="User message",
            severity=ErrorSeverity.LOW
        )
        
        result = error.to_dict()
        
        assert result["error_id"] == error.error_id
        assert result["error_code"] == "TEST_ERROR"
        assert result["message"] == "Test message"
        assert result["user_message"] == "User message"
        assert result["details"] == details
        assert result["severity"] == "low"
        assert result["type"] == "PredictionMarketError"
        assert "timestamp" in result


class TestValidationError:
    """Test ValidationError class."""
    
    def test_basic_validation_error(self):
        """Test basic validation error."""
        error = ValidationError("Invalid input")
        
        assert str(error) == "Invalid input"
        assert error.error_code == "VALIDATION_ERROR"
        assert error.user_message == "❌ Invalid input"
        assert error.severity == ErrorSeverity.LOW
    
    def test_validation_error_with_field(self):
        """Test validation error with field information."""
        error = ValidationError("Invalid value", field="amount", value="-100")
        
        assert error.details["field"] == "amount"
        assert error.details["invalid_value"] == "-100"
    
    def test_validation_error_with_none_value(self):
        """Test validation error with None value."""
        error = ValidationError("Missing value", field="required_field", value=None)
        
        assert error.details["field"] == "required_field"
        assert "invalid_value" not in error.details


class TestInsufficientBalanceError:
    """Test InsufficientBalanceError class."""
    
    def test_insufficient_balance_error(self):
        """Test insufficient balance error creation."""
        error = InsufficientBalanceError(required=1000, available=500, user_id=12345)
        
        assert "required 1000, available 500" in str(error)
        assert error.error_code == "INSUFFICIENT_BALANCE"
        assert "1,000 points but only have 500" in error.user_message
        assert error.details["required_amount"] == 1000
        assert error.details["available_amount"] == 500
        assert error.details["user_id"] == 12345
        assert error.details["deficit"] == 500
        assert error.severity == ErrorSeverity.LOW


class TestPredictionNotFoundError:
    """Test PredictionNotFoundError class."""
    
    def test_prediction_not_found_error(self):
        """Test prediction not found error."""
        error = PredictionNotFoundError("pred-123")
        
        assert "pred-123" in str(error)
        assert error.error_code == "PREDICTION_NOT_FOUND"
        assert "doesn't exist" in error.user_message
        assert error.details["prediction_id"] == "pred-123"
        assert error.severity == ErrorSeverity.LOW


class TestPredictionClosedError:
    """Test PredictionClosedError class."""
    
    def test_prediction_closed_error(self):
        """Test prediction closed error."""
        end_time = datetime(2024, 1, 1, 12, 0, 0)
        error = PredictionClosedError("pred-456", end_time=end_time)
        
        assert "pred-456" in str(error)
        assert error.error_code == "PREDICTION_CLOSED"
        assert "no longer accepting bets" in error.user_message
        assert error.details["prediction_id"] == "pred-456"
        assert error.details["end_time"] == end_time.isoformat()
    
    def test_prediction_closed_error_without_end_time(self):
        """Test prediction closed error without end time."""
        error = PredictionClosedError("pred-789")
        
        assert error.details["prediction_id"] == "pred-789"
        assert "end_time" not in error.details


class TestInvalidOptionError:
    """Test InvalidOptionError class."""
    
    def test_invalid_option_error(self):
        """Test invalid option error."""
        valid_options = ["Yes", "No", "Maybe"]
        error = InvalidOptionError("Invalid", valid_options, "pred-123")
        
        assert "Invalid option 'Invalid'" in str(error)
        assert error.error_code == "INVALID_OPTION"
        assert "Yes, No, Maybe" in error.user_message
        assert error.details["invalid_option"] == "Invalid"
        assert error.details["valid_options"] == valid_options
        assert error.details["prediction_id"] == "pred-123"


class TestDatabaseErrors:
    """Test database-related errors."""
    
    def test_database_error(self):
        """Test basic database error."""
        error = DatabaseError("Connection failed", operation="select")
        
        assert str(error) == "Connection failed"
        assert error.error_code == "DATABASE_ERROR"
        assert "database error occurred" in error.user_message
        assert error.details["operation"] == "select"
        assert error.severity == ErrorSeverity.HIGH
    
    def test_database_connection_error(self):
        """Test database connection error."""
        error = DatabaseConnectionError()
        
        assert "Failed to connect to database" in str(error)
        assert error.error_code == "DATABASE_CONNECTION_ERROR"
        assert "Unable to connect" in error.user_message
        assert error.severity == ErrorSeverity.CRITICAL
    
    def test_database_timeout_error(self):
        """Test database timeout error."""
        error = DatabaseTimeoutError("select_predictions", 30.0)
        
        assert "timed out after 30.0s" in str(error)
        assert error.error_code == "DATABASE_TIMEOUT"
        assert "took too long" in error.user_message
        assert error.details["operation"] == "select_predictions"
        assert error.details["timeout_seconds"] == 30.0


class TestExternalAPIError:
    """Test ExternalAPIError class."""
    
    def test_external_api_error(self):
        """Test external API error."""
        error = ExternalAPIError("DRIP API", status_code=500)
        
        assert "DRIP API" in str(error)
        assert "HTTP 500" in str(error)
        assert error.error_code == "EXTERNAL_API_ERROR"
        assert "temporarily unavailable" in error.user_message
        assert error.details["service"] == "DRIP API"
        assert error.details["status_code"] == 500
        assert error.severity == ErrorSeverity.MEDIUM
    
    def test_external_api_error_without_status_code(self):
        """Test external API error without status code."""
        error = ExternalAPIError("Test Service")
        
        assert error.details["service"] == "Test Service"
        assert "status_code" not in error.details


class TestRateLimitExceededError:
    """Test RateLimitExceededError class."""
    
    def test_rate_limit_exceeded_error(self):
        """Test rate limit exceeded error."""
        error = RateLimitExceededError(user_id=12345, limit=10, window_seconds=60)
        
        assert "user 12345" in str(error)
        assert "10 requests per 60s" in str(error)
        assert error.error_code == "RATE_LIMIT_EXCEEDED"
        assert "10 requests every 60 seconds" in error.user_message
        assert error.details["user_id"] == 12345
        assert error.details["limit"] == 10
        assert error.details["window_seconds"] == 60


class TestConfigurationError:
    """Test ConfigurationError class."""
    
    def test_configuration_error(self):
        """Test configuration error."""
        error = ConfigurationError("database_url", "Missing required setting")
        
        assert "database_url" in str(error)
        assert "Missing required setting" in str(error)
        assert error.error_code == "CONFIGURATION_ERROR"
        assert "configuration error" in error.user_message
        assert error.details["setting"] == "database_url"
        assert error.details["reason"] == "Missing required setting"
        assert error.severity == ErrorSeverity.CRITICAL


class TestBusinessLogicErrors:
    """Test business logic related errors."""
    
    def test_insufficient_liquidity_error(self):
        """Test insufficient liquidity error."""
        error = InsufficientLiquidityError("pred-123", 1000, 500)
        
        assert "pred-123" in str(error)
        assert error.error_code == "INSUFFICIENT_LIQUIDITY"
        assert "Not enough liquidity" in error.user_message
        assert error.details["prediction_id"] == "pred-123"
        assert error.details["requested_amount"] == 1000
        assert error.details["available_liquidity"] == 500
    
    def test_bet_too_small_error(self):
        """Test bet too small error."""
        error = BetTooSmallError(amount=5, minimum=10)
        
        assert "below minimum 10" in str(error)
        assert error.error_code == "BET_TOO_SMALL"
        assert "Minimum bet amount is 10" in error.user_message
        assert error.details["amount"] == 5
        assert error.details["minimum"] == 10
    
    def test_bet_too_large_error(self):
        """Test bet too large error."""
        error = BetTooLargeError(amount=2000000, maximum=1000000)
        
        assert "exceeds maximum 1000000" in str(error)
        assert error.error_code == "BET_TOO_LARGE"
        assert "Maximum bet amount is 1,000,000" in error.user_message
        assert error.details["amount"] == 2000000
        assert error.details["maximum"] == 1000000


class TestInsufficientPermissionsError:
    """Test InsufficientPermissionsError class."""
    
    def test_insufficient_permissions_error(self):
        """Test insufficient permissions error."""
        error = InsufficientPermissionsError(user_id=12345, required_permission="admin")
        
        assert "User 12345 lacks required permission: admin" in str(error)
        assert error.error_code == "INSUFFICIENT_PERMISSIONS"
        assert "don't have permission" in error.user_message
        assert error.details["user_id"] == 12345
        assert error.details["required_permission"] == "admin"


class TestDIContainerErrors:
    """Test dependency injection container errors."""
    
    def test_service_not_found_error(self):
        """Test service not found error."""
        error = ServiceNotFoundError("TestService")
        
        assert "TestService" in str(error)
        assert "not registered" in str(error)
        assert error.error_code == "SERVICE_NOT_FOUND"
        assert error.service_name == "TestService"
        assert error.severity == ErrorSeverity.CRITICAL
    
    def test_service_registration_error(self):
        """Test service registration error."""
        error = ServiceRegistrationError("TestService", "Invalid configuration")
        
        assert "TestService" in str(error)
        assert "Invalid configuration" in str(error)
        assert error.error_code == "SERVICE_REGISTRATION_ERROR"
        assert error.service_name == "TestService"
        assert error.details["reason"] == "Invalid configuration"
    
    def test_circular_dependency_error(self):
        """Test circular dependency error."""
        chain = ["ServiceA", "ServiceB", "ServiceC", "ServiceA"]
        error = CircularDependencyError(chain)
        
        assert "ServiceA -> ServiceB -> ServiceC -> ServiceA" in str(error)
        assert error.error_code == "CIRCULAR_DEPENDENCY"
        assert error.dependency_chain == chain
        assert error.details["dependency_chain"] == chain


class TestErrorInheritance:
    """Test that all errors inherit from PredictionMarketError."""
    
    def test_all_errors_inherit_from_base(self):
        """Test that all custom errors inherit from PredictionMarketError."""
        error_classes = [
            ValidationError,
            InsufficientBalanceError,
            PredictionNotFoundError,
            PredictionClosedError,
            PredictionAlreadyResolvedError,
            InvalidOptionError,
            DatabaseError,
            DatabaseConnectionError,
            DatabaseTimeoutError,
            ExternalAPIError,
            RateLimitExceededError,
            ConfigurationError,
            InsufficientLiquidityError,
            BetTooSmallError,
            BetTooLargeError,
            InsufficientPermissionsError,
            DIContainerError,
            ServiceNotFoundError,
            ServiceRegistrationError,
            CircularDependencyError
        ]
        
        for error_class in error_classes:
            assert issubclass(error_class, PredictionMarketError)
            assert issubclass(error_class, Exception)
    
    def test_error_severity_enum(self):
        """Test ErrorSeverity enum values."""
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.CRITICAL.value == "critical"


if __name__ == "__main__":
    pytest.main([__file__])