"""
Simple demonstration of the validation framework without Discord dependencies.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from typing import List

from core.validation import Validator, validate_input, ValidationResult
from core.exceptions import ValidationError, InsufficientBalanceError


def demonstrate_static_validation():
    """Demonstrate static validation methods"""
    print("=== Static Validation Methods ===")
    
    # Test Discord ID validation
    print("1. Discord ID Validation:")
    valid_id = Validator.validate_discord_id(123456789012345678)
    print(f"   Valid ID: {valid_id.is_valid}, Sanitized: {valid_id.sanitized_data}")
    
    invalid_id = Validator.validate_discord_id("invalid")
    print(f"   Invalid ID: {invalid_id.is_valid}, Errors: {invalid_id.errors}")
    
    # Test question validation
    print("\n2. Question Validation:")
    valid_question = Validator.validate_prediction_question("Will it rain tomorrow")
    print(f"   Valid question: {valid_question.is_valid}, Sanitized: '{valid_question.sanitized_data}'")
    
    invalid_question = Validator.validate_prediction_question("Hi")
    print(f"   Invalid question: {invalid_question.is_valid}, Errors: {invalid_question.errors}")
    
    # Test options validation
    print("\n3. Options Validation:")
    valid_options = Validator.validate_prediction_options(["Yes", "No", "Maybe"])
    print(f"   Valid options: {valid_options.is_valid}, Sanitized: {valid_options.sanitized_data}")
    
    invalid_options = Validator.validate_prediction_options(["Only one"])
    print(f"   Invalid options: {invalid_options.is_valid}, Errors: {invalid_options.errors}")
    
    # Test bet amount validation
    print("\n4. Bet Amount Validation:")
    valid_amount = Validator.validate_bet_amount(1000)
    print(f"   Valid amount: {valid_amount.is_valid}, Sanitized: {valid_amount.sanitized_data}")
    
    invalid_amount = Validator.validate_bet_amount(-100)
    print(f"   Invalid amount: {invalid_amount.is_valid}, Errors: {invalid_amount.errors}")


def demonstrate_input_sanitization():
    """Demonstrate input sanitization"""
    print("\n=== Input Sanitization ===")
    
    dangerous_inputs = [
        "<script>alert('xss')</script>Hello World",
        "'; DROP TABLE users; --",
        "javascript:alert('hack')",
        "Normal text with\x00null bytes",
        "   Lots   of    whitespace   ",
    ]
    
    for i, dangerous_input in enumerate(dangerous_inputs, 1):
        sanitized = Validator.sanitize_text(dangerous_input, max_length=50)
        print(f"{i}. Original: {repr(dangerous_input[:30])}")
        print(f"   Sanitized: {repr(sanitized)}")


class ExampleService:
    """Example service using validation decorators"""
    
    @validate_input(
        user_id=Validator.validate_discord_id,
        amount=lambda x: Validator.validate_bet_amount(x, min_amount=10, max_amount=10000)
    )
    def process_payment(self, user_id: int, amount: int) -> str:
        """Process payment with validation"""
        return f"Payment processed: User {user_id}, Amount {amount}"
    
    @validate_input(
        question=Validator.validate_prediction_question,
        options=Validator.validate_prediction_options
    )
    async def create_prediction_async(self, question: str, options: List[str]) -> str:
        """Create prediction with async validation"""
        return f"Prediction created: '{question}' with options {options}"


async def demonstrate_validation_decorators():
    """Demonstrate validation decorators"""
    print("\n=== Validation Decorators ===")
    
    service = ExampleService()
    
    # Test sync method with valid input
    print("1. Sync method with valid input:")
    try:
        result = service.process_payment(123456789012345678, 100)
        print(f"   Success: {result}")
    except ValidationError as e:
        print(f"   Error: {e}")
    
    # Test sync method with invalid input
    print("\n2. Sync method with invalid input:")
    try:
        result = service.process_payment("invalid_id", -50)
        print(f"   Success: {result}")
    except ValidationError as e:
        print(f"   Error: {e.details}")
    
    # Test async method with valid input
    print("\n3. Async method with valid input:")
    try:
        result = await service.create_prediction_async(
            "Will it rain tomorrow?", 
            ["Yes", "No"]
        )
        print(f"   Success: {result}")
    except ValidationError as e:
        print(f"   Error: {e}")
    
    # Test async method with invalid input
    print("\n4. Async method with invalid input:")
    try:
        result = await service.create_prediction_async("Hi", ["Only one"])
        print(f"   Success: {result}")
    except ValidationError as e:
        print(f"   Error: {e.details}")


def demonstrate_security_features():
    """Demonstrate security features"""
    print("\n=== Security Features ===")
    
    # XSS prevention
    print("1. XSS Prevention:")
    xss_payload = "<script>alert('XSS')</script>Hello"
    sanitized = Validator.sanitize_text(xss_payload)
    print(f"   Original: {xss_payload}")
    print(f"   Sanitized: {sanitized}")
    
    # SQL injection detection in questions
    print("\n2. SQL Injection Detection:")
    sql_payload = "'; DROP TABLE users; --"
    result = Validator.validate_prediction_question(sql_payload)
    print(f"   SQL payload: {sql_payload}")
    print(f"   Valid: {result.is_valid}")
    print(f"   Errors: {result.errors}")
    
    # Length limiting
    print("\n3. Length Limiting:")
    long_text = "A" * 1000
    limited = Validator.sanitize_text(long_text, max_length=50)
    print(f"   Original length: {len(long_text)}")
    print(f"   Limited length: {len(limited)}")
    print(f"   Limited text: {limited}")


def demonstrate_business_logic_validation():
    """Demonstrate business logic validation"""
    print("\n=== Business Logic Validation ===")
    
    # Balance validation
    print("1. Balance Validation:")
    sufficient = Validator.validate_user_balance(123, 100, 500)
    print(f"   Sufficient balance: {sufficient.is_valid}")
    
    insufficient = Validator.validate_user_balance(123, 1000, 500)
    print(f"   Insufficient balance: {insufficient.is_valid}")
    print(f"   Errors: {insufficient.errors}")
    
    # Duration validation
    print("\n2. Duration Validation:")
    valid_duration = Validator.validate_duration("2d")
    print(f"   Valid duration '2d': {valid_duration.is_valid}")
    print(f"   End time: {valid_duration.sanitized_data}")
    
    invalid_duration = Validator.validate_duration("1000h")
    print(f"   Invalid duration '1000h': {invalid_duration.is_valid}")
    print(f"   Errors: {invalid_duration.errors}")


async def main():
    """Run all demonstrations"""
    print("🔍 Validation Framework Demonstration")
    print("=" * 50)
    
    demonstrate_static_validation()
    demonstrate_input_sanitization()
    await demonstrate_validation_decorators()
    demonstrate_security_features()
    demonstrate_business_logic_validation()
    
    print("\n" + "=" * 50)
    print("✅ Validation Framework Demo Complete!")
    print("\n📋 Features Demonstrated:")
    print("  • Static validation methods for all data types")
    print("  • Input sanitization preventing XSS and injection attacks")
    print("  • Validation decorators for automatic input validation")
    print("  • Business logic validation (balance, duration, etc.)")
    print("  • Comprehensive error handling with detailed messages")
    print("  • Security features protecting against common attacks")


if __name__ == "__main__":
    asyncio.run(main())