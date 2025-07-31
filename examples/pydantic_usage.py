"""
Example usage of Pydantic data models for validation and sanitization.

This script demonstrates how to use the Pydantic models for request validation,
data sanitization, and error handling in the Discord bot.
"""

from datetime import datetime
from pydantic import ValidationError

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.schemas import (
    CreatePredictionRequest,
    PlaceBetRequest,
    ResolvePredictionRequest,
    VoteRequest,
    PredictionCategory,
    PredictionStatus,
    ModelFactory,
    SanitizedInput,
    ErrorResponse
)


def demonstrate_prediction_creation():
    """Demonstrate prediction creation with validation"""
    print("=== Prediction Creation Examples ===")
    
    # Valid prediction request
    try:
        valid_request = CreatePredictionRequest(
            question="Will Bitcoin reach $100,000 by end of 2024?",
            options=["Yes", "No"],
            duration_minutes=2880,  # 2 days
            category=PredictionCategory.CRYPTO,
            initial_liquidity=50000
        )
        print(f"✅ Valid prediction created: {valid_request.question}")
        print(f"   Options: {valid_request.options}")
        print(f"   Duration: {valid_request.duration_minutes} minutes")
        print(f"   Category: {valid_request.category}")
        print()
    except ValidationError as e:
        print(f"❌ Validation error: {e}")
    
    # Invalid prediction request - question too short
    try:
        invalid_request = CreatePredictionRequest(
            question="Rain?",  # Too short
            options=["Yes", "No"],
            duration_minutes=1440
        )
        print("This should not print")
    except ValidationError as e:
        print(f"❌ Expected validation error for short question: {e.errors()[0]['msg']}")
        print()
    
    # Invalid prediction request - inappropriate content
    try:
        spam_request = CreatePredictionRequest(
            question="Is this a spam question about scams?",
            options=["Yes", "No"],
            duration_minutes=1440
        )
        print("This should not print")
    except ValidationError as e:
        print(f"❌ Expected validation error for inappropriate content: {e.errors()[0]['msg']}")
        print()
    
    # Automatic question mark addition
    try:
        auto_question = CreatePredictionRequest(
            question="Will it rain tomorrow",  # No question mark
            options=["Yes", "No"],
            duration_minutes=1440
        )
        print(f"✅ Question mark automatically added: {auto_question.question}")
        print()
    except ValidationError as e:
        print(f"❌ Unexpected error: {e}")


def demonstrate_bet_placement():
    """Demonstrate bet placement with validation"""
    print("=== Bet Placement Examples ===")
    
    # Valid bet request
    try:
        valid_bet = PlaceBetRequest(
            prediction_id="crypto-btc-100k-2024",
            option="Yes",
            amount=1000
        )
        print(f"✅ Valid bet placed: {valid_bet.amount} points on '{valid_bet.option}'")
        print(f"   Prediction ID: {valid_bet.prediction_id}")
        print()
    except ValidationError as e:
        print(f"❌ Validation error: {e}")
    
    # Invalid bet request - amount too large
    try:
        invalid_bet = PlaceBetRequest(
            prediction_id="test-prediction",
            option="Yes",
            amount=2_000_000  # Too large
        )
        print("This should not print")
    except ValidationError as e:
        print(f"❌ Expected validation error for large amount: {e.errors()[0]['msg']}")
        print()
    
    # Invalid bet request - invalid prediction ID
    try:
        invalid_id_bet = PlaceBetRequest(
            prediction_id="invalid@id#format",  # Invalid characters
            option="Yes",
            amount=100
        )
        print("This should not print")
    except ValidationError as e:
        print(f"❌ Expected validation error for invalid ID: {e.errors()[0]['msg']}")
        print()


def demonstrate_data_sanitization():
    """Demonstrate data sanitization utilities"""
    print("=== Data Sanitization Examples ===")
    
    # Text sanitization
    dirty_texts = [
        "Hello <script>alert('xss')</script> world",
        "Normal text with    excessive    whitespace",
        "Text with\x00control\x01characters",
        "javascript:alert('hack')",
        "Hello <b>bold</b> text"
    ]
    
    for dirty_text in dirty_texts:
        clean_text = SanitizedInput.sanitize_text(dirty_text)
        print(f"Original: {repr(dirty_text)}")
        print(f"Cleaned:  {repr(clean_text)}")
        print()
    
    # Discord ID validation
    test_ids = [
        123456789012345678,  # Valid
        "123456789012345678",  # Valid string
        123,  # Too short
        "abc",  # Invalid format
        -1,  # Negative
    ]
    
    for test_id in test_ids:
        try:
            validated_id = SanitizedInput.validate_discord_id(test_id)
            print(f"✅ Valid Discord ID: {validated_id}")
        except ValueError as e:
            print(f"❌ Invalid Discord ID {test_id}: {e}")
    print()


def demonstrate_model_factories():
    """Demonstrate model factories for testing"""
    print("=== Model Factory Examples ===")
    
    # Create test prediction request
    test_prediction = ModelFactory.create_prediction_request(
        question="Will the weather be sunny tomorrow?",
        options=["Sunny", "Cloudy", "Rainy"],
        duration_minutes=720,
        category=PredictionCategory.WEATHER
    )
    print(f"✅ Test prediction created: {test_prediction.question}")
    print(f"   Options: {test_prediction.options}")
    print()
    
    # Create test bet request
    test_bet = ModelFactory.create_bet_request(
        prediction_id="weather-sunny-tomorrow",
        option="Sunny",
        amount=500
    )
    print(f"✅ Test bet created: {test_bet.amount} points on '{test_bet.option}'")
    print()
    
    # Create test prediction response
    test_response = ModelFactory.create_prediction_response(
        id="weather-prediction-123",
        question="Will it be sunny tomorrow?",
        options=["Yes", "No"],
        status=PredictionStatus.ACTIVE
    )
    print(f"✅ Test response created: {test_response.id}")
    print(f"   Status: {test_response.status}")
    print(f"   Created: {test_response.created_at}")
    print()
    
    # Create test market prices
    test_prices = ModelFactory.create_market_prices_response(
        prediction_id="weather-prediction-123",
        options=["Sunny", "Cloudy", "Rainy"]
    )
    print(f"✅ Test market prices created for {len(test_prices.prices)} options:")
    for option, price_info in test_prices.prices.items():
        print(f"   {option}: {price_info.price_per_share:.2f} per share, {price_info.probability:.1f}% probability")
    print()


def demonstrate_error_handling():
    """Demonstrate error handling with validation"""
    print("=== Error Handling Examples ===")
    
    # Multiple validation errors
    try:
        invalid_request = CreatePredictionRequest(
            question="Bad?",  # Too short
            options=["Only one option"],  # Too few options
            duration_minutes=1,  # Too short duration
            initial_liquidity=100  # Too low liquidity
        )
        print("This should not print")
    except ValidationError as e:
        print(f"❌ Multiple validation errors found:")
        for error in e.errors():
            field = error['loc'][0] if error['loc'] else 'unknown'
            message = error['msg']
            print(f"   - {field}: {message}")
        print()
    
    # Create error response
    error_response = ModelFactory.create_error_response(
        error_code="VALIDATION_FAILED",
        message="Request validation failed",
        error_id="err-12345"
    )
    print(f"✅ Error response created:")
    print(f"   Code: {error_response.error_code}")
    print(f"   Message: {error_response.message}")
    print(f"   ID: {error_response.error_id}")
    print(f"   Timestamp: {error_response.timestamp}")
    print()


def main():
    """Run all demonstration examples"""
    print("🚀 Pydantic Data Models Usage Examples")
    print("=" * 50)
    print()
    
    demonstrate_prediction_creation()
    demonstrate_bet_placement()
    demonstrate_data_sanitization()
    demonstrate_model_factories()
    demonstrate_error_handling()
    
    print("✅ All examples completed successfully!")


if __name__ == "__main__":
    main()