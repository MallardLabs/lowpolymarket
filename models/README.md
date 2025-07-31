# Pydantic Data Models

This module provides comprehensive data validation, sanitization, and type conversion for all Discord bot interactions and API requests using Pydantic v2.

## Overview

The `models/schemas.py` file contains:

- **Request Models**: Validate incoming data from Discord commands and API calls
- **Response Models**: Structure outgoing data with type safety
- **Validation Logic**: Custom field validators with sanitization
- **Error Handling**: Standardized error responses
- **Model Factories**: Test utilities for creating mock data
- **Data Sanitization**: Security utilities to prevent injection attacks

## Key Features

### 1. Comprehensive Validation

All models include extensive validation rules:

```python
from models.schemas import CreatePredictionRequest, PredictionCategory

# Valid request with automatic sanitization
request = CreatePredictionRequest(
    question="Will Bitcoin reach $100,000 by end of 2024",  # Auto-adds '?'
    options=["  Yes  ", "  No  "],  # Auto-trims whitespace
    duration_minutes=2880,
    category=PredictionCategory.CRYPTO,
    initial_liquidity=50000
)
```

### 2. Data Sanitization

Built-in protection against common security vulnerabilities:

```python
from models.schemas import SanitizedInput

# Removes script injection attempts
dirty_text = "Hello <script>alert('xss')</script> world"
clean_text = SanitizedInput.sanitize_text(dirty_text)
# Result: "Hello world"

# Validates Discord ID format
user_id = SanitizedInput.validate_discord_id("123456789012345678")
# Result: 123456789012345678 (int)
```

### 3. Error Handling

Standardized error responses with detailed validation information:

```python
from pydantic import ValidationError
from models.schemas import CreatePredictionRequest

try:
    invalid_request = CreatePredictionRequest(
        question="Too short",  # Less than 10 characters
        options=["Only one"],  # Less than 2 options
        duration_minutes=1     # Less than 5 minutes
    )
except ValidationError as e:
    # Get detailed error information
    for error in e.errors():
        field = error['loc'][0]
        message = error['msg']
        print(f"Field '{field}': {message}")
```

## Request Models

### CreatePredictionRequest

Validates prediction creation data:

```python
CreatePredictionRequest(
    question: str,           # 10-500 chars, auto-sanitized
    options: List[str],      # 2-10 unique options, auto-trimmed
    duration_minutes: int,   # 5-43200 minutes (30 days max)
    category: PredictionCategory = GENERAL,
    initial_liquidity: int = 10000  # 1000-1000000
)
```

**Validation Rules:**
- Question must be 10-500 characters
- Automatically adds '?' if missing
- Removes inappropriate content (spam, script injection)
- Options must be 2-10 unique items
- Removes duplicate options (case-insensitive)
- Duration must be 5 minutes to 30 days

### PlaceBetRequest

Validates bet placement data:

```python
PlaceBetRequest(
    prediction_id: str,  # Alphanumeric, hyphens, underscores only
    option: str,         # 1-100 chars, sanitized
    amount: int          # 1-1,000,000 points
)
```

**Validation Rules:**
- Prediction ID must match format `^[a-zA-Z0-9_-]+$`
- Option text is sanitized for security
- Amount must be positive and within limits

### ResolvePredictionRequest

Validates prediction resolution:

```python
ResolvePredictionRequest(
    prediction_id: str,    # Valid ID format
    winning_option: str    # Sanitized option text
)
```

### VoteRequest

Validates resolution voting:

```python
VoteRequest(
    prediction_id: str,  # Valid ID format
    option: str          # Sanitized option text
)
```

## Response Models

### PredictionResponse

Structured prediction data:

```python
PredictionResponse(
    id: str,
    guild_id: int,
    question: str,
    options: List[str],
    creator_id: int,
    category: Optional[str],
    status: PredictionStatus,
    created_at: datetime,
    end_time: datetime,
    resolved: bool = False,
    result: Optional[str] = None,
    refunded: bool = False,
    initial_liquidity: int,
    k_constant: int,
    total_bets: int = 0
)
```

### BetResponse

Structured bet data:

```python
BetResponse(
    id: str,
    prediction_id: str,
    user_id: int,
    guild_id: int,
    option: str,
    amount: int,
    shares: float,
    price_per_share: float,
    created_at: datetime
)
```

### MarketPricesResponse

Market pricing information:

```python
MarketPricesResponse(
    prediction_id: str,
    prices: Dict[str, MarketPriceInfo],
    timestamp: datetime
)

# MarketPriceInfo contains:
# - price_per_share: float
# - potential_shares: float  
# - potential_payout: int
# - probability: float (0-100)
# - total_bets: int
```

## Enums

### PredictionStatus

```python
class PredictionStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"
```

### PredictionCategory

```python
class PredictionCategory(str, Enum):
    GENERAL = "general"
    SPORTS = "sports"
    POLITICS = "politics"
    ENTERTAINMENT = "entertainment"
    TECHNOLOGY = "technology"
    CRYPTO = "crypto"
    WEATHER = "weather"
    OTHER = "other"
```

## Model Factories (Testing)

The `ModelFactory` class provides convenient methods for creating test data:

```python
from models.schemas import ModelFactory

# Create test prediction request
test_prediction = ModelFactory.create_prediction_request(
    question="Will it rain tomorrow?",
    options=["Yes", "No"],
    duration_minutes=1440
)

# Create test bet request
test_bet = ModelFactory.create_bet_request(
    prediction_id="test-prediction-1",
    option="Yes",
    amount=100
)

# Create test response data
test_response = ModelFactory.create_prediction_response(
    id="test-prediction-1",
    status=PredictionStatus.ACTIVE
)
```

## Security Features

### Input Sanitization

All text inputs are automatically sanitized to prevent:

- **Script Injection**: Removes `javascript:`, `data:`, `vbscript:` schemes
- **HTML/XML Injection**: Strips all HTML/XML tags
- **Control Characters**: Removes dangerous control characters
- **Excessive Whitespace**: Normalizes whitespace

### Validation Patterns

- **Discord IDs**: Must be 17-20 digit positive integers
- **Prediction IDs**: Alphanumeric with hyphens/underscores only
- **Text Fields**: Length limits and content filtering
- **Numeric Fields**: Range validation and type checking

## Error Handling

### ValidationError

Pydantic automatically raises `ValidationError` for invalid data:

```python
try:
    request = CreatePredictionRequest(...)
except ValidationError as e:
    # Access detailed error information
    errors = e.errors()
    # Each error contains: loc, msg, type, input
```

### ErrorResponse Model

Standardized error responses:

```python
ErrorResponse(
    error_code: str,           # Error category
    message: str,              # Human-readable message
    details: Optional[Dict],   # Additional context
    error_id: str,            # Unique error identifier
    timestamp: datetime        # When error occurred
)
```

## Usage in Discord Commands

### Command Validation

```python
from discord.ext import commands
from models.schemas import CreatePredictionRequest, ValidationError

@bot.command()
async def create_prediction(ctx, question: str, *options):
    try:
        # Validate input using Pydantic
        request = CreatePredictionRequest(
            question=question,
            options=list(options),
            duration_minutes=1440  # Default 1 day
        )
        
        # Use validated and sanitized data
        prediction = await create_prediction_in_db(request)
        await ctx.send(f"Created prediction: {request.question}")
        
    except ValidationError as e:
        # Send user-friendly error message
        errors = [error['msg'] for error in e.errors()]
        await ctx.send(f"Invalid input: {', '.join(errors)}")
```

### Response Formatting

```python
from models.schemas import PredictionResponse, MarketPricesResponse

async def get_prediction_info(prediction_id: str) -> PredictionResponse:
    # Get data from database
    data = await db.get_prediction(prediction_id)
    
    # Create validated response
    return PredictionResponse(**data)

async def get_market_prices(prediction_id: str) -> MarketPricesResponse:
    # Calculate current prices
    prices = await calculate_market_prices(prediction_id)
    
    # Return structured response
    return MarketPricesResponse(
        prediction_id=prediction_id,
        prices=prices
    )
```

## Testing

Run the comprehensive test suite:

```bash
python3 -m pytest tests/test_schemas.py -v
```

See example usage:

```bash
python3 examples/pydantic_usage.py
```

## Best Practices

1. **Always validate input**: Use request models for all user input
2. **Use response models**: Structure all outgoing data
3. **Handle ValidationError**: Provide user-friendly error messages
4. **Leverage factories**: Use ModelFactory for testing
5. **Sanitize data**: Trust the built-in sanitization
6. **Check field constraints**: Review Field() definitions for limits
7. **Use enums**: Prefer enums over string literals for consistency

## Migration from Raw Data

Before (raw data):
```python
def create_prediction(question, options, duration):
    # Manual validation
    if len(question) < 10:
        raise ValueError("Question too short")
    if len(options) < 2:
        raise ValueError("Need more options")
    # ... more manual checks
```

After (Pydantic models):
```python
def create_prediction(request: CreatePredictionRequest):
    # Validation handled automatically
    # Data is already sanitized and validated
    # Type safety guaranteed
    pass
```

This provides comprehensive data validation, sanitization, and type safety for the entire Discord bot system.