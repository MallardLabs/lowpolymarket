"""
Pydantic data models for request/response validation and data sanitization.

This module provides comprehensive data validation, sanitization, and type conversion
for all Discord bot interactions and API requests.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from enum import Enum
import re
from decimal import Decimal

from pydantic import (
    BaseModel, 
    Field, 
    field_validator,
    model_validator,
    ConfigDict
)


class PredictionStatus(str, Enum):
    """Enumeration of possible prediction statuses"""
    ACTIVE = "active"
    RESOLVED = "resolved"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class PredictionCategory(str, Enum):
    """Enumeration of prediction categories"""
    GENERAL = "general"
    SPORTS = "sports"
    POLITICS = "politics"
    ENTERTAINMENT = "entertainment"
    TECHNOLOGY = "technology"
    CRYPTO = "crypto"
    WEATHER = "weather"
    OTHER = "other"


# Request Models
class CreatePredictionRequest(BaseModel):
    """Request model for creating a new prediction market"""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )
    
    question: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="The prediction question"
    )
    
    options: List[str] = Field(
        ...,
        min_length=2,
        max_length=10,
        description="List of prediction options"
    )
    
    duration_minutes: int = Field(
        ...,
        gt=4,  # Must be greater than 4 (so minimum is 5)
        le=43200,  # 30 days max
        description="Duration in minutes before prediction closes"
    )
    
    category: Optional[PredictionCategory] = Field(
        default=PredictionCategory.GENERAL,
        description="Prediction category"
    )
    
    initial_liquidity: Optional[int] = Field(
        default=10000,
        ge=1000,
        le=1000000,
        description="Initial liquidity for AMM"
    )
    
    @field_validator('question')
    @classmethod
    def validate_question(cls, v):
        """Validate and sanitize question text"""
        if not v or not v.strip():
            raise ValueError("Question cannot be empty")
        
        # Remove excessive whitespace
        v = re.sub(r'\s+', ' ', v.strip())
        
        # Check for inappropriate content patterns
        inappropriate_patterns = [
            r'\b(spam|scam|hack|cheat)\b',
            r'[<>{}[\]\\]',  # Potential injection characters
            r'(javascript:|data:|vbscript:)',  # Script injection
        ]
        
        for pattern in inappropriate_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Question contains inappropriate content")
        
        # Ensure question ends with question mark
        if not v.endswith('?'):
            v += '?'
            
        return v
    
    @field_validator('options')
    @classmethod
    def validate_options(cls, v):
        """Validate and sanitize prediction options"""
        if not v:
            raise ValueError("At least 2 options are required")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_options = []
        for option in v:
            option_clean = option.strip().lower()
            if option_clean and option_clean not in seen:
                seen.add(option_clean)
                unique_options.append(option.strip())
        
        if len(unique_options) < 2:
            raise ValueError("At least 2 unique options are required")
        
        # Validate each option
        validated_options = []
        for option in unique_options:
            # Remove excessive whitespace
            option = re.sub(r'\s+', ' ', option.strip())
            
            if len(option) < 1:
                raise ValueError("Option cannot be empty")
            if len(option) > 100:
                raise ValueError("Option cannot exceed 100 characters")
            
            # Check for inappropriate content
            if re.search(r'[<>{}[\]\\]', option):
                raise ValueError(f"Option '{option}' contains invalid characters")
            
            validated_options.append(option)
        
        return validated_options
    
    @field_validator('duration_minutes')
    @classmethod
    def validate_duration(cls, v):
        """Validate prediction duration"""
        if v < 5:
            raise ValueError("Prediction must be active for at least 5 minutes")
        if v > 43200:  # 30 days
            raise ValueError("Prediction cannot exceed 30 days")
        return v


class PlaceBetRequest(BaseModel):
    """Request model for placing a bet on a prediction"""
    
    model_config = ConfigDict(
        validate_assignment=True,
        extra='forbid'
    )
    
    prediction_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="ID of the prediction to bet on"
    )
    
    option: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Option to bet on"
    )
    
    amount: int = Field(
        ...,
        gt=0,
        le=1_000_000,
        description="Amount of points to bet"
    )
    
    @field_validator('prediction_id')
    @classmethod
    def validate_prediction_id(cls, v):
        """Validate prediction ID format"""
        v = v.strip()
        if not v:
            raise ValueError("Prediction ID cannot be empty")
        
        # Check for valid ID format (alphanumeric, hyphens, underscores)
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Invalid prediction ID format")
        
        return v
    
    @field_validator('option')
    @classmethod
    def validate_option(cls, v):
        """Validate and sanitize bet option"""
        v = v.strip()
        if not v:
            raise ValueError("Option cannot be empty")
        
        # Remove excessive whitespace
        v = re.sub(r'\s+', ' ', v)
        
        # Check for inappropriate content
        if re.search(r'[<>{}[\]\\]', v):
            raise ValueError("Option contains invalid characters")
        
        return v
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        """Validate bet amount"""
        if v <= 0:
            raise ValueError("Bet amount must be positive")
        if v > 1_000_000:
            raise ValueError("Bet amount cannot exceed 1,000,000 points")
        return v


class ResolvePredictionRequest(BaseModel):
    """Request model for resolving a prediction"""
    
    model_config = ConfigDict(
        validate_assignment=True,
        extra='forbid'
    )
    
    prediction_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="ID of the prediction to resolve"
    )
    
    winning_option: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="The winning option"
    )
    
    @field_validator('prediction_id')
    @classmethod
    def validate_prediction_id(cls, v):
        """Validate prediction ID format"""
        v = v.strip()
        if not v:
            raise ValueError("Prediction ID cannot be empty")
        
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Invalid prediction ID format")
        
        return v
    
    @field_validator('winning_option')
    @classmethod
    def validate_winning_option(cls, v):
        """Validate winning option"""
        v = v.strip()
        if not v:
            raise ValueError("Winning option cannot be empty")
        
        v = re.sub(r'\s+', ' ', v)
        
        if re.search(r'[<>{}[\]\\]', v):
            raise ValueError("Winning option contains invalid characters")
        
        return v


class VoteRequest(BaseModel):
    """Request model for voting on prediction resolution"""
    
    model_config = ConfigDict(
        validate_assignment=True,
        extra='forbid'
    )
    
    prediction_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="ID of the prediction to vote on"
    )
    
    option: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Option to vote for"
    )
    
    @field_validator('prediction_id')
    @classmethod
    def validate_prediction_id(cls, v):
        """Validate prediction ID format"""
        v = v.strip()
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Invalid prediction ID format")
        return v
    
    @field_validator('option')
    @classmethod
    def validate_option(cls, v):
        """Validate vote option"""
        v = v.strip()
        if not v:
            raise ValueError("Vote option cannot be empty")
        
        v = re.sub(r'\s+', ' ', v)
        
        if re.search(r'[<>{}[\]\\]', v):
            raise ValueError("Vote option contains invalid characters")
        
        return v


# Response Models
class PredictionResponse(BaseModel):
    """Response model for prediction data"""
    
    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True
    )
    
    id: str
    guild_id: int
    question: str
    options: List[str]
    creator_id: int
    category: Optional[str] = None
    status: PredictionStatus
    created_at: datetime
    end_time: datetime
    resolved: bool = False
    result: Optional[str] = None
    refunded: bool = False
    initial_liquidity: int
    k_constant: int
    total_bets: int = 0


class BetResponse(BaseModel):
    """Response model for bet data"""
    
    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True
    )
    
    id: str
    prediction_id: str
    user_id: int
    guild_id: int
    option: str
    amount: int
    shares: float
    price_per_share: float
    created_at: datetime


class MarketPriceInfo(BaseModel):
    """Market price information for an option"""
    
    price_per_share: float = Field(ge=0, description="Current price per share")
    potential_shares: float = Field(ge=0, description="Shares user would receive")
    potential_payout: int = Field(ge=0, description="Potential payout amount")
    probability: float = Field(ge=0, le=100, description="Implied probability percentage")
    total_bets: int = Field(ge=0, description="Total amount bet on this option")


class MarketPricesResponse(BaseModel):
    """Response model for market prices"""
    
    model_config = ConfigDict(validate_assignment=True)
    
    prediction_id: str
    prices: Dict[str, MarketPriceInfo]
    timestamp: datetime = Field(default_factory=datetime.now)


class UserBalanceResponse(BaseModel):
    """Response model for user balance information"""
    
    model_config = ConfigDict(validate_assignment=True)
    
    user_id: int
    guild_id: int
    balance: int = Field(ge=0)
    total_wagered: int = Field(ge=0, default=0)
    total_won: int = Field(ge=0, default=0)
    active_bets: int = Field(ge=0, default=0)


class ErrorResponse(BaseModel):
    """Standardized error response model"""
    
    model_config = ConfigDict(validate_assignment=True)
    
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    error_id: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ValidationErrorDetail(BaseModel):
    """Detailed validation error information"""
    
    field: str
    message: str
    invalid_value: Optional[Any] = None


class ValidationErrorResponse(ErrorResponse):
    """Validation error response with field details"""
    
    validation_errors: List[ValidationErrorDetail]


# Utility Models for Data Sanitization
class SanitizedInput(BaseModel):
    """Base model for sanitized user input"""
    
    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Sanitize text input to prevent injection attacks"""
        if not text:
            return ""
        
        # Remove potential script injection
        text = re.sub(r'(javascript:|data:|vbscript:)', '', text, flags=re.IGNORECASE)
        
        # Remove HTML/XML tags completely
        text = re.sub(r'<[^>]*>', '', text)
        
        # Remove script content that might remain after tag removal
        text = re.sub(r'alert\([^)]*\)', '', text, flags=re.IGNORECASE)
        text = re.sub(r'script[^>]*', '', text, flags=re.IGNORECASE)
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove control characters except newlines and tabs
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        return text
    
    @classmethod
    def validate_discord_id(cls, discord_id: Union[str, int]) -> int:
        """Validate Discord ID format"""
        try:
            id_int = int(discord_id)
            if id_int <= 0:
                raise ValueError("Discord ID must be positive")
            if len(str(id_int)) < 17 or len(str(id_int)) > 20:
                raise ValueError("Invalid Discord ID format")
            return id_int
        except (ValueError, TypeError):
            raise ValueError("Invalid Discord ID")


# Factory classes for testing
class ModelFactory:
    """Factory class for creating test models"""
    
    @staticmethod
    def create_prediction_request(
        question: str = "Will it rain tomorrow?",
        options: List[str] = None,
        duration_minutes: int = 1440,
        category: PredictionCategory = PredictionCategory.GENERAL,
        initial_liquidity: int = 10000
    ) -> CreatePredictionRequest:
        """Create a test prediction request"""
        if options is None:
            options = ["Yes", "No"]
        
        return CreatePredictionRequest(
            question=question,
            options=options,
            duration_minutes=duration_minutes,
            category=category,
            initial_liquidity=initial_liquidity
        )
    
    @staticmethod
    def create_bet_request(
        prediction_id: str = "test-prediction-1",
        option: str = "Yes",
        amount: int = 100
    ) -> PlaceBetRequest:
        """Create a test bet request"""
        return PlaceBetRequest(
            prediction_id=prediction_id,
            option=option,
            amount=amount
        )
    
    @staticmethod
    def create_resolve_request(
        prediction_id: str = "test-prediction-1",
        winning_option: str = "Yes"
    ) -> ResolvePredictionRequest:
        """Create a test resolve request"""
        return ResolvePredictionRequest(
            prediction_id=prediction_id,
            winning_option=winning_option
        )
    
    @staticmethod
    def create_vote_request(
        prediction_id: str = "test-prediction-1",
        option: str = "Yes"
    ) -> VoteRequest:
        """Create a test vote request"""
        return VoteRequest(
            prediction_id=prediction_id,
            option=option
        )
    
    @staticmethod
    def create_prediction_response(
        id: str = "test-prediction-1",
        guild_id: int = 123456789,
        question: str = "Will it rain tomorrow?",
        options: List[str] = None,
        creator_id: int = 987654321,
        status: PredictionStatus = PredictionStatus.ACTIVE
    ) -> PredictionResponse:
        """Create a test prediction response"""
        if options is None:
            options = ["Yes", "No"]
        
        now = datetime.now()
        return PredictionResponse(
            id=id,
            guild_id=guild_id,
            question=question,
            options=options,
            creator_id=creator_id,
            status=status,
            created_at=now,
            end_time=now + timedelta(days=1),
            initial_liquidity=10000,
            k_constant=100000000
        )
    
    @staticmethod
    def create_bet_response(
        id: str = "test-bet-1",
        prediction_id: str = "test-prediction-1",
        user_id: int = 123456789,
        guild_id: int = 987654321,
        option: str = "Yes",
        amount: int = 100,
        shares: float = 95.0,
        price_per_share: float = 1.05
    ) -> BetResponse:
        """Create a test bet response"""
        return BetResponse(
            id=id,
            prediction_id=prediction_id,
            user_id=user_id,
            guild_id=guild_id,
            option=option,
            amount=amount,
            shares=shares,
            price_per_share=price_per_share,
            created_at=datetime.now()
        )
    
    @staticmethod
    def create_market_prices_response(
        prediction_id: str = "test-prediction-1",
        options: List[str] = None
    ) -> MarketPricesResponse:
        """Create a test market prices response"""
        if options is None:
            options = ["Yes", "No"]
        
        prices = {}
        for i, option in enumerate(options):
            prices[option] = MarketPriceInfo(
                price_per_share=1.0 + (i * 0.1),
                potential_shares=95.0 - (i * 5),
                potential_payout=100,
                probability=50.0 + (i * 10),
                total_bets=1000 + (i * 500)
            )
        
        return MarketPricesResponse(
            prediction_id=prediction_id,
            prices=prices
        )
    
    @staticmethod
    def create_error_response(
        error_code: str = "VALIDATION_ERROR",
        message: str = "Invalid input provided",
        error_id: str = "err-123456"
    ) -> ErrorResponse:
        """Create a test error response"""
        return ErrorResponse(
            error_code=error_code,
            message=message,
            error_id=error_id
        )