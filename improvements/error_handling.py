"""
Improved Error Handling and Validation
"""

from typing import Optional, Union, Any
from dataclasses import dataclass
from enum import Enum
import logging
import traceback
from functools import wraps

# 1. CUSTOM EXCEPTION HIERARCHY
class PredictionMarketError(Exception):
    """Base exception for prediction market operations"""
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}

class ValidationError(PredictionMarketError):
    """Raised when input validation fails"""
    pass

class InsufficientBalanceError(PredictionMarketError):
    """Raised when user doesn't have enough points"""
    pass

class PredictionNotFoundError(PredictionMarketError):
    """Raised when prediction doesn't exist"""
    pass

class PredictionClosedError(PredictionMarketError):
    """Raised when trying to bet on closed prediction"""
    pass

class DatabaseError(PredictionMarketError):
    """Raised when database operations fail"""
    pass

class ExternalAPIError(PredictionMarketError):
    """Raised when external API calls fail"""
    pass

# 2. VALIDATION FRAMEWORK
class Validator:
    @staticmethod
    def validate_bet_amount(amount: int) -> None:
        if not isinstance(amount, int):
            raise ValidationError("Bet amount must be an integer")
        if amount <= 0:
            raise ValidationError("Bet amount must be positive")
        if amount > 1_000_000:
            raise ValidationError("Bet amount too large (max: 1,000,000)")
    
    @staticmethod
    def validate_user_id(user_id: int) -> None:
        if not isinstance(user_id, int):
            raise ValidationError("User ID must be an integer")
        if user_id <= 0:
            raise ValidationError("User ID must be positive")
    
    @staticmethod
    def validate_prediction_question(question: str) -> None:
        if not isinstance(question, str):
            raise ValidationError("Question must be a string")
        if not question.strip():
            raise ValidationError("Question cannot be empty")
        if len(question) > 500:
            raise ValidationError("Question too long (max: 500 characters)")
    
    @staticmethod
    def validate_options(options: list[str]) -> None:
        if not isinstance(options, list):
            raise ValidationError("Options must be a list")
        if len(options) < 2:
            raise ValidationError("Must have at least 2 options")
        if len(options) > 10:
            raise ValidationError("Too many options (max: 10)")
        
        for option in options:
            if not isinstance(option, str):
                raise ValidationError("All options must be strings")
            if not option.strip():
                raise ValidationError("Options cannot be empty")
            if len(option) > 100:
                raise ValidationError("Option too long (max: 100 characters)")
        
        if len(set(options)) != len(options):
            raise ValidationError("Options must be unique")

# 3. RETRY DECORATOR WITH EXPONENTIAL BACKOFF
def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except (DatabaseError, ExternalAPIError) as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logging.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                except Exception as e:
                    # Don't retry for validation errors or other non-transient errors
                    raise
            
            raise last_exception
        return wrapper
    return decorator

# 4. CIRCUIT BREAKER PATTERN
class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
    
    async def call(self, func, *args, **kwargs):
        if self.state == CircuitBreakerState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise ExternalAPIError("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN

# 5. COMPREHENSIVE ERROR HANDLER
class ErrorHandler:
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    async def handle_discord_interaction_error(self, interaction, error: Exception):
        """Handle errors in Discord interactions with user-friendly messages"""
        error_id = self._log_error(error)
        
        if isinstance(error, ValidationError):
            message = f"❌ {error}"
        elif isinstance(error, InsufficientBalanceError):
            message = "💰 You don't have enough points for this bet!"
        elif isinstance(error, PredictionNotFoundError):
            message = "🔍 Prediction not found!"
        elif isinstance(error, PredictionClosedError):
            message = "🔒 This prediction is no longer accepting bets!"
        elif isinstance(error, DatabaseError):
            message = f"🔧 Database error occurred. Error ID: {error_id}"
        elif isinstance(error, ExternalAPIError):
            message = f"🌐 External service error. Error ID: {error_id}"
        else:
            message = f"❓ An unexpected error occurred. Error ID: {error_id}"
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception as e:
            self.logger.error(f"Failed to send error message: {e}")
    
    def _log_error(self, error: Exception) -> str:
        """Log error with unique ID for tracking"""
        import uuid
        error_id = str(uuid.uuid4())[:8]
        
        self.logger.error(
            f"Error ID: {error_id} | {type(error).__name__}: {error}",
            extra={
                'error_id': error_id,
                'error_type': type(error).__name__,
                'traceback': traceback.format_exc()
            }
        )
        
        return error_id

# 6. IMPROVED DATABASE OPERATIONS WITH ERROR HANDLING
class SafeDatabaseOperations:
    def __init__(self, db_manager, circuit_breaker: CircuitBreaker):
        self.db = db_manager
        self.circuit_breaker = circuit_breaker
    
    @retry_with_backoff(max_retries=3)
    async def safe_place_bet(self, bet_data: dict) -> bool:
        """Place bet with comprehensive error handling"""
        try:
            return await self.circuit_breaker.call(self.db.place_bet, bet_data)
        except asyncpg.PostgresError as e:
            raise DatabaseError(f"Database operation failed: {e}")
        except Exception as e:
            raise DatabaseError(f"Unexpected database error: {e}")
    
    @retry_with_backoff(max_retries=2)
    async def safe_get_prediction(self, prediction_id: str) -> Optional[dict]:
        """Get prediction with error handling"""
        try:
            return await self.circuit_breaker.call(self.db.get_prediction_by_id, prediction_id)
        except asyncpg.PostgresError as e:
            raise DatabaseError(f"Failed to retrieve prediction: {e}")

# 7. VALIDATION DECORATORS
def validate_bet_request(func):
    @wraps(func)
    async def wrapper(self, bet_request: BetRequest, *args, **kwargs):
        Validator.validate_user_id(bet_request.user_id)
        Validator.validate_bet_amount(bet_request.amount)
        if not bet_request.prediction_id:
            raise ValidationError("Prediction ID is required")
        if not bet_request.option:
            raise ValidationError("Option is required")
        
        return await func(self, bet_request, *args, **kwargs)
    return wrapper

def validate_prediction_creation(func):
    @wraps(func)
    async def wrapper(self, question: str, options: list[str], *args, **kwargs):
        Validator.validate_prediction_question(question)
        Validator.validate_options(options)
        
        return await func(self, question, options, *args, **kwargs)
    return wrapper

# Usage Example:
"""
class ImprovedPredictionService:
    def __init__(self, db_manager):
        self.db_ops = SafeDatabaseOperations(db_manager, CircuitBreaker())
        self.error_handler = ErrorHandler(logging.getLogger(__name__))
    
    @validate_bet_request
    async def place_bet(self, bet_request: BetRequest) -> Result[bool, str]:
        try:
            success = await self.db_ops.safe_place_bet(bet_request.__dict__)
            return Result.success(success)
        except PredictionMarketError as e:
            return Result.error(str(e))
"""