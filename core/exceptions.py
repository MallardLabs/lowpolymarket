"""
Core exceptions for the prediction market bot system.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class ErrorSeverity(Enum):
    """Error severity levels for categorization and handling."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PredictionMarketError(Exception):
    """
    Base exception for all prediction market operations.
    
    Provides structured error handling with unique IDs, error codes,
    user-friendly messages, and detailed context for debugging.
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM
    ):
        super().__init__(message)
        self.error_id = self._generate_error_id()
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.user_message = user_message or self._get_default_user_message()
        self.severity = severity
        self.timestamp = datetime.utcnow()
    
    def _generate_error_id(self) -> str:
        """Generate a unique error ID for tracking."""
        return str(uuid.uuid4())[:8].upper()
    
    def _get_default_user_message(self) -> str:
        """Get default user-friendly message for Discord interactions."""
        return "An error occurred while processing your request."
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging and serialization."""
        return {
            "error_id": self.error_id,
            "error_code": self.error_code,
            "message": str(self),
            "user_message": self.user_message,
            "details": self.details,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "type": self.__class__.__name__
        }


# Validation Errors
class ValidationError(PredictionMarketError):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Any = None, **kwargs):
        details = kwargs.get('details', {})
        if field:
            details['field'] = field
        if value is not None:
            details['invalid_value'] = str(value)
        
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=details,
            user_message=f"❌ {message}",
            severity=ErrorSeverity.LOW,
            **{k: v for k, v in kwargs.items() if k != 'details'}
        )


class InsufficientBalanceError(PredictionMarketError):
    """Raised when user doesn't have enough points for an operation."""
    
    def __init__(self, required: int, available: int, user_id: int, **kwargs):
        message = f"Insufficient balance: required {required}, available {available}"
        details = {
            "required_amount": required,
            "available_amount": available,
            "user_id": user_id,
            "deficit": required - available
        }
        
        super().__init__(
            message=message,
            error_code="INSUFFICIENT_BALANCE",
            details=details,
            user_message=f"💰 You need {required:,} points but only have {available:,} available!",
            severity=ErrorSeverity.LOW,
            **kwargs
        )


class PredictionNotFoundError(PredictionMarketError):
    """Raised when a prediction cannot be found."""
    
    def __init__(self, prediction_id: str, **kwargs):
        message = f"Prediction not found: {prediction_id}"
        details = {"prediction_id": prediction_id}
        
        super().__init__(
            message=message,
            error_code="PREDICTION_NOT_FOUND",
            details=details,
            user_message="🔍 That prediction doesn't exist or has been removed!",
            severity=ErrorSeverity.LOW,
            **kwargs
        )


class PredictionClosedError(PredictionMarketError):
    """Raised when trying to interact with a closed prediction."""
    
    def __init__(self, prediction_id: str, end_time: Optional[datetime] = None, **kwargs):
        message = f"Prediction is closed: {prediction_id}"
        details = {"prediction_id": prediction_id}
        if end_time:
            details["end_time"] = end_time.isoformat()
        
        super().__init__(
            message=message,
            error_code="PREDICTION_CLOSED",
            details=details,
            user_message="🔒 This prediction is no longer accepting bets!",
            severity=ErrorSeverity.LOW,
            **kwargs
        )


class PredictionAlreadyResolvedError(PredictionMarketError):
    """Raised when trying to resolve an already resolved prediction."""
    
    def __init__(self, prediction_id: str, resolved_option: str, **kwargs):
        message = f"Prediction already resolved: {prediction_id} -> {resolved_option}"
        details = {
            "prediction_id": prediction_id,
            "resolved_option": resolved_option
        }
        
        super().__init__(
            message=message,
            error_code="PREDICTION_ALREADY_RESOLVED",
            details=details,
            user_message="✅ This prediction has already been resolved!",
            severity=ErrorSeverity.LOW,
            **kwargs
        )


class InvalidOptionError(PredictionMarketError):
    """Raised when an invalid option is selected for a prediction."""
    
    def __init__(self, option: str, valid_options: list, prediction_id: str, **kwargs):
        message = f"Invalid option '{option}' for prediction {prediction_id}"
        details = {
            "invalid_option": option,
            "valid_options": valid_options,
            "prediction_id": prediction_id
        }
        
        super().__init__(
            message=message,
            error_code="INVALID_OPTION",
            details=details,
            user_message=f"❌ '{option}' is not a valid option. Choose from: {', '.join(valid_options)}",
            severity=ErrorSeverity.LOW,
            **kwargs
        )


# Database Errors
class DatabaseError(PredictionMarketError):
    """Raised when database operations fail."""
    
    def __init__(self, message: str, operation: Optional[str] = None, **kwargs):
        details = kwargs.get('details', {})
        if operation:
            details['operation'] = operation
        
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            details=details,
            user_message="🔧 A database error occurred. Please try again later.",
            severity=ErrorSeverity.HIGH,
            **{k: v for k, v in kwargs.items() if k != 'details'}
        )


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""
    
    def __init__(self, **kwargs):
        # Call PredictionMarketError directly to avoid parameter conflicts
        PredictionMarketError.__init__(
            self,
            message="Failed to connect to database",
            error_code="DATABASE_CONNECTION_ERROR",
            user_message="🔧 Unable to connect to database. Please try again later.",
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )


class DatabaseTimeoutError(DatabaseError):
    """Raised when database operations timeout."""
    
    def __init__(self, operation: str, timeout_seconds: float, **kwargs):
        message = f"Database operation '{operation}' timed out after {timeout_seconds}s"
        details = {
            "operation": operation,
            "timeout_seconds": timeout_seconds
        }
        
        # Call PredictionMarketError directly to avoid parameter conflicts
        PredictionMarketError.__init__(
            self,
            message=message,
            error_code="DATABASE_TIMEOUT",
            details=details,
            user_message="⏱️ The operation took too long. Please try again.",
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


# External API Errors
class ExternalAPIError(PredictionMarketError):
    """Raised when external API calls fail."""
    
    def __init__(self, service: str, status_code: Optional[int] = None, **kwargs):
        message = f"External API error: {service}"
        if status_code:
            message += f" (HTTP {status_code})"
        
        # Extract details from kwargs if provided, otherwise create new
        details = kwargs.pop('details', {})
        details["service"] = service
        if status_code:
            details["status_code"] = status_code
        
        super().__init__(
            message=message,
            error_code="EXTERNAL_API_ERROR",
            details=details,
            user_message="🌐 External service is temporarily unavailable. Please try again later.",
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )


# Rate Limiting Errors
class RateLimitExceededError(PredictionMarketError):
    """Raised when rate limits are exceeded."""
    
    def __init__(self, message: str, rate_limit_info=None, **kwargs):
        # Extract details from kwargs if provided, otherwise create new
        details = kwargs.pop('details', {})
        
        if rate_limit_info:
            details.update({
                "limit": rate_limit_info.limit,
                "remaining": rate_limit_info.remaining,
                "reset_time": rate_limit_info.reset_time,
                "window_seconds": rate_limit_info.window_seconds,
                "seconds_until_reset": rate_limit_info.seconds_until_reset
            })
            user_msg = f"🚦 Slow down! You can only make {rate_limit_info.limit} requests every {rate_limit_info.window_seconds} seconds."
        else:
            user_msg = "🚦 Rate limit exceeded. Please slow down."
        
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            details=details,
            user_message=user_msg,
            severity=ErrorSeverity.LOW,
            **kwargs
        )
        
        self.rate_limit_info = rate_limit_info


# Configuration Errors
class ConfigurationError(PredictionMarketError):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, setting: str, reason: str, **kwargs):
        message = f"Configuration error for '{setting}': {reason}"
        details = {
            "setting": setting,
            "reason": reason
        }
        
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            details=details,
            user_message="⚙️ System configuration error. Please contact an administrator.",
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )


# Business Logic Errors
class InsufficientLiquidityError(PredictionMarketError):
    """Raised when there's insufficient liquidity for a bet."""
    
    def __init__(self, prediction_id: str, requested_amount: int, available_liquidity: int, **kwargs):
        message = f"Insufficient liquidity in prediction {prediction_id}"
        details = {
            "prediction_id": prediction_id,
            "requested_amount": requested_amount,
            "available_liquidity": available_liquidity
        }
        
        super().__init__(
            message=message,
            error_code="INSUFFICIENT_LIQUIDITY",
            details=details,
            user_message="💧 Not enough liquidity available for this bet size.",
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )


class BetTooSmallError(PredictionMarketError):
    """Raised when bet amount is below minimum threshold."""
    
    def __init__(self, amount: int, minimum: int, **kwargs):
        message = f"Bet amount {amount} is below minimum {minimum}"
        details = {
            "amount": amount,
            "minimum": minimum
        }
        
        super().__init__(
            message=message,
            error_code="BET_TOO_SMALL",
            details=details,
            user_message=f"💰 Minimum bet amount is {minimum:,} points.",
            severity=ErrorSeverity.LOW,
            **kwargs
        )


class BetTooLargeError(PredictionMarketError):
    """Raised when bet amount exceeds maximum threshold."""
    
    def __init__(self, amount: int, maximum: int, **kwargs):
        message = f"Bet amount {amount} exceeds maximum {maximum}"
        details = {
            "amount": amount,
            "maximum": maximum
        }
        
        super().__init__(
            message=message,
            error_code="BET_TOO_LARGE",
            details=details,
            user_message=f"💰 Maximum bet amount is {maximum:,} points.",
            severity=ErrorSeverity.LOW,
            **kwargs
        )


# Permission Errors
class InsufficientPermissionsError(PredictionMarketError):
    """Raised when user lacks required permissions."""
    
    def __init__(self, user_id: int, required_permission: str, **kwargs):
        message = f"User {user_id} lacks required permission: {required_permission}"
        details = {
            "user_id": user_id,
            "required_permission": required_permission
        }
        
        super().__init__(
            message=message,
            error_code="INSUFFICIENT_PERMISSIONS",
            details=details,
            user_message="🚫 You don't have permission to perform this action.",
            severity=ErrorSeverity.LOW,
            **kwargs
        )


# Security Errors
class SecurityError(PredictionMarketError):
    """Raised when security violations or threats are detected."""
    
    def __init__(self, message: str, violation_type: Optional[str] = None, **kwargs):
        details = kwargs.get('details', {})
        if violation_type:
            details['violation_type'] = violation_type
        
        super().__init__(
            message=message,
            error_code="SECURITY_ERROR",
            details=details,
            user_message="🔒 Security violation detected. Your request has been blocked.",
            severity=ErrorSeverity.HIGH,
            **{k: v for k, v in kwargs.items() if k != 'details'}
        )


# Legacy DI Container Errors (keeping for backward compatibility)
class DIContainerError(PredictionMarketError):
    """Base exception for dependency injection container errors."""
    
    def __init__(self, message: str, service_name: Optional[str] = None, **kwargs):
        details = kwargs.get('details', {})
        if service_name:
            details['service_name'] = service_name
        
        super().__init__(
            message=message,
            error_code="DI_CONTAINER_ERROR",
            details=details,
            user_message="⚙️ System initialization error. Please contact an administrator.",
            severity=ErrorSeverity.CRITICAL,
            **{k: v for k, v in kwargs.items() if k != 'details'}
        )
        self.service_name = service_name


class ServiceNotFoundError(DIContainerError):
    """Raised when a requested service is not registered in the container."""
    
    def __init__(self, service_name: str, **kwargs):
        # Call PredictionMarketError directly to avoid parameter conflicts
        PredictionMarketError.__init__(
            self,
            message=f"Service '{service_name}' is not registered",
            error_code="SERVICE_NOT_FOUND",
            details={"service_name": service_name},
            user_message="⚙️ System initialization error. Please contact an administrator.",
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )
        self.service_name = service_name


class ServiceRegistrationError(DIContainerError):
    """Raised when there's an error registering a service."""
    
    def __init__(self, service_name: str, reason: str, **kwargs):
        # Call PredictionMarketError directly to avoid parameter conflicts
        PredictionMarketError.__init__(
            self,
            message=f"Failed to register service '{service_name}': {reason}",
            error_code="SERVICE_REGISTRATION_ERROR",
            details={"reason": reason, "service_name": service_name},
            user_message="⚙️ System initialization error. Please contact an administrator.",
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )
        self.service_name = service_name


class CircularDependencyError(DIContainerError):
    """Raised when a circular dependency is detected during service resolution."""
    
    def __init__(self, dependency_chain: list, **kwargs):
        chain_str = " -> ".join(dependency_chain)
        
        # Call PredictionMarketError directly to avoid parameter conflicts
        PredictionMarketError.__init__(
            self,
            message=f"Circular dependency detected: {chain_str}",
            error_code="CIRCULAR_DEPENDENCY",
            details={"dependency_chain": dependency_chain},
            user_message="⚙️ System initialization error. Please contact an administrator.",
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )
        self.dependency_chain = dependency_chain