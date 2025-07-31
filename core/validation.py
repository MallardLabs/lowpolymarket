"""
Comprehensive validation framework for the Discord Prediction Market Bot.

This module provides validation utilities, decorators, and middleware to ensure
data integrity, security, and proper input sanitization across the application.
"""

import re
import html
import functools
from typing import Any, Dict, List, Optional, Union, Callable, Type, get_type_hints
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum

import discord
from pydantic import BaseModel, ValidationError

from .exceptions import (
    ValidationError as CustomValidationError,
    InsufficientBalanceError,
    PredictionNotFoundError,
    RateLimitExceededError
)


class ValidationSeverity(str, Enum):
    """Validation severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationResult:
    """Result of a validation operation"""
    
    def __init__(self, is_valid: bool = True, errors: List[str] = None, 
                 warnings: List[str] = None, sanitized_data: Any = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
        self.sanitized_data = sanitized_data
    
    def add_error(self, message: str):
        """Add an error message"""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str):
        """Add a warning message"""
        self.warnings.append(message)
    
    def has_errors(self) -> bool:
        """Check if validation has errors"""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if validation has warnings"""
        return len(self.warnings) > 0


class Validator:
    """Static validation methods for various data types and business rules"""
    
    # Regex patterns for common validations
    DISCORD_ID_PATTERN = re.compile(r'^\d{17,20}$')
    PREDICTION_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,50}$')
    SAFE_TEXT_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_.,!?()]+$')
    
    # Dangerous patterns to detect
    INJECTION_PATTERNS = [
        re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'data:', re.IGNORECASE),
        re.compile(r'vbscript:', re.IGNORECASE),
        re.compile(r'on\w+\s*=', re.IGNORECASE),
        re.compile(r'<iframe[^>]*>', re.IGNORECASE),
        re.compile(r'<object[^>]*>', re.IGNORECASE),
        re.compile(r'<embed[^>]*>', re.IGNORECASE),
        re.compile(r'<link[^>]*>', re.IGNORECASE),
        re.compile(r'<meta[^>]*>', re.IGNORECASE),
    ]
    
    SQL_INJECTION_PATTERNS = [
        re.compile(r'\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b', re.IGNORECASE),
        re.compile(r'[\'";]', re.IGNORECASE),
        re.compile(r'--', re.IGNORECASE),
        re.compile(r'/\*.*?\*/', re.IGNORECASE | re.DOTALL),
    ]
    
    @staticmethod
    def sanitize_text(text: str, max_length: int = None, allow_html: bool = False) -> str:
        """
        Sanitize text input to prevent injection attacks
        
        Args:
            text: Input text to sanitize
            max_length: Maximum allowed length
            allow_html: Whether to allow HTML tags (escaped)
            
        Returns:
            Sanitized text
        """
        if not isinstance(text, str):
            text = str(text)
        
        # Remove null bytes and control characters
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        if not allow_html:
            # Remove HTML tags completely
            text = re.sub(r'<[^>]*>', '', text)
            
            # Remove potential script content
            for pattern in Validator.INJECTION_PATTERNS:
                text = pattern.sub('', text)
            
            # Remove remaining script-related content
            text = re.sub(r'alert\([^)]*\)', '', text, flags=re.IGNORECASE)
            text = re.sub(r'script[^>]*', '', text, flags=re.IGNORECASE)
        else:
            # Escape HTML entities
            text = html.escape(text)
        
        # Truncate if max_length specified
        if max_length and len(text) > max_length:
            text = text[:max_length].rstrip()
        
        return text
    
    @staticmethod
    def validate_discord_id(discord_id: Union[str, int]) -> ValidationResult:
        """Validate Discord ID format"""
        result = ValidationResult()
        
        try:
            id_str = str(discord_id)
            if not Validator.DISCORD_ID_PATTERN.match(id_str):
                result.add_error("Invalid Discord ID format")
                return result
            
            id_int = int(id_str)
            if id_int <= 0:
                result.add_error("Discord ID must be positive")
                return result
            
            result.sanitized_data = id_int
            
        except (ValueError, TypeError):
            result.add_error("Discord ID must be a valid integer")
        
        return result
    
    @staticmethod
    def validate_prediction_question(question: str) -> ValidationResult:
        """Validate prediction question"""
        result = ValidationResult()
        
        if not question or not question.strip():
            result.add_error("Question cannot be empty")
            return result
        
        # Sanitize the question
        sanitized = Validator.sanitize_text(question)
        
        if len(sanitized) < 10:
            result.add_error("Question must be at least 10 characters long")
        
        if len(sanitized) > 500:
            result.add_error("Question cannot exceed 500 characters")
            sanitized = sanitized[:500]
        
        # Check for injection attempts (be more specific about what constitutes dangerous content)
        dangerous_patterns = [
            re.compile(r'\b(select|insert|update|delete|drop|create|alter|exec|execute)\b', re.IGNORECASE),
            re.compile(r'[\'";]', re.IGNORECASE),
            re.compile(r'--', re.IGNORECASE),
        ]
        
        for pattern in dangerous_patterns:
            if pattern.search(sanitized):
                result.add_error("Question contains potentially dangerous content")
                break
        
        # Ensure question ends with question mark
        if not sanitized.endswith('?'):
            sanitized += '?'
            result.add_warning("Added question mark to the end")
        
        result.sanitized_data = sanitized
        return result
    
    @staticmethod
    def validate_prediction_options(options: List[str]) -> ValidationResult:
        """Validate prediction options"""
        result = ValidationResult()
        
        if not options or len(options) < 2:
            result.add_error("At least 2 options are required")
            return result
        
        if len(options) > 10:
            result.add_error("Maximum 10 options allowed")
            return result
        
        sanitized_options = []
        seen_options = set()
        
        for option in options:
            if not option or not option.strip():
                result.add_error("Option cannot be empty")
                continue
            
            # Check length before sanitization
            if len(option.strip()) > 100:
                result.add_error("Option cannot exceed 100 characters")
                continue
            
            sanitized = Validator.sanitize_text(option, max_length=100)
            
            if len(sanitized) < 1:
                result.add_error("Option cannot be empty after sanitization")
                continue
            
            # Check for duplicates (case-insensitive)
            option_lower = sanitized.lower()
            if option_lower in seen_options:
                result.add_error(f"Duplicate option: {sanitized}")
                continue
            
            seen_options.add(option_lower)
            sanitized_options.append(sanitized)
        
        if len(sanitized_options) < 2:
            result.add_error("At least 2 valid unique options are required")
        
        result.sanitized_data = sanitized_options
        return result
    
    @staticmethod
    def validate_bet_amount(amount: Union[str, int, float], min_amount: int = 1, 
                          max_amount: int = 1_000_000) -> ValidationResult:
        """Validate bet amount"""
        result = ValidationResult()
        
        try:
            if isinstance(amount, str):
                # Remove common formatting
                amount = amount.replace(',', '').replace(' ', '')
                amount = int(float(amount))
            elif isinstance(amount, float):
                amount = int(amount)
            
            if not isinstance(amount, int):
                result.add_error("Amount must be a valid integer")
                return result
            
            if amount <= 0:
                result.add_error("Amount must be positive")
                return result
            
            if amount < min_amount:
                result.add_error(f"Minimum bet amount is {min_amount:,}")
                return result
            
            if amount > max_amount:
                result.add_error(f"Maximum bet amount is {max_amount:,}")
                return result
            
            result.sanitized_data = amount
            
        except (ValueError, TypeError):
            result.add_error("Amount must be a valid number")
        
        return result
    
    @staticmethod
    def validate_duration(duration_str: str, min_minutes: int = 5, 
                         max_hours: int = 720) -> ValidationResult:
        """Validate and parse duration string"""
        result = ValidationResult()
        
        if not duration_str or not duration_str.strip():
            result.add_error("Duration cannot be empty")
            return result
        
        try:
            # Parse duration string (e.g., "2h", "1d", "3d 2h", "1w")
            duration_str = duration_str.replace(" ", "").lower()
            
            total_minutes = 0
            current_number = ""
            
            for char in duration_str:
                if char.isdigit():
                    current_number += char
                elif char in ['w', 'd', 'h', 'm']:
                    if current_number:
                        num = int(current_number)
                        if char == 'w':  # weeks
                            total_minutes += num * 7 * 24 * 60
                        elif char == 'd':  # days
                            total_minutes += num * 24 * 60
                        elif char == 'h':  # hours
                            total_minutes += num * 60
                        elif char == 'm':  # minutes
                            total_minutes += num
                        current_number = ""
                else:
                    result.add_error(f"Invalid character in duration: {char}")
                    return result
            
            if total_minutes < min_minutes:
                result.add_error(f"Duration must be at least {min_minutes} minutes")
                return result
            
            if total_minutes > max_hours * 60:
                result.add_error(f"Duration cannot exceed {max_hours} hours")
                return result
            
            end_time = datetime.utcnow() + timedelta(minutes=total_minutes)
            result.sanitized_data = end_time
            
        except (ValueError, TypeError):
            result.add_error("Invalid duration format. Use formats like: '2h', '1d', '3d 2h', '1w'")
        
        return result
    
    @staticmethod
    def validate_category(category: str) -> ValidationResult:
        """Validate prediction category"""
        result = ValidationResult()
        
        if not category:
            result.sanitized_data = "general"
            return result
        
        sanitized = Validator.sanitize_text(category)
        
        if len(sanitized) > 50:
            result.add_error("Category cannot exceed 50 characters")
            sanitized = sanitized[:50]
        
        # Convert to lowercase for consistency
        sanitized = sanitized.lower()
        
        # Valid categories
        valid_categories = {
            'general', 'sports', 'politics', 'entertainment', 
            'technology', 'crypto', 'weather', 'other'
        }
        
        if sanitized not in valid_categories:
            result.add_warning(f"Category '{sanitized}' is not in predefined list")
        
        result.sanitized_data = sanitized
        return result
    
    @staticmethod
    def validate_user_balance(user_id: int, required_amount: int, 
                            current_balance: int) -> ValidationResult:
        """Validate user has sufficient balance"""
        result = ValidationResult()
        
        if current_balance < required_amount:
            result.add_error(
                f"Insufficient balance. Required: {required_amount:,}, "
                f"Available: {current_balance:,}"
            )
        
        return result
    
    @staticmethod
    def validate_prediction_id(prediction_id: str) -> ValidationResult:
        """Validate prediction ID format"""
        result = ValidationResult()
        
        if not prediction_id or not prediction_id.strip():
            result.add_error("Prediction ID cannot be empty")
            return result
        
        sanitized = prediction_id.strip()
        
        if not Validator.PREDICTION_ID_PATTERN.match(sanitized):
            result.add_error("Invalid prediction ID format")
            return result
        
        result.sanitized_data = sanitized
        return result
    
    @staticmethod
    def validate_pydantic_model(model_class: Type[BaseModel], data: Dict[str, Any]) -> ValidationResult:
        """Validate data against a Pydantic model"""
        result = ValidationResult()
        
        try:
            validated_model = model_class(**data)
            result.sanitized_data = validated_model
        except ValidationError as e:
            for error in e.errors():
                field_path = " -> ".join(str(loc) for loc in error['loc'])
                result.add_error(f"{field_path}: {error['msg']}")
        except Exception as e:
            result.add_error(f"Validation error: {str(e)}")
        
        return result


def validate_input(**validators):
    """
    Decorator to validate function inputs using specified validators
    
    Usage:
        @validate_input(
            user_id=Validator.validate_discord_id,
            amount=lambda x: Validator.validate_bet_amount(x, min_amount=10)
        )
        def place_bet(user_id, amount):
            pass
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get function signature
            sig = func.__annotations__
            param_names = list(func.__code__.co_varnames[:func.__code__.co_argcount])
            
            # Handle 'self' parameter for method calls
            original_args = args
            is_method = param_names and param_names[0] == 'self'
            
            if is_method:
                param_names = param_names[1:]  # Remove 'self' from param names
                validation_args = args[1:]     # Remove 'self' from args for validation
            else:
                validation_args = args
            
            # Create parameter mapping
            params = dict(zip(param_names, validation_args))
            params.update(kwargs)
            
            # Validate each specified parameter
            validation_errors = []
            sanitized_params = {}
            
            for param_name, validator_func in validators.items():
                if param_name in params:
                    try:
                        validation_result = validator_func(params[param_name])
                        if validation_result.has_errors():
                            validation_errors.extend([
                                f"{param_name}: {error}" for error in validation_result.errors
                            ])
                        else:
                            # Use sanitized data if available
                            if validation_result.sanitized_data is not None:
                                sanitized_params[param_name] = validation_result.sanitized_data
                            else:
                                sanitized_params[param_name] = params[param_name]
                    except Exception as e:
                        validation_errors.append(f"{param_name}: Validation error - {str(e)}")
                else:
                    # Parameter not provided but validator specified
                    validation_errors.append(f"{param_name}: Required parameter missing")
            
            if validation_errors:
                raise CustomValidationError(
                    "Input validation failed",
                    details={"validation_errors": validation_errors}
                )
            
            # Update kwargs with sanitized values
            for param_name, sanitized_value in sanitized_params.items():
                if param_name in kwargs:
                    kwargs[param_name] = sanitized_value
                else:
                    # Find position in validation_args and update
                    try:
                        param_index = param_names.index(param_name)
                        if param_index < len(validation_args):
                            validation_args = list(validation_args)
                            validation_args[param_index] = sanitized_value
                            validation_args = tuple(validation_args)
                    except (ValueError, IndexError):
                        pass
            
            # Reconstruct args with 'self' if it's a method
            if is_method:
                final_args = (original_args[0],) + validation_args
            else:
                final_args = validation_args
            
            return await func(*final_args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Similar logic for sync functions
            sig = func.__annotations__
            param_names = list(func.__code__.co_varnames[:func.__code__.co_argcount])
            
            # Handle 'self' parameter for method calls
            original_args = args
            is_method = param_names and param_names[0] == 'self'
            
            if is_method:
                param_names = param_names[1:]  # Remove 'self' from param names
                validation_args = args[1:]     # Remove 'self' from args for validation
            else:
                validation_args = args
            
            # Create parameter mapping
            params = dict(zip(param_names, validation_args))
            params.update(kwargs)
            
            validation_errors = []
            sanitized_params = {}
            
            for param_name, validator_func in validators.items():
                if param_name in params:
                    try:
                        validation_result = validator_func(params[param_name])
                        if validation_result.has_errors():
                            validation_errors.extend([
                                f"{param_name}: {error}" for error in validation_result.errors
                            ])
                        else:
                            if validation_result.sanitized_data is not None:
                                sanitized_params[param_name] = validation_result.sanitized_data
                            else:
                                sanitized_params[param_name] = params[param_name]
                    except Exception as e:
                        validation_errors.append(f"{param_name}: Validation error - {str(e)}")
                else:
                    validation_errors.append(f"{param_name}: Required parameter missing")
            
            if validation_errors:
                raise CustomValidationError(
                    "Input validation failed",
                    details={"validation_errors": validation_errors}
                )
            
            # Update kwargs with sanitized values
            for param_name, sanitized_value in sanitized_params.items():
                if param_name in kwargs:
                    kwargs[param_name] = sanitized_value
                else:
                    # Find position in validation_args and update
                    try:
                        param_index = param_names.index(param_name)
                        if param_index < len(validation_args):
                            validation_args = list(validation_args)
                            validation_args[param_index] = sanitized_value
                            validation_args = tuple(validation_args)
                    except (ValueError, IndexError):
                        pass
            
            # Reconstruct args with 'self' if it's a method
            if is_method:
                final_args = (original_args[0],) + validation_args
            else:
                final_args = validation_args
            
            return func(*final_args, **kwargs)
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def validate_discord_command(
    validate_permissions: bool = True,
    rate_limit_key: str = None,
    sanitize_inputs: bool = True
):
    """
    Decorator for Discord command validation middleware
    
    Args:
        validate_permissions: Whether to validate user permissions
        rate_limit_key: Key for rate limiting (if None, uses command name)
        sanitize_inputs: Whether to sanitize string inputs
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            try:
                # Rate limiting check
                if hasattr(self, 'rate_limiter') and rate_limit_key:
                    key = f"{rate_limit_key}:{interaction.user.id}"
                    if not await self.rate_limiter.check_rate_limit(key):
                        raise RateLimitExceededError("Rate limit exceeded")
                
                # Permission validation
                if validate_permissions:
                    # Basic permission checks can be added here
                    if not interaction.guild:
                        raise CustomValidationError("Command can only be used in servers")
                
                # Input sanitization
                if sanitize_inputs:
                    sanitized_args = []
                    for arg in args:
                        if isinstance(arg, str):
                            sanitized_args.append(Validator.sanitize_text(arg))
                        else:
                            sanitized_args.append(arg)
                    args = tuple(sanitized_args)
                    
                    sanitized_kwargs = {}
                    for key, value in kwargs.items():
                        if isinstance(value, str):
                            sanitized_kwargs[key] = Validator.sanitize_text(value)
                        else:
                            sanitized_kwargs[key] = value
                    kwargs = sanitized_kwargs
                
                return await func(self, interaction, *args, **kwargs)
                
            except CustomValidationError as e:
                await interaction.response.send_message(
                    f"❌ Validation Error: {e.message}",
                    ephemeral=True
                )
            except RateLimitExceededError:
                await interaction.response.send_message(
                    "⏰ You're doing that too fast! Please wait a moment.",
                    ephemeral=True
                )
            except Exception as e:
                # Log the error and send generic message
                if hasattr(self, 'logger'):
                    self.logger.error(f"Command error: {str(e)}")
                
                await interaction.response.send_message(
                    "❌ An error occurred while processing your command.",
                    ephemeral=True
                )
        
        return wrapper
    return decorator


# Import asyncio at the end to avoid circular imports
import asyncio