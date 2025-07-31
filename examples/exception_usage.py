"""
Example usage of the custom exception hierarchy.

This demonstrates how to use the various exception types in the prediction market bot.
"""

from core.exceptions import (
    ValidationError,
    InsufficientBalanceError,
    PredictionNotFoundError,
    PredictionClosedError,
    DatabaseError,
    ExternalAPIError,
    RateLimitExceededError,
    ErrorSeverity
)


def demonstrate_validation_error():
    """Demonstrate ValidationError usage."""
    try:
        # Simulate invalid bet amount
        amount = -100
        if amount <= 0:
            raise ValidationError(
                "Bet amount must be positive",
                field="amount",
                value=amount
            )
    except ValidationError as e:
        print(f"Validation Error: {e}")
        print(f"Error ID: {e.error_id}")
        print(f"User Message: {e.user_message}")
        print(f"Details: {e.details}")
        print()


def demonstrate_insufficient_balance_error():
    """Demonstrate InsufficientBalanceError usage."""
    try:
        # Simulate insufficient balance
        required = 1000
        available = 250
        user_id = 12345
        
        if available < required:
            raise InsufficientBalanceError(
                required=required,
                available=available,
                user_id=user_id
            )
    except InsufficientBalanceError as e:
        print(f"Insufficient Balance Error: {e}")
        print(f"Error ID: {e.error_id}")
        print(f"User Message: {e.user_message}")
        print(f"Deficit: {e.details['deficit']} points")
        print()


def demonstrate_prediction_not_found_error():
    """Demonstrate PredictionNotFoundError usage."""
    try:
        # Simulate prediction not found
        prediction_id = "pred-nonexistent"
        raise PredictionNotFoundError(prediction_id)
    except PredictionNotFoundError as e:
        print(f"Prediction Not Found Error: {e}")
        print(f"Error ID: {e.error_id}")
        print(f"User Message: {e.user_message}")
        print(f"Prediction ID: {e.details['prediction_id']}")
        print()


def demonstrate_database_error():
    """Demonstrate DatabaseError usage."""
    try:
        # Simulate database connection failure
        raise DatabaseError(
            "Connection to database failed",
            operation="connect",
            details={"host": "localhost", "port": 5432}
        )
    except DatabaseError as e:
        print(f"Database Error: {e}")
        print(f"Error ID: {e.error_id}")
        print(f"User Message: {e.user_message}")
        print(f"Severity: {e.severity.value}")
        print(f"Operation: {e.details['operation']}")
        print()


def demonstrate_rate_limit_error():
    """Demonstrate RateLimitExceededError usage."""
    try:
        # Simulate rate limit exceeded
        raise RateLimitExceededError(
            user_id=67890,
            limit=10,
            window_seconds=60
        )
    except RateLimitExceededError as e:
        print(f"Rate Limit Error: {e}")
        print(f"Error ID: {e.error_id}")
        print(f"User Message: {e.user_message}")
        print(f"Limit: {e.details['limit']} requests per {e.details['window_seconds']}s")
        print()


def demonstrate_error_serialization():
    """Demonstrate error serialization to dictionary."""
    try:
        raise ValidationError(
            "Invalid prediction question",
            field="question",
            value="",
            details={"min_length": 1, "max_length": 500}
        )
    except ValidationError as e:
        print("Error Serialization:")
        error_dict = e.to_dict()
        for key, value in error_dict.items():
            print(f"  {key}: {value}")
        print()


def demonstrate_error_handling_pattern():
    """Demonstrate a typical error handling pattern."""
    def place_bet(user_id: int, prediction_id: str, amount: int, user_balance: int):
        """Simulate placing a bet with various validation checks."""
        
        # Validate amount
        if amount <= 0:
            raise ValidationError("Bet amount must be positive", field="amount", value=amount)
        
        if amount > 1_000_000:
            raise ValidationError("Bet amount too large", field="amount", value=amount)
        
        # Check balance
        if user_balance < amount:
            raise InsufficientBalanceError(
                required=amount,
                available=user_balance,
                user_id=user_id
            )
        
        # Simulate prediction lookup
        if prediction_id == "nonexistent":
            raise PredictionNotFoundError(prediction_id)
        
        # Simulate successful bet placement
        return True
    
    # Test various scenarios
    test_cases = [
        (12345, "pred-123", -50, 1000),      # Negative amount
        (12345, "pred-123", 2000000, 1000),  # Amount too large
        (12345, "pred-123", 500, 100),       # Insufficient balance
        (12345, "nonexistent", 100, 1000),   # Prediction not found
        (12345, "pred-123", 100, 1000),      # Success case
    ]
    
    for user_id, pred_id, amount, balance in test_cases:
        try:
            result = place_bet(user_id, pred_id, amount, balance)
            print(f"✅ Bet placed successfully: user={user_id}, amount={amount}")
        except ValidationError as e:
            print(f"❌ Validation failed: {e.user_message} (ID: {e.error_id})")
        except InsufficientBalanceError as e:
            print(f"💰 {e.user_message} (ID: {e.error_id})")
        except PredictionNotFoundError as e:
            print(f"🔍 {e.user_message} (ID: {e.error_id})")
        except Exception as e:
            print(f"❓ Unexpected error: {e}")
    print()


if __name__ == "__main__":
    print("=== Custom Exception Hierarchy Demo ===\n")
    
    demonstrate_validation_error()
    demonstrate_insufficient_balance_error()
    demonstrate_prediction_not_found_error()
    demonstrate_database_error()
    demonstrate_rate_limit_error()
    demonstrate_error_serialization()
    demonstrate_error_handling_pattern()
    
    print("=== Demo Complete ===")