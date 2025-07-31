"""
Examples demonstrating the comprehensive validation framework usage.

This module shows how to use the validation framework components:
- Static validation methods
- Validation decorators for service methods
- Discord command validation middleware
- Input sanitization for security
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from typing import List, Optional
from datetime import datetime

try:
    import discord
    from discord.ext import commands
except ImportError:
    # Mock discord for demonstration purposes
    class MockDiscord:
        class Interaction:
            pass
        app_commands = type('app_commands', (), {'command': lambda **kwargs: lambda f: f})()
    discord = MockDiscord()
    commands = type('commands', (), {'Cog': object})()

from core.validation import Validator, validate_input, ValidationResult
from core.validation_middleware import (
    ValidationMiddleware, 
    rate_limit, 
    require_permissions, 
    admin_only, 
    moderator_only,
    validate_inputs,
    sanitize_all_inputs
)
from core.exceptions import ValidationError, InsufficientBalanceError


# Example 1: Using static validation methods
class PredictionService:
    """Example service using static validation methods"""
    
    def create_prediction(self, question: str, options: List[str], 
                         duration: str, category: str = None) -> str:
        """Create a prediction with comprehensive validation"""
        
        # Validate question
        question_result = Validator.validate_prediction_question(question)
        if question_result.has_errors():
            raise ValidationError(
                "Invalid question", 
                details={"errors": question_result.errors}
            )
        
        # Validate options
        options_result = Validator.validate_prediction_options(options)
        if options_result.has_errors():
            raise ValidationError(
                "Invalid options", 
                details={"errors": options_result.errors}
            )
        
        # Validate duration
        duration_result = Validator.validate_duration(duration)
        if duration_result.has_errors():
            raise ValidationError(
                "Invalid duration", 
                details={"errors": duration_result.errors}
            )
        
        # Validate category (optional)
        if category:
            category_result = Validator.validate_category(category)
            if category_result.has_errors():
                raise ValidationError(
                    "Invalid category", 
                    details={"errors": category_result.errors}
                )
            category = category_result.sanitized_data
        
        # Use sanitized data
        sanitized_question = question_result.sanitized_data
        sanitized_options = options_result.sanitized_data
        end_time = duration_result.sanitized_data
        
        print(f"Creating prediction: {sanitized_question}")
        print(f"Options: {sanitized_options}")
        print(f"End time: {end_time}")
        print(f"Category: {category}")
        
        return "pred-12345"  # Mock prediction ID


# Example 2: Using validation decorators for service methods
class BettingService:
    """Example service using validation decorators"""
    
    @validate_input(
        user_id=Validator.validate_discord_id,
        prediction_id=Validator.validate_prediction_id,
        amount=lambda x: Validator.validate_bet_amount(x, min_amount=10, max_amount=100000),
        option=lambda x: Validator.sanitize_text(x, max_length=100)
    )
    async def place_bet(self, user_id: int, prediction_id: str, 
                       amount: int, option: str) -> bool:
        """Place a bet with automatic input validation"""
        
        # Check user balance (example)
        current_balance = 50000  # Mock balance
        balance_result = Validator.validate_user_balance(
            user_id, amount, current_balance
        )
        if balance_result.has_errors():
            raise InsufficientBalanceError(
                required=amount,
                available=current_balance,
                user_id=user_id
            )
        
        print(f"Placing bet: User {user_id}, Amount {amount}, Option '{option}'")
        return True
    
    @validate_input(
        user_id=Validator.validate_discord_id,
        prediction_id=Validator.validate_prediction_id
    )
    async def get_user_bets(self, user_id: int, prediction_id: str) -> List[dict]:
        """Get user bets with validation"""
        print(f"Getting bets for user {user_id} in prediction {prediction_id}")
        return []


# Example 3: Discord Cog with validation middleware
class PredictionCog(commands.Cog):
    """Example Discord cog using validation middleware"""
    
    def __init__(self, bot):
        self.bot = bot
        self.prediction_service = PredictionService()
        self.betting_service = BettingService()
        self.validation_middleware = ValidationMiddleware()
    
    @discord.app_commands.command(name="create_prediction")
    @rate_limit(limit=5, window=300)  # 5 predictions per 5 minutes
    @moderator_only()  # Only moderators can create predictions
    @validate_inputs(
        question=Validator.validate_prediction_question,
        duration=Validator.validate_duration
    )
    async def create_prediction_command(
        self, 
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        duration: str,
        option3: str = None,
        option4: str = None,
        category: str = None
    ):
        """Create a new prediction market"""
        
        # Build options list
        options = [option1, option2]
        if option3:
            options.append(option3)
        if option4:
            options.append(option4)
        
        try:
            prediction_id = self.prediction_service.create_prediction(
                question=question,
                options=options,
                duration=duration,
                category=category
            )
            
            await interaction.response.send_message(
                f"✅ **Prediction Created!**\n"
                f"**ID:** {prediction_id}\n"
                f"**Question:** {question}\n"
                f"**Options:** {', '.join(options)}"
            )
            
        except ValidationError as e:
            await interaction.response.send_message(
                f"❌ **Validation Error**\n{e.user_message}",
                ephemeral=True
            )
    
    @discord.app_commands.command(name="bet")
    @rate_limit(limit=10, window=60)  # 10 bets per minute
    @validate_inputs(
        prediction_id=Validator.validate_prediction_id,
        amount=lambda x: Validator.validate_bet_amount(x, min_amount=1, max_amount=10000),
        option=lambda x: Validator.sanitize_text(x, max_length=100)
    )
    async def place_bet_command(
        self,
        interaction: discord.Interaction,
        prediction_id: str,
        amount: int,
        option: str
    ):
        """Place a bet on a prediction"""
        
        try:
            success = await self.betting_service.place_bet(
                user_id=interaction.user.id,
                prediction_id=prediction_id,
                amount=amount,
                option=option
            )
            
            if success:
                await interaction.response.send_message(
                    f"✅ **Bet Placed!**\n"
                    f"**Amount:** {amount:,} points\n"
                    f"**Option:** {option}\n"
                    f"**Prediction:** {prediction_id}"
                )
            else:
                await interaction.response.send_message(
                    "❌ Failed to place bet. Please try again.",
                    ephemeral=True
                )
                
        except (ValidationError, InsufficientBalanceError) as e:
            await interaction.response.send_message(
                f"❌ {e.user_message}",
                ephemeral=True
            )
    
    @discord.app_commands.command(name="resolve_prediction")
    @admin_only()  # Only admins can resolve predictions
    @sanitize_all_inputs()  # Sanitize all string inputs
    async def resolve_prediction_command(
        self,
        interaction: discord.Interaction,
        prediction_id: str,
        winning_option: str
    ):
        """Resolve a prediction (admin only)"""
        
        await interaction.response.send_message(
            f"✅ **Prediction Resolved!**\n"
            f"**ID:** {prediction_id}\n"
            f"**Winner:** {winning_option}"
        )
    
    @discord.app_commands.command(name="admin_command")
    @require_permissions("administrator", "manage_guild")
    async def admin_command(self, interaction: discord.Interaction):
        """Example command requiring specific permissions"""
        
        await interaction.response.send_message(
            "🔧 **Admin Command Executed**\n"
            "You have the required permissions!"
        )


# Example 4: Custom validation functions
def validate_custom_bet_rules(amount: int, user_level: int) -> ValidationResult:
    """Custom validation for bet amounts based on user level"""
    result = ValidationResult()
    
    # Different limits based on user level
    if user_level == 1:  # Beginner
        max_amount = 1000
    elif user_level == 2:  # Intermediate
        max_amount = 5000
    else:  # Advanced
        max_amount = 50000
    
    if amount > max_amount:
        result.add_error(f"Amount exceeds limit for your level ({max_amount:,})")
    
    result.sanitized_data = amount
    return result


class AdvancedBettingService:
    """Service with custom validation rules"""
    
    @validate_input(
        user_id=Validator.validate_discord_id,
        amount=validate_custom_bet_rules,
        prediction_id=Validator.validate_prediction_id
    )
    async def place_advanced_bet(self, user_id: int, amount: int, 
                               prediction_id: str, user_level: int = 1) -> bool:
        """Place bet with custom validation rules"""
        print(f"Advanced bet: User {user_id}, Amount {amount}")
        return True


# Example 5: Input sanitization demonstration
def demonstrate_input_sanitization():
    """Demonstrate input sanitization capabilities"""
    
    print("=== Input Sanitization Examples ===")
    
    # Dangerous inputs
    dangerous_inputs = [
        "<script>alert('xss')</script>Hello World",
        "'; DROP TABLE users; --",
        "javascript:alert('hack')",
        "Hello<iframe src='evil.com'></iframe>World",
        "Normal text with\x00null bytes\x08and control chars",
        "   Lots   of    whitespace   ",
        "Very long text " * 100,  # Long text
    ]
    
    for dangerous_input in dangerous_inputs:
        sanitized = Validator.sanitize_text(dangerous_input, max_length=100)
        print(f"Original: {repr(dangerous_input[:50])}")
        print(f"Sanitized: {repr(sanitized)}")
        print("---")


# Example 6: Comprehensive validation workflow
async def demonstrate_validation_workflow():
    """Demonstrate complete validation workflow"""
    
    print("=== Validation Workflow Demo ===")
    
    # Initialize services
    prediction_service = PredictionService()
    betting_service = BettingService()
    
    try:
        # 1. Create prediction with validation
        print("1. Creating prediction...")
        prediction_id = prediction_service.create_prediction(
            question="Will it rain tomorrow?",
            options=["Yes", "No", "Maybe"],
            duration="1d",
            category="weather"
        )
        print(f"Created: {prediction_id}")
        
        # 2. Place bet with validation
        print("\n2. Placing bet...")
        success = await betting_service.place_bet(
            user_id=123456789,
            prediction_id=prediction_id,
            amount=100,
            option="Yes"
        )
        print(f"Bet placed: {success}")
        
        # 3. Get user bets
        print("\n3. Getting user bets...")
        bets = await betting_service.get_user_bets(
            user_id=123456789,
            prediction_id=prediction_id
        )
        print(f"User bets: {len(bets)}")
        
    except ValidationError as e:
        print(f"Validation Error: {e.message}")
        print(f"Details: {e.details}")
    except Exception as e:
        print(f"Error: {e}")


# Example usage
if __name__ == "__main__":
    print("=== Validation Framework Usage Examples ===")
    
    # Run demonstrations
    demonstrate_input_sanitization()
    
    # Run async demo
    asyncio.run(demonstrate_validation_workflow())
    
    print("\n=== Validation Framework Examples Complete ===")
    print("✅ All validation framework components are working correctly!")
    print("📋 Features demonstrated:")
    print("  • Static validation methods")
    print("  • Input sanitization and security")
    print("  • Validation decorators")
    print("  • Service layer validation")
    print("  • Comprehensive error handling")