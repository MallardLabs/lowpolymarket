"""
Examples demonstrating the validation framework usage.

This module shows how to use the validation framework in different scenarios:
- Service layer validation
- Discord command validation
- Input sanitization
- Custom validators
"""

import asyncio
from typing import List, Optional
from datetime import datetime

import discord
from discord.ext import commands

from core.validation import Validator, ValidationResult, validate_input
from core.validation_middleware import (
    ValidationMiddleware, 
    rate_limit, 
    admin_only, 
    moderator_only,
    require_permissions,
    validate_inputs,
    sanitize_all_inputs
)
from models.schemas import CreatePredictionRequest, PlaceBetRequest


# Example 1: Service Layer Validation
class PredictionService:
    """Example service with validation decorators"""
    
    @validate_input(
        user_id=Validator.validate_discord_id,
        question=Validator.validate_prediction_question,
        options=Validator.validate_prediction_options,
        duration=lambda x: Validator.validate_duration(x, min_minutes=5, max_hours=168)
    )
    async def create_prediction(self, user_id: int, question: str, 
                              options: List[str], duration: str) -> str:
        """Create a prediction with input validation"""
        # Business logic here - inputs are already validated and sanitized
        print(f"Creating prediction by user {user_id}")
        print(f"Question: {question}")
        print(f"Options: {options}")
        return "prediction-123"
    
    @validate_input(
        user_id=Validator.validate_discord_id,
        prediction_id=Validator.validate_prediction_id,
        amount=lambda x: Validator.validate_bet_amount(x, min_amount=10, max_amount=100000)
    )
    async def place_bet(self, user_id: int, prediction_id: str, 
                       option: str, amount: int) -> bool:
        """Place a bet with validation"""
        # Validate option against prediction options (custom validation)
        option_result = Validator.sanitize_text(option, max_length=100)
        
        print(f"User {user_id} betting {amount} on '{option}' in {prediction_id}")
        return True


# Example 2: Discord Command Validation
class ExampleCog(commands.Cog):
    """Example Discord cog with validation middleware"""
    
    def __init__(self, bot):
        self.bot = bot
        self.validation_middleware = ValidationMiddleware()
    
    @discord.app_commands.command(name="create_prediction")
    @rate_limit(limit=5, window=300)  # 5 predictions per 5 minutes
    @moderator_only()
    @validate_inputs(
        question=Validator.validate_prediction_question,
        duration=lambda x: Validator.validate_duration(x, min_minutes=5)
    )
    async def create_prediction_command(self, interaction: discord.Interaction,
                                      question: str, option1: str, option2: str,
                                      duration: str = "24h"):
        """Create a prediction with comprehensive validation"""
        await interaction.response.defer()
        
        # Options validation
        options_result = Validator.validate_prediction_options([option1, option2])
        if options_result.has_errors():
            await interaction.followup.send(
                f"❌ Invalid options: {', '.join(options_result.errors)}",
                ephemeral=True
            )
            return
        
        # All validation passed, create prediction
        await interaction.followup.send(
            f"✅ Created prediction: {question}\nOptions: {', '.join(options_result.sanitized_data)}"
        )
    
    @discord.app_commands.command(name="place_bet")
    @rate_limit(limit=10, window=60)  # 10 bets per minute
    @sanitize_all_inputs()
    async def place_bet_command(self, interaction: discord.Interaction,
                               prediction_id: str, option: str, amount: int):
        """Place a bet with rate limiting and input sanitization"""
        await interaction.response.defer()
        
        # Validate inputs
        id_result = Validator.validate_prediction_id(prediction_id)
        amount_result = Validator.validate_bet_amount(amount, min_amount=10)
        
        if id_result.has_errors() or amount_result.has_errors():
            errors = id_result.errors + amount_result.errors
            await interaction.followup.send(
                f"❌ Validation errors:\n" + "\n".join(f"• {err}" for err in errors),
                ephemeral=True
            )
            return
        
        await interaction.followup.send(
            f"✅ Placed bet of {amount} on '{option}' in prediction {prediction_id}"
        )
    
    @discord.app_commands.command(name="admin_command")
    @admin_only()
    async def admin_only_command(self, interaction: discord.Interaction):
        """Admin-only command"""
        await interaction.response.send_message("🔧 Admin command executed!", ephemeral=True)
    
    @discord.app_commands.command(name="mod_command")
    @require_permissions("manage_messages", "manage_guild")
    async def permission_required_command(self, interaction: discord.Interaction):
        """Command requiring specific permissions"""
        await interaction.response.send_message("🛡️ Permission check passed!", ephemeral=True)


# Example 3: Custom Validators
class CustomValidators:
    """Custom validation functions for specific business rules"""
    
    @staticmethod
    def validate_prediction_category(category: str) -> ValidationResult:
        """Validate prediction category with custom rules"""
        result = ValidationResult()
        
        if not category:
            result.sanitized_data = "general"
            return result
        
        sanitized = Validator.sanitize_text(category.lower(), max_length=50)
        
        # Custom business rule: certain categories require approval
        restricted_categories = {'politics', 'religion', 'adult'}
        if sanitized in restricted_categories:
            result.add_warning(f"Category '{sanitized}' requires moderator approval")
        
        # Custom validation: category must be alphanumeric
        if not sanitized.replace(' ', '').replace('-', '').isalnum():
            result.add_error("Category must contain only letters, numbers, spaces, and hyphens")
        
        result.sanitized_data = sanitized
        return result
    
    @staticmethod
    def validate_bet_with_balance(amount: int, user_balance: int) -> ValidationResult:
        """Validate bet amount against user balance"""
        result = Validator.validate_bet_amount(amount)
        
        if result.is_valid and amount > user_balance:
            result.add_error(f"Insufficient balance. Required: {amount:,}, Available: {user_balance:,}")
        
        return result
    
    @staticmethod
    def validate_prediction_end_time(end_time: datetime) -> ValidationResult:
        """Validate prediction end time with business rules"""
        result = ValidationResult()
        
        now = datetime.utcnow()
        
        if end_time <= now:
            result.add_error("End time must be in the future")
            return result
        
        # Business rule: predictions can't be longer than 30 days
        max_duration = now.replace(day=now.day + 30) if now.day <= 1 else now.replace(month=now.month + 1)
        if end_time > max_duration:
            result.add_error("Predictions cannot run longer than 30 days")
        
        # Business rule: predictions should be at least 5 minutes
        min_duration = now.replace(minute=now.minute + 5)
        if end_time < min_duration:
            result.add_warning("Very short prediction duration")
        
        result.sanitized_data = end_time
        return result


# Example 4: Pydantic Model Integration
class EnhancedPredictionService:
    """Service demonstrating Pydantic model validation integration"""
    
    async def create_prediction_from_request(self, request_data: dict) -> str:
        """Create prediction using Pydantic model validation"""
        # Validate using Pydantic model
        validation_result = Validator.validate_pydantic_model(
            CreatePredictionRequest, 
            request_data
        )
        
        if validation_result.has_errors():
            raise ValueError(f"Validation failed: {', '.join(validation_result.errors)}")
        
        # Use validated model
        validated_request = validation_result.sanitized_data
        print(f"Creating prediction: {validated_request.question}")
        print(f"Options: {validated_request.options}")
        print(f"Duration: {validated_request.duration_minutes} minutes")
        
        return "prediction-456"
    
    async def place_bet_from_request(self, request_data: dict, user_balance: int) -> bool:
        """Place bet using Pydantic model validation with custom checks"""
        # First validate with Pydantic
        validation_result = Validator.validate_pydantic_model(
            PlaceBetRequest,
            request_data
        )
        
        if validation_result.has_errors():
            raise ValueError(f"Validation failed: {', '.join(validation_result.errors)}")
        
        validated_request = validation_result.sanitized_data
        
        # Additional custom validation
        balance_result = CustomValidators.validate_bet_with_balance(
            validated_request.amount, 
            user_balance
        )
        
        if balance_result.has_errors():
            raise ValueError(f"Balance validation failed: {', '.join(balance_result.errors)}")
        
        print(f"Placing bet: {validated_request.amount} on {validated_request.option}")
        return True


# Example 5: Comprehensive Validation Pipeline
class ValidationPipeline:
    """Example of chaining multiple validators"""
    
    @staticmethod
    async def validate_prediction_creation(user_id: int, question: str, 
                                         options: List[str], duration: str,
                                         category: str = None) -> dict:
        """Comprehensive validation pipeline for prediction creation"""
        results = {}
        errors = []
        warnings = []
        
        # Validate user ID
        user_result = Validator.validate_discord_id(user_id)
        if user_result.has_errors():
            errors.extend(user_result.errors)
        else:
            results['user_id'] = user_result.sanitized_data
        
        # Validate question
        question_result = Validator.validate_prediction_question(question)
        if question_result.has_errors():
            errors.extend(question_result.errors)
        else:
            results['question'] = question_result.sanitized_data
            warnings.extend(question_result.warnings)
        
        # Validate options
        options_result = Validator.validate_prediction_options(options)
        if options_result.has_errors():
            errors.extend(options_result.errors)
        else:
            results['options'] = options_result.sanitized_data
        
        # Validate duration
        duration_result = Validator.validate_duration(duration)
        if duration_result.has_errors():
            errors.extend(duration_result.errors)
        else:
            results['end_time'] = duration_result.sanitized_data
        
        # Validate category (optional)
        if category:
            category_result = CustomValidators.validate_prediction_category(category)
            if category_result.has_errors():
                errors.extend(category_result.errors)
            else:
                results['category'] = category_result.sanitized_data
                warnings.extend(category_result.warnings)
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'sanitized_data': results
        }


# Example usage and testing
async def main():
    """Example usage of the validation framework"""
    
    print("=== Validation Framework Examples ===\n")
    
    # Example 1: Basic validation
    print("1. Basic Validation:")
    question_result = Validator.validate_prediction_question("Will it rain tomorrow")
    print(f"Question validation: {question_result.is_valid}")
    print(f"Sanitized: '{question_result.sanitized_data}'")
    print(f"Warnings: {question_result.warnings}\n")
    
    # Example 2: Options validation
    print("2. Options Validation:")
    options_result = Validator.validate_prediction_options(["Yes", "No", "Maybe", "yes"])
    print(f"Options validation: {options_result.is_valid}")
    print(f"Sanitized: {options_result.sanitized_data}")
    print(f"Errors: {options_result.errors}\n")
    
    # Example 3: Service validation
    print("3. Service Layer Validation:")
    service = PredictionService()
    try:
        prediction_id = await service.create_prediction(
            user_id="123456789012345678",
            question="Will the weather be nice?",
            options=["Yes", "No"],
            duration="2d"
        )
        print(f"Created prediction: {prediction_id}")
    except Exception as e:
        print(f"Validation error: {e}")
    
    print("\n4. Comprehensive Pipeline:")
    pipeline_result = await ValidationPipeline.validate_prediction_creation(
        user_id=123456789012345678,
        question="Will AI take over the world?",
        options=["Yes", "No", "Maybe"],
        duration="1w",
        category="technology"
    )
    
    print(f"Pipeline result: {pipeline_result['is_valid']}")
    if pipeline_result['warnings']:
        print(f"Warnings: {pipeline_result['warnings']}")
    if pipeline_result['errors']:
        print(f"Errors: {pipeline_result['errors']}")
    else:
        print(f"Sanitized data: {pipeline_result['sanitized_data']}")


if __name__ == "__main__":
    asyncio.run(main())