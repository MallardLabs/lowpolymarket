# Discord Prediction Bot - Implementation Guide (Steps 1-9)

This guide explains each component built in the first 9 steps of the implementation plan, focusing on practical usage and real-world benefits for your Discord prediction/betting bot.

## Step 1: Configuration Management System

### 1️⃣ What I Built

A centralized configuration system using Pydantic BaseSettings that manages all bot settings across different environments (development, staging, production).

**Key Files:**
- `config/settings.py` - Main configuration classes
- `config/validation.py` - Configuration validation
- `.env.example` - Environment variable template

### 2️⃣ Why It's Important

**Problems It Solves:**
- **Configuration Chaos**: No more scattered config files or hardcoded values
- **Environment Issues**: Prevents "works on my machine" problems
- **Security Risks**: Keeps sensitive data (tokens, passwords) out of code
- **Validation Errors**: Catches configuration mistakes before they cause runtime errors

### 3️⃣ Practical Advantages

- **Type Safety**: All config values are typed and validated
- **Environment Switching**: Easy switching between dev/staging/prod
- **Error Prevention**: Invalid configs fail fast with clear error messages
- **Documentation**: Self-documenting configuration with field descriptions

### 4️⃣ How to Use It Daily

**Basic Usage:**
```python
from config.settings import get_settings

# Get configuration anywhere in your code
settings = get_settings()

# Access typed configuration values
discord_token = settings.discord.token
database_url = settings.database.url
max_bet = settings.business.max_bet_amount
```

**Environment Setup:**
```bash
# Create .env file for your environment
cp .env.example .env

# Edit with your values
DISCORD_TOKEN=your_bot_token_here
DATABASE_URL=postgresql://user:pass@localhost/db
API_KEY=your_drip_api_key
```

**Adding New Configuration:**
```python
# In config/settings.py
class NewFeatureSettings(BaseSettings):
    enabled: bool = Field(True, description="Enable new feature")
    timeout: int = Field(30, description="Timeout in seconds")
    
    model_config = SettingsConfigDict(env_prefix="FEATURE_")

# Add to main Settings class
class Settings(BaseSettings):
    # ... existing settings
    new_feature: NewFeatureSettings = Field(default_factory=NewFeatureSettings)
```

### 5️⃣ How It Connects to Other Components

- **Logging System**: Uses logging settings for log levels and formats
- **Database**: Provides connection strings and pool settings
- **Rate Limiting**: Configures rate limits and windows
- **Security**: Sets encryption keys and security levels
- **All Services**: Every component gets its config from this system

### 6️⃣ Common Mistakes to Avoid

❌ **Don't hardcode values:**
```python
# BAD
max_bet = 1000000
```

✅ **Use configuration:**
```python
# GOOD
max_bet = settings.business.max_bet_amount
```

❌ **Don't access environment variables directly:**
```python
# BAD
import os
token = os.getenv('DISCORD_TOKEN')
```

✅ **Use the settings system:**
```python
# GOOD
token = settings.discord.token
```

### 7️⃣ Testing and Verification

**Test Configuration Loading:**
```python
# Run the validation script
python scripts/validate_config.py

# Test in Python
from config.settings import get_settings
settings = get_settings()
print(f"Bot configured for: {settings.environment}")
```

**Environment-Specific Testing:**
```bash
# Test different environments
ENVIRONMENT=development python -c "from config.settings import get_settings; print(get_settings().environment)"
ENVIRONMENT=production python -c "from config.settings import get_settings; print(get_settings().environment)"
```

---

## Step 2: Dependency Injection Container

### 1️⃣ What I Built

A dependency injection container that manages all application services and their dependencies, ensuring proper initialization order and lifecycle management.

**Key Files:**
- `core/container.py` - Main DI container implementation
- `examples/di_container_integration.py` - Usage examples

### 2️⃣ Why It's Important

**Problems It Solves:**
- **Tight Coupling**: Services don't need to know how to create their dependencies
- **Initialization Order**: Ensures services are created in the right order
- **Testing Difficulty**: Makes it easy to mock dependencies for testing
- **Memory Leaks**: Proper lifecycle management prevents resource leaks

### 3️⃣ Practical Advantages

- **Loose Coupling**: Services only depend on interfaces, not implementations
- **Easy Testing**: Swap real services for mocks during testing
- **Configuration**: Change implementations without code changes
- **Lifecycle Management**: Automatic cleanup of resources

### 4️⃣ How to Use It Daily

**Register Services:**
```python
from core.container import DIContainer

# Create container
container = DIContainer()

# Register services
container.register_singleton('database', DatabaseService)
container.register_transient('prediction_service', PredictionService)
container.register_factory('cache', lambda: RedisCache(settings.cache.redis_url))
```

**Use in Discord Cogs:**
```python
class PredictionCog(commands.Cog):
    def __init__(self, bot, container: DIContainer):
        self.bot = bot
        self.prediction_service = container.get('prediction_service')
        self.database = container.get('database')
    
    @discord.app_commands.command()
    async def create_prediction(self, interaction, question: str):
        # Use injected services
        result = await self.prediction_service.create(question)
        await interaction.response.send_message(f"Created: {result.id}")
```

**Service Implementation:**
```python
class PredictionService:
    def __init__(self, database: DatabaseService, cache: CacheService):
        self.database = database
        self.cache = cache
    
    async def create(self, question: str):
        # Service logic here
        pass
```

### 5️⃣ How It Connects to Other Components

- **Configuration**: Services get their config through injection
- **Logging**: Logger instances are injected into services
- **Database**: Database connections are managed and injected
- **Caching**: Cache instances are shared across services
- **Error Handling**: Error handlers are injected for consistent error management

### 6️⃣ Common Mistakes to Avoid

❌ **Don't create services manually:**
```python
# BAD
class PredictionCog:
    def __init__(self):
        self.database = DatabaseService()  # Manual creation
```

✅ **Use dependency injection:**
```python
# GOOD
class PredictionCog:
    def __init__(self, database: DatabaseService):
        self.database = database  # Injected
```

❌ **Don't ignore lifecycle management:**
```python
# BAD - No cleanup
container.register_singleton('database', DatabaseService)
```

✅ **Implement proper cleanup:**
```python
# GOOD
@container.on_shutdown
async def cleanup_database():
    await container.get('database').close()
```

### 7️⃣ Testing and Verification

**Test Service Registration:**
```python
# Test the container
python -m pytest tests/test_di_container.py -v

# Manual testing
from core.container import DIContainer
container = DIContainer()
container.register_singleton('test_service', TestService)
service = container.get('test_service')
assert service is not None
```

---

## Step 3: Custom Exception Hierarchy

### 1️⃣ What I Built

A comprehensive exception system with structured error handling, unique error IDs, and user-friendly messages for Discord interactions.

**Key Files:**
- `core/exceptions.py` - Exception hierarchy
- `examples/exception_usage.py` - Usage examples

### 2️⃣ Why It's Important

**Problems It Solves:**
- **Generic Errors**: No more generic "Something went wrong" messages
- **Debugging Difficulty**: Error IDs make it easy to track specific issues
- **User Experience**: Users get helpful, actionable error messages
- **Error Tracking**: Structured errors enable better monitoring and alerting

### 3️⃣ Practical Advantages

- **Specific Error Types**: Different exceptions for different problems
- **Error Tracking**: Unique IDs for each error instance
- **User-Friendly Messages**: Discord users see helpful messages
- **Structured Data**: Errors include context for debugging
- **Severity Levels**: Different handling based on error severity

### 4️⃣ How to Use It Daily

**Raise Specific Exceptions:**
```python
from core.exceptions import InsufficientBalanceError, ValidationError

# In your service methods
async def place_bet(self, user_id: int, amount: int):
    user_balance = await self.get_balance(user_id)
    
    if user_balance < amount:
        raise InsufficientBalanceError(
            required=amount,
            available=user_balance,
            user_id=user_id
        )
    
    if amount < 1:
        raise ValidationError(
            message="Bet amount must be positive",
            field="amount",
            value=amount
        )
```

**Handle in Discord Commands:**
```python
@discord.app_commands.command()
async def bet(self, interaction, amount: int):
    try:
        await self.betting_service.place_bet(interaction.user.id, amount)
        await interaction.response.send_message("✅ Bet placed!")
    
    except InsufficientBalanceError as e:
        # User gets friendly message: "💰 You need 1,000 points but only have 500 available!"
        await interaction.response.send_message(e.user_message, ephemeral=True)
    
    except ValidationError as e:
        # User gets specific validation error
        await interaction.response.send_message(f"❌ {e.user_message}", ephemeral=True)
```

**Create Custom Exceptions:**
```python
class PredictionExpiredError(PredictionMarketError):
    def __init__(self, prediction_id: str, expired_at: datetime, **kwargs):
        super().__init__(
            message=f"Prediction {prediction_id} expired at {expired_at}",
            error_code="PREDICTION_EXPIRED",
            user_message="⏰ This prediction has expired and no longer accepts bets!",
            details={"prediction_id": prediction_id, "expired_at": expired_at.isoformat()},
            severity=ErrorSeverity.LOW,
            **kwargs
        )
```

### 5️⃣ How It Connects to Other Components

- **Error Handler**: Catches and processes these exceptions
- **Logging**: Structured error data is logged automatically
- **Discord UI**: User-friendly messages are shown to users
- **Monitoring**: Error IDs and severity levels enable alerting
- **Validation**: Validation errors use this exception system

### 6️⃣ Common Mistakes to Avoid

❌ **Don't use generic exceptions:**
```python
# BAD
raise Exception("Something went wrong")
```

✅ **Use specific exception types:**
```python
# GOOD
raise InsufficientBalanceError(required=100, available=50, user_id=123)
```

❌ **Don't ignore error context:**
```python
# BAD
raise ValidationError("Invalid input")
```

✅ **Include helpful context:**
```python
# GOOD
raise ValidationError(
    message="Bet amount must be between 1 and 1,000,000",
    field="amount",
    value=amount,
    details={"min": 1, "max": 1000000}
)
```

### 7️⃣ Testing and Verification

**Test Exception Behavior:**
```python
# Run exception tests
python -m pytest tests/test_exceptions.py -v

# Test specific exception
from core.exceptions import InsufficientBalanceError

try:
    raise InsufficientBalanceError(required=100, available=50, user_id=123)
except InsufficientBalanceError as e:
    print(f"Error ID: {e.error_id}")
    print(f"User Message: {e.user_message}")
    print(f"Details: {e.details}")
```

---

## Step 4: Comprehensive Error Handler

### 1️⃣ What I Built

A centralized error handling system with Discord integration, retry logic, circuit breakers, and structured error logging.

**Key Files:**
- `core/error_handler.py` - Main error handler
- `core/ERROR_HANDLER_SUMMARY.md` - Detailed documentation

### 2️⃣ Why It's Important

**Problems It Solves:**
- **Inconsistent Error Handling**: Standardizes how errors are handled across the bot
- **Poor User Experience**: Users get consistent, helpful error messages
- **Service Failures**: Automatic retries and circuit breakers prevent cascading failures
- **Debugging Difficulty**: Structured logging makes issues easier to track

### 3️⃣ Practical Advantages

- **Automatic Retries**: Transient failures are retried automatically
- **Circuit Breaker**: Prevents cascading failures from external services
- **User-Friendly Messages**: Discord users see helpful error messages
- **Structured Logging**: All errors are logged with context and correlation IDs
- **Error Recovery**: Graceful degradation when services fail

### 4️⃣ How to Use It Daily

**Use Retry Decorator:**
```python
from core.error_handler import retry_with_backoff

@retry_with_backoff(max_retries=3, base_delay=1.0)
async def call_external_api():
    # This will retry up to 3 times with exponential backoff
    response = await external_api.get_data()
    return response
```

**Use Circuit Breaker:**
```python
from core.error_handler import circuit_breaker

@circuit_breaker(failure_threshold=5, recovery_timeout=60)
async def get_market_data():
    # Circuit opens after 5 failures, stays open for 60 seconds
    return await market_api.get_prices()
```

**Handle Discord Errors:**
```python
from core.error_handler import ErrorHandler

class PredictionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.error_handler = ErrorHandler()
    
    @discord.app_commands.command()
    async def create_prediction(self, interaction, question: str):
        try:
            result = await self.prediction_service.create(question)
            await interaction.response.send_message(f"Created: {result.id}")
        except Exception as e:
            # Error handler manages the response
            await self.error_handler.handle_discord_error(interaction, e)
```

**Custom Error Handling:**
```python
async def handle_betting_error(self, interaction, error):
    if isinstance(error, InsufficientBalanceError):
        embed = discord.Embed(
            title="💰 Insufficient Balance",
            description=error.user_message,
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        # Fallback to default handler
        await self.error_handler.handle_discord_error(interaction, error)
```

### 5️⃣ How It Connects to Other Components

- **Exception System**: Processes custom exceptions with appropriate handling
- **Logging**: All errors are logged with structured data
- **Discord UI**: Provides consistent error messages to users
- **Monitoring**: Error patterns trigger alerts and monitoring
- **Services**: Protects service calls with retries and circuit breakers

### 6️⃣ Common Mistakes to Avoid

❌ **Don't ignore error handling:**
```python
# BAD
@discord.app_commands.command()
async def bet(self, interaction, amount: int):
    result = await self.betting_service.place_bet(amount)  # No error handling
```

✅ **Always handle errors:**
```python
# GOOD
@discord.app_commands.command()
async def bet(self, interaction, amount: int):
    try:
        result = await self.betting_service.place_bet(amount)
        await interaction.response.send_message("✅ Bet placed!")
    except Exception as e:
        await self.error_handler.handle_discord_error(interaction, e)
```

❌ **Don't overuse retries:**
```python
# BAD - Retrying user input validation
@retry_with_backoff(max_retries=3)
async def validate_user_input(input_data):
    # User input won't change on retry!
```

✅ **Only retry transient failures:**
```python
# GOOD - Retrying network calls
@retry_with_backoff(max_retries=3)
async def fetch_external_data():
    # Network issues might resolve on retry
```

### 7️⃣ Testing and Verification

**Test Error Handling:**
```python
# Run error handler tests
python -m pytest tests/test_error_handler.py -v

# Test retry behavior
from core.error_handler import retry_with_backoff
import asyncio

@retry_with_backoff(max_retries=3)
async def failing_function():
    print("Attempting...")
    raise Exception("Temporary failure")

# This will retry 3 times
try:
    await failing_function()
except Exception as e:
    print(f"Final failure: {e}")
```

---

## Step 5: Structured Logging System

### 1️⃣ What I Built

A comprehensive logging system with JSON formatting, correlation IDs, log rotation, and contextual logging for better debugging and monitoring.

**Key Files:**
- `core/logging_manager.py` - Main logging system
- `core/LOGGING_SYSTEM_SUMMARY.md` - Detailed documentation

### 2️⃣ Why It's Important

**Problems It Solves:**
- **Debugging Difficulty**: Correlation IDs let you trace requests across services
- **Log Chaos**: Structured JSON logs are easily searchable and parseable
- **Performance Issues**: Function timing and performance logging
- **Production Monitoring**: Proper log levels and rotation for production use

### 3️⃣ Practical Advantages

- **Correlation Tracking**: Follow a single request through the entire system
- **Structured Data**: JSON logs work with log aggregation tools
- **Performance Monitoring**: Automatic function timing and slow query detection
- **Context Preservation**: User ID, guild ID, and operation context in every log
- **Production Ready**: Log rotation, levels, and file management

### 4️⃣ How to Use It Daily

**Basic Logging:**
```python
from core.logging_manager import get_logger

logger = get_logger(__name__)

# Basic logging
logger.info("Processing bet placement")
logger.warning("High bet amount detected", extra={"amount": 50000})
logger.error("Database connection failed", extra={"error": str(e)})
```

**Contextual Logging:**
```python
from core.logging_manager import get_logger, LogContext

logger = get_logger(__name__)

# Log with context
context = LogContext(
    user_id=interaction.user.id,
    guild_id=interaction.guild.id,
    operation="place_bet",
    extra={"amount": 1000, "prediction_id": "pred_123"}
)

logger.info("Bet placed successfully", extra=context.__dict__)
```

**Function Timing:**
```python
from core.logging_manager import log_function_call, log_performance

@log_function_call(include_args=True, include_duration=True)
async def place_bet(user_id: int, amount: int):
    # Function entry/exit automatically logged
    return await self.database.create_bet(user_id, amount)

@log_performance(threshold_seconds=2.0)
async def complex_calculation():
    # Logs warning if function takes longer than 2 seconds
    return await heavy_computation()
```

**Correlation ID Tracking:**
```python
from core.logging_manager import set_correlation_id, get_correlation_id

# Set correlation ID at request start
correlation_id = set_correlation_id()

# All subsequent logs will include this ID
logger.info("Starting bet processing")

# Pass to other services
await other_service.process(correlation_id=get_correlation_id())
```

### 5️⃣ How It Connects to Other Components

- **Error Handler**: All errors are logged with full context
- **Security**: Security violations and audit events are logged
- **Performance**: Slow queries and functions are automatically logged
- **Discord Commands**: Each command gets a correlation ID for tracking
- **Services**: All service operations include contextual logging

### 6️⃣ Common Mistakes to Avoid

❌ **Don't use print statements:**
```python
# BAD
print(f"User {user_id} placed bet")
```

✅ **Use proper logging:**
```python
# GOOD
logger.info("Bet placed", extra={"user_id": user_id, "amount": amount})
```

❌ **Don't log sensitive data:**
```python
# BAD
logger.info("User login", extra={"password": password})
```

✅ **Mask sensitive information:**
```python
# GOOD
logger.info("User login", extra={"user_id": user_id, "password": "***"})
```

❌ **Don't ignore log levels:**
```python
# BAD - Everything as INFO
logger.info("Debug information")
logger.info("Critical error occurred")
```

✅ **Use appropriate log levels:**
```python
# GOOD
logger.debug("Debug information")
logger.error("Critical error occurred")
```

### 7️⃣ Testing and Verification

**Test Logging:**
```python
# Run logging tests
python -m pytest tests/test_logging_manager.py -v

# Test correlation IDs
from core.logging_manager import set_correlation_id, get_logger

logger = get_logger("test")
correlation_id = set_correlation_id()
logger.info("Test message")
# Check logs for correlation ID
```

**Monitor Log Output:**
```bash
# Watch logs in real-time
tail -f logs/discord.log

# Search logs by correlation ID
grep "correlation_id.*abc123" logs/discord.log

# Parse JSON logs
cat logs/discord.log | jq '.message'
```

---

## Step 6: Pydantic Data Models

### 1️⃣ What I Built

Comprehensive data models using Pydantic for request/response validation, type safety, and automatic data conversion with custom validators.

**Key Files:**
- `models/schemas.py` - All data models
- `examples/pydantic_usage.py` - Usage examples

### 2️⃣ Why It's Important

**Problems It Solves:**
- **Data Validation**: Ensures all data meets requirements before processing
- **Type Safety**: Prevents runtime errors from incorrect data types
- **API Consistency**: Standardizes request/response formats
- **Documentation**: Self-documenting data structures with field descriptions

### 3️⃣ Practical Advantages

- **Automatic Validation**: Invalid data is rejected with clear error messages
- **Type Conversion**: Strings are automatically converted to appropriate types
- **IDE Support**: Full autocomplete and type checking in your IDE
- **Serialization**: Easy conversion to/from JSON for API responses
- **Testing**: Consistent data structures make testing easier

### 4️⃣ How to Use It Daily

**Request Validation:**
```python
from models.schemas import CreatePredictionRequest, PlaceBetRequest

@discord.app_commands.command()
async def create_prediction(self, interaction, question: str, option1: str, option2: str):
    try:
        # Validate input data
        request = CreatePredictionRequest(
            question=question,
            options=[option1, option2],
            creator_id=interaction.user.id,
            guild_id=interaction.guild.id
        )
        
        # Use validated data
        result = await self.prediction_service.create(request)
        await interaction.response.send_message(f"Created: {result.prediction_id}")
        
    except ValidationError as e:
        await interaction.response.send_message(f"❌ Invalid input: {e}", ephemeral=True)
```

**Service Layer Usage:**
```python
from models.schemas import PredictionResponse, BetResponse

class PredictionService:
    async def create(self, request: CreatePredictionRequest) -> PredictionResponse:
        # Input is already validated
        prediction_data = {
            "question": request.question,
            "options": request.options,
            "creator_id": request.creator_id,
            "guild_id": request.guild_id
        }
        
        # Create in database
        prediction = await self.database.create_prediction(prediction_data)
        
        # Return validated response
        return PredictionResponse(
            prediction_id=prediction.id,
            question=prediction.question,
            options=prediction.options,
            status=prediction.status,
            created_at=prediction.created_at
        )
```

**Custom Validators:**
```python
from pydantic import BaseModel, Field, field_validator

class BetRequest(BaseModel):
    amount: int = Field(..., description="Bet amount in points")
    prediction_id: str = Field(..., description="Prediction ID")
    option_index: int = Field(..., description="Selected option index")
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        if v < 1:
            raise ValueError('Bet amount must be positive')
        if v > 1_000_000:
            raise ValueError('Bet amount cannot exceed 1,000,000')
        return v
    
    @field_validator('prediction_id')
    @classmethod
    def validate_prediction_id(cls, v):
        if not v.startswith('pred_'):
            raise ValueError('Invalid prediction ID format')
        return v
```

### 5️⃣ How It Connects to Other Components

- **Validation Framework**: Works with validation decorators and middleware
- **Error Handling**: Validation errors are handled by the error system
- **Database**: Models define the structure of database operations
- **API Responses**: Consistent response formats for Discord interactions
- **Testing**: Models provide consistent test data structures

### 6️⃣ Common Mistakes to Avoid

❌ **Don't skip validation:**
```python
# BAD - No validation
async def create_prediction(question, options):
    # What if question is None? What if options is empty?
    return await self.database.create(question, options)
```

✅ **Always validate input:**
```python
# GOOD
async def create_prediction(request: CreatePredictionRequest):
    # Input is guaranteed to be valid
    return await self.database.create(request.question, request.options)
```

❌ **Don't ignore field constraints:**
```python
# BAD
class BetRequest(BaseModel):
    amount: int  # No constraints
```

✅ **Use proper field validation:**
```python
# GOOD
class BetRequest(BaseModel):
    amount: int = Field(ge=1, le=1_000_000, description="Bet amount in points")
```

### 7️⃣ Testing and Verification

**Test Model Validation:**
```python
# Run model tests
python -m pytest tests/test_schemas.py -v

# Test validation manually
from models.schemas import CreatePredictionRequest

# Valid data
request = CreatePredictionRequest(
    question="Will it rain tomorrow?",
    options=["Yes", "No"],
    creator_id=123456789,
    guild_id=987654321
)

# Invalid data (will raise ValidationError)
try:
    invalid_request = CreatePredictionRequest(
        question="",  # Empty question
        options=["Yes"],  # Only one option
        creator_id="invalid",  # Wrong type
        guild_id=987654321
    )
except ValidationError as e:
    print(f"Validation errors: {e}")
```

---

## Step 7: Validation Framework

### 1️⃣ What I Built

A comprehensive validation system with decorators, middleware, and input sanitization to prevent injection attacks and ensure data integrity.

**Key Files:**
- `core/validation.py` - Main validation framework
- `core/validation_middleware.py` - Discord command middleware

### 2️⃣ Why It's Important

**Problems It Solves:**
- **Security Vulnerabilities**: Prevents SQL injection, XSS, and other attacks
- **Data Corruption**: Ensures all data meets business rules before processing
- **Inconsistent Validation**: Standardizes validation across all commands
- **Poor Error Messages**: Provides clear, actionable validation feedback

### 3️⃣ Practical Advantages

- **Security**: Automatic input sanitization prevents injection attacks
- **Consistency**: Same validation rules applied everywhere
- **Performance**: Validation happens before expensive operations
- **User Experience**: Clear error messages help users fix their input
- **Maintainability**: Centralized validation logic is easier to update

### 4️⃣ How to Use It Daily

**Validation Decorators:**
```python
from core.validation import validate_input, Validator

@validate_input(
    user_id=Validator.validate_discord_id,
    amount=lambda x: Validator.validate_bet_amount(x, min_amount=1, max_amount=1000000),
    question=Validator.validate_prediction_question
)
async def create_prediction(user_id: int, amount: int, question: str):
    # All inputs are validated and sanitized before this runs
    return await self.database.create_prediction(user_id, amount, question)
```

**Discord Command Middleware:**
```python
from core.validation_middleware import validate_inputs, require_permissions

@validate_inputs(
    question=Validator.validate_prediction_question,
    duration=lambda x: Validator.validate_duration(x, min_minutes=5, max_hours=168)
)
@require_permissions('manage_messages')
@discord.app_commands.command()
async def create_prediction(self, interaction, question: str, duration: str):
    # Input is validated, user permissions are checked
    end_time = await self.validator.validate_duration(duration)
    result = await self.prediction_service.create(question, end_time)
    await interaction.response.send_message(f"Created: {result.id}")
```

**Manual Validation:**
```python
from core.validation import Validator

async def process_bet(self, user_input: str, amount_str: str):
    # Validate and sanitize user input
    question_result = Validator.validate_prediction_question(user_input)
    if question_result.has_errors():
        raise ValidationError(f"Invalid question: {', '.join(question_result.errors)}")
    
    # Validate bet amount
    amount_result = Validator.validate_bet_amount(amount_str)
    if amount_result.has_errors():
        raise ValidationError(f"Invalid amount: {', '.join(amount_result.errors)}")
    
    # Use sanitized data
    clean_question = question_result.sanitized_data
    clean_amount = amount_result.sanitized_data
    
    return await self.create_bet(clean_question, clean_amount)
```

**Custom Validators:**
```python
from core.validation import ValidationResult

def validate_custom_field(value: str) -> ValidationResult:
    result = ValidationResult()
    
    if not value or len(value.strip()) == 0:
        result.add_error("Field cannot be empty")
        return result
    
    # Custom business logic
    if "forbidden_word" in value.lower():
        result.add_error("Contains forbidden content")
        return result
    
    # Sanitize the value
    sanitized = value.strip().title()
    result.sanitized_data = sanitized
    
    return result
```

### 5️⃣ How It Connects to Other Components

- **Security System**: Works with input sanitization and threat detection
- **Pydantic Models**: Validates data before model creation
- **Error Handling**: Validation errors are processed by error handlers
- **Discord Middleware**: Automatic validation for all Discord commands
- **Logging**: Validation failures are logged for monitoring

### 6️⃣ Common Mistakes to Avoid

❌ **Don't trust user input:**
```python
# BAD - No validation
async def create_prediction(question: str):
    # What if question contains SQL injection?
    await self.database.execute(f"INSERT INTO predictions (question) VALUES ('{question}')")
```

✅ **Always validate and sanitize:**
```python
# GOOD
@validate_input(question=Validator.validate_prediction_question)
async def create_prediction(question: str):
    # Question is validated and sanitized
    await self.database.create_prediction(question)
```

❌ **Don't ignore validation results:**
```python
# BAD
result = Validator.validate_bet_amount(amount)
# Ignoring result.has_errors()
```

✅ **Check validation results:**
```python
# GOOD
result = Validator.validate_bet_amount(amount)
if result.has_errors():
    raise ValidationError(f"Invalid amount: {', '.join(result.errors)}")
```

### 7️⃣ Testing and Verification

**Test Validation:**
```python
# Run validation tests
python -m pytest tests/test_validation_framework.py -v

# Test specific validators
from core.validation import Validator

# Test valid input
result = Validator.validate_prediction_question("Will it rain tomorrow?")
assert result.is_valid
assert result.sanitized_data == "Will it rain tomorrow?"

# Test invalid input
result = Validator.validate_prediction_question("<script>alert('xss')</script>")
assert not result.is_valid
assert "script" not in result.sanitized_data
```

---

## Step 8: Rate Limiting System

### 1️⃣ What I Built

A sophisticated rate limiting system with sliding window algorithm, per-user and per-guild limits, admin bypass, and Discord command integration.

**Key Files:**
- `core/rate_limiter.py` - Core rate limiting logic
- `core/rate_limit_middleware.py` - Discord integration

### 2️⃣ Why It's Important

**Problems It Solves:**
- **Spam Prevention**: Stops users from flooding commands
- **Resource Protection**: Prevents abuse that could crash the bot
- **Fair Usage**: Ensures all users get equal access to bot features
- **Cost Control**: Limits expensive operations like API calls

### 3️⃣ Practical Advantages

- **Flexible Limits**: Different limits for different commands and user types
- **Sliding Window**: More accurate than simple time-based limits
- **Admin Override**: Administrators can bypass limits when needed
- **Graceful Degradation**: Users get helpful messages when limited
- **Monitoring**: Rate limit violations are logged and monitored

### 4️⃣ How to Use It Daily

**Basic Rate Limiting:**
```python
from core.rate_limit_middleware import rate_limit

@rate_limit(limit=5, window=60)  # 5 commands per minute
@discord.app_commands.command()
async def place_bet(self, interaction, amount: int):
    # Rate limiting is automatic
    result = await self.betting_service.place_bet(interaction.user.id, amount)
    await interaction.response.send_message(f"Bet placed: {result.id}")
```

**Advanced Rate Limiting:**
```python
from core.rate_limit_middleware import rate_limit

@rate_limit(
    limit=3,           # 3 predictions per hour
    window=3600,       # 1 hour window
    per_user=True,     # Per user limit
    per_guild=True,    # Also per guild limit
    guild_limit=10,    # 10 predictions per guild per hour
    admin_bypass=True  # Admins can bypass
)
@discord.app_commands.command()
async def create_prediction(self, interaction, question: str):
    result = await self.prediction_service.create(question)
    await interaction.response.send_message(f"Created: {result.id}")
```

**Manual Rate Limiting:**
```python
from core.rate_limiter import RateLimiter

class BettingService:
    def __init__(self):
        self.rate_limiter = RateLimiter()
    
    async def place_bet(self, user_id: int, amount: int):
        # Check rate limit manually
        key = f"bet:{user_id}"
        if not await self.rate_limiter.check_rate_limit(key, limit=10, window=60):
            remaining_time = self.rate_limiter.get_remaining_time(key, 60)
            raise RateLimitExceededError(
                f"Rate limit exceeded. Try again in {remaining_time} seconds"
            )
        
        # Process the bet
        return await self.database.create_bet(user_id, amount)
```

**Custom Rate Limit Keys:**
```python
@rate_limit(
    limit=1,
    window=300,  # 5 minutes
    key_func=lambda interaction: f"expensive_op:{interaction.guild.id}"
)
@discord.app_commands.command()
async def expensive_operation(self, interaction):
    # Rate limited per guild, not per user
    result = await self.expensive_service.process()
    await interaction.response.send_message("Operation completed")
```

### 5️⃣ How It Connects to Other Components

- **Discord Commands**: Automatic rate limiting for all commands
- **Error Handling**: Rate limit errors are handled gracefully
- **Logging**: Rate limit violations are logged for monitoring
- **Security**: Prevents abuse and DoS attacks
- **Configuration**: Rate limits are configurable per environment

### 6️⃣ Common Mistakes to Avoid

❌ **Don't set limits too low:**
```python
# BAD - Too restrictive
@rate_limit(limit=1, window=3600)  # 1 per hour is too strict
```

✅ **Use reasonable limits:**
```python
# GOOD - Allows normal usage while preventing abuse
@rate_limit(limit=10, window=60)  # 10 per minute is reasonable
```

❌ **Don't ignore rate limit errors:**
```python
# BAD - No error handling
@rate_limit(limit=5, window=60)
async def command(self, interaction):
    # What happens when rate limited?
```

✅ **Handle rate limit gracefully:**
```python
# GOOD - Middleware handles this automatically
@rate_limit(limit=5, window=60)
async def command(self, interaction):
    # Rate limit errors are handled by middleware
```

❌ **Don't use the same limits for everything:**
```python
# BAD - Same limit for all commands
@rate_limit(limit=10, window=60)  # For both betting and viewing
```

✅ **Use appropriate limits per command:**
```python
# GOOD - Different limits for different operations
@rate_limit(limit=20, window=60)  # Higher limit for viewing
async def view_predictions(self, interaction): pass

@rate_limit(limit=5, window=60)   # Lower limit for betting
async def place_bet(self, interaction): pass
```

### 7️⃣ Testing and Verification

**Test Rate Limiting:**
```python
# Run rate limiter tests
python -m pytest tests/test_rate_limiter.py -v

# Test rate limiting manually
from core.rate_limiter import RateLimiter
import asyncio

rate_limiter = RateLimiter()

async def test_rate_limit():
    # Should allow first 5 requests
    for i in range(5):
        allowed = await rate_limiter.check_rate_limit("test_user", limit=5, window=60)
        print(f"Request {i+1}: {'Allowed' if allowed else 'Blocked'}")
    
    # 6th request should be blocked
    allowed = await rate_limiter.check_rate_limit("test_user", limit=5, window=60)
    print(f"Request 6: {'Allowed' if allowed else 'Blocked'}")

asyncio.run(test_rate_limit())
```

---

## Step 9: Security Enhancements

### 1️⃣ What I Built

A comprehensive security system with input sanitization, audit logging, secure token handling, data encryption, and threat monitoring.

**Key Files:**
- `core/security.py` - Main security components
- `core/security_middleware.py` - Discord integration
- `core/SECURITY_ENHANCEMENTS_SUMMARY.md` - Detailed documentation

### 2️⃣ Why It's Important

**Problems It Solves:**
- **Security Vulnerabilities**: Prevents XSS, SQL injection, and other attacks
- **Data Breaches**: Encrypts sensitive data and secures API tokens
- **Audit Requirements**: Comprehensive logging for compliance and debugging
- **Threat Detection**: Real-time monitoring for suspicious activity

### 3️⃣ Practical Advantages

- **Multi-Layer Protection**: Input sanitization, validation, and monitoring
- **Compliance Ready**: Audit logging meets regulatory requirements
- **Threat Detection**: Automatic detection of suspicious patterns
- **Data Protection**: Encryption for sensitive information
- **Token Security**: Secure handling of API keys and tokens

### 4️⃣ How to Use It Daily

**Secure Discord Commands:**
```python
from core.security_middleware import secure_prediction_command, secure_betting_command

@secure_prediction_command(
    audit_event_type=AuditEventType.PREDICTION_CREATED,
    security_level=SecurityLevel.HIGH
)
@discord.app_commands.command()
async def create_prediction(self, interaction, question: str, option1: str, option2: str):
    # Input is automatically sanitized
    # Audit event is automatically logged
    # Security monitoring is active
    
    result = await self.prediction_service.create(question, [option1, option2])
    await interaction.response.send_message(f"Created: {result.id}")

@secure_betting_command(sensitive_params=['amount'])
@discord.app_commands.command()
async def place_bet(self, interaction, prediction_id: str, amount: int):
    # Amount is treated as sensitive data in logs
    result = await self.betting_service.place_bet(interaction.user.id, prediction_id, amount)
    await interaction.response.send_message(f"Bet placed: {result.id}")
```

**Manual Input Sanitization:**
```python
from core.security import sanitize_user_input, InputSanitizer

# Quick sanitization
clean_input = sanitize_user_input(user_input, max_length=500)

# Advanced sanitization
sanitizer = InputSanitizer()
try:
    clean_input = sanitizer.sanitize_text(user_input, strict_mode=True)
except SecurityError as e:
    # Malicious input detected
    logger.warning(f"Security violation: {e}")
    raise
```

**Audit Logging:**
```python
from core.security import audit_user_action, AuditEventType, SecurityLevel

# Log user actions
audit_user_action(
    event_type=AuditEventType.BET_PLACED,
    user_id=interaction.user.id,
    guild_id=interaction.guild.id,
    details={
        "prediction_id": prediction_id,
        "amount": amount,
        "option": selected_option
    },
    security_level=SecurityLevel.HIGH
)
```

**Data Encryption:**
```python
from core.security import encrypt_sensitive_data, decrypt_sensitive_data

# Encrypt sensitive data before storage
sensitive_data = {
    "user_id": 123456789,
    "api_key": "secret_key_12345",
    "personal_info": "sensitive information"
}

encrypted_data = encrypt_sensitive_data(sensitive_data)
# Store encrypted_data in database

# Decrypt when needed
decrypted_data = decrypt_sensitive_data(encrypted_data)
```

**Token Management:**
```python
from core.security import get_token_manager

token_manager = get_token_manager()

# Generate secure tokens
api_token = token_manager.generate_secure_token()

# Encrypt tokens for storage
encrypted_token = token_manager.encrypt_token(api_token)

# Decrypt for use
decrypted_token = token_manager.decrypt_token(encrypted_token)
```

### 5️⃣ How It Connects to Other Components

- **Validation Framework**: Enhanced with security-focused input sanitization
- **Error Handling**: Security errors are handled with appropriate responses
- **Logging System**: Security events are logged with full context
- **Rate Limiting**: Security monitoring detects rate limit abuse
- **Discord Commands**: All commands can be secured with middleware

### 6️⃣ Common Mistakes to Avoid

❌ **Don't trust any user input:**
```python
# BAD - No sanitization
async def create_prediction(question: str):
    # What if question contains <script> tags?
    await self.database.create(question)
```

✅ **Always sanitize input:**
```python
# GOOD
@secure_prediction_command()
async def create_prediction(question: str):
    # Input is automatically sanitized
    await self.database.create(question)
```

❌ **Don't store sensitive data in plain text:**
```python
# BAD
user_data = {"api_key": "secret123", "password": "mypass"}
await self.database.store(user_data)
```

✅ **Encrypt sensitive data:**
```python
# GOOD
encrypted_data = encrypt_sensitive_data(user_data)
await self.database.store(encrypted_data)
```

❌ **Don't ignore security events:**
```python
# BAD - No audit logging
async def admin_action():
    # Critical action with no logging
    await self.database.delete_all_predictions()
```

✅ **Log security-relevant events:**
```python
# GOOD
@secure_admin_command()
async def admin_action():
    # Automatically logged with high security level
    await self.database.delete_all_predictions()
```

### 7️⃣ Testing and Verification

**Test Security Components:**
```python
# Run security tests
python -m pytest tests/test_security.py -v

# Test input sanitization
from core.security import InputSanitizer

sanitizer = InputSanitizer()

# Test malicious input
malicious_input = "<script>alert('xss')</script>Hello"
sanitized = sanitizer.sanitize_text(malicious_input)
print(f"Original: {malicious_input}")
print(f"Sanitized: {sanitized}")  # Should be just "Hello"

# Test SQL injection
sql_injection = "'; DROP TABLE users; --"
try:
    sanitized = sanitizer.sanitize_text(sql_injection, strict_mode=True)
except SecurityError as e:
    print(f"Security violation detected: {e}")
```

---

## How All Components Work Together

### The Complete Flow

1. **Configuration** loads all settings and validates environment
2. **DI Container** creates and manages all service instances
3. **Discord Command** receives user input
4. **Rate Limiting** checks if user can execute command
5. **Security Middleware** sanitizes input and starts audit logging
6. **Validation Framework** validates business rules
7. **Pydantic Models** ensure data structure correctness
8. **Service Layer** processes the business logic
9. **Error Handler** catches any issues and provides user feedback
10. **Logging System** records everything with correlation IDs

### Example Complete Command Flow

```python
@secure_betting_command(
    audit_event_type=AuditEventType.BET_PLACED,
    security_level=SecurityLevel.HIGH,
    sensitive_params=['amount']
)
@rate_limit(limit=5, window=60)
@validate_inputs(
    prediction_id=Validator.validate_prediction_id,
    amount=lambda x: Validator.validate_bet_amount(x, min_amount=1)
)
@discord.app_commands.command()
async def place_bet(self, interaction, prediction_id: str, amount: int):
    """Complete secure betting command with all protections."""
    try:
        # 1. Rate limiting already checked (middleware)
        # 2. Input sanitized and validated (middleware)
        # 3. Audit logging started (middleware)
        
        # 4. Create validated request model
        request = PlaceBetRequest(
            user_id=interaction.user.id,
            prediction_id=prediction_id,
            amount=amount,
            guild_id=interaction.guild.id
        )
        
        # 5. Process through service layer
        result = await self.betting_service.place_bet(request)
        
        # 6. Return success response
        await interaction.response.send_message(
            f"✅ Bet placed! ID: {result.bet_id}"
        )
        
    except Exception as e:
        # 7. Error handler manages the response
        await self.error_handler.handle_discord_error(interaction, e)
```

This comprehensive system provides enterprise-grade security, reliability, and maintainability for your Discord prediction bot. Each component builds on the others to create a robust, secure, and user-friendly application.