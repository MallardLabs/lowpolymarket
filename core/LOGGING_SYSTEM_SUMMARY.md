# Structured Logging System Implementation

## Overview

This document summarizes the comprehensive structured logging system implemented for the Discord Prediction Market Bot. The system provides JSON-formatted logging, correlation ID tracking, automatic function logging, and performance monitoring.

## Components Implemented

### 1. Core Logging Manager (`core/logging_manager.py`)

**LoggingManager Class**
- Centralized logging configuration and management
- Support for both console and file logging
- Automatic log rotation with configurable size limits
- JSON and human-readable formatting options

**Key Features:**
- **Correlation ID Management**: Automatic generation and tracking of correlation IDs across function calls
- **Contextual Logging**: Rich context information including user IDs, guild IDs, operation names
- **Thread-Safe**: Uses context variables for correlation ID tracking across async operations

### 2. JSON Formatter (`JSONFormatter`)

**Features:**
- Structured JSON output for all log entries
- Automatic timestamp formatting (ISO 8601)
- Exception information with stack traces
- Extra field inclusion for contextual data
- JSON-serializable value handling

**Example Output:**
```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "level": "INFO",
  "logger": "prediction_service",
  "message": "Bet placed successfully",
  "module": "prediction_service",
  "function": "place_bet",
  "line": 45,
  "correlation_id": "bet-12345-67890",
  "extra": {
    "user_id": 12345,
    "guild_id": 67890,
    "prediction_id": "pred-123",
    "amount": 100,
    "option": "Yes"
  }
}
```

### 3. Contextual Formatter (`ContextualFormatter`)

**Features:**
- Human-readable log format for console output
- Correlation ID display
- Contextual information in brackets
- Color support (when enabled)

**Example Output:**
```
[2024-01-15 10:30:45] [INFO    ] [bet-12345-67890] prediction_service:place_bet:45 - Bet placed successfully [user:12345:guild:67890:pred:pred-123]
```

### 4. Function Decorators

#### `@log_function_call`
**Purpose:** Automatic logging of function entry/exit with timing

**Features:**
- Function argument logging (sanitized for JSON)
- Return value logging
- Execution duration tracking
- Exception logging with context
- Support for both sync and async functions

**Usage:**
```python
@log_function_call(include_args=True, include_result=True, include_duration=True)
async def place_bet(prediction_id: str, user_id: int, amount: int):
    # Function implementation
    return result
```

#### `@log_performance`
**Purpose:** Performance monitoring with configurable thresholds

**Features:**
- Configurable performance thresholds
- Automatic slow function detection
- Duration tracking and reporting
- Support for both sync and async functions

**Usage:**
```python
@log_performance(threshold_seconds=1.0)
async def complex_calculation():
    # Function implementation
    return result
```

### 5. Configuration Integration

**Enhanced LoggingSettings:**
- JSON format configuration
- Correlation ID settings
- Performance monitoring options
- Log rotation configuration
- Structured logging options

**New Configuration Options:**
```python
# Structured logging
json_format: bool = Field(False, description="Use JSON format for logs")
include_extra_fields: bool = Field(True, description="Include extra fields in logs")

# Correlation ID settings
auto_correlation_id: bool = Field(True, description="Automatically generate correlation IDs")
correlation_id_header: str = Field("X-Correlation-ID", description="HTTP header for correlation ID")

# Performance logging
log_slow_queries: bool = Field(True, description="Log slow database queries")
slow_query_threshold: float = Field(1.0, description="Threshold in seconds for slow query logging")
log_function_calls: bool = Field(False, description="Log function entry/exit (debug mode)")
```

## Usage Examples

### 1. Basic Logging with Context

```python
from core.logging_manager import get_logger, set_correlation_id, LogContext

logger = get_logger(__name__)

# Set correlation ID for operation tracking
correlation_id = set_correlation_id("user-operation-123")

# Log with rich context
context = LogContext(
    user_id=12345,
    guild_id=67890,
    prediction_id="pred-456",
    operation="place_bet"
)

logging_manager.log_with_context(
    logger,
    logger.info,
    "Processing bet placement",
    context,
    amount=100,
    option="Yes"
)
```

### 2. Discord Command Integration

```python
@commands.slash_command()
@log_function_call(include_args=True, include_duration=True)
async def create_prediction(ctx, question: str, option1: str, option2: str):
    # Set correlation ID for this command
    correlation_id = set_correlation_id(f"cmd-{ctx.user.id}-{ctx.guild.id}")
    
    logger.info("Creating prediction", extra={
        'user_id': ctx.user.id,
        'guild_id': ctx.guild.id,
        'question': question,
        'options': [option1, option2]
    })
    
    # Command implementation...
```

### 3. Performance Monitoring

```python
@log_performance(threshold_seconds=2.0)
async def complex_amm_calculation(prediction_id: str, bet_amount: int):
    # Complex calculation that might be slow
    await asyncio.sleep(1.5)  # Simulated work
    return calculation_result
```

## File Structure

```
core/
├── logging_manager.py          # Main logging system implementation
├── LOGGING_SYSTEM_SUMMARY.md   # This documentation

examples/
├── logging_usage.py            # Basic usage examples
├── bot_integration_example.py  # Discord bot integration example

tests/
├── test_logging_manager.py     # Comprehensive test suite

config/
├── settings.py                 # Enhanced with logging configuration
```

## Benefits

### 1. **Observability**
- Complete request tracing with correlation IDs
- Rich contextual information in all log entries
- Performance monitoring and alerting capabilities

### 2. **Debugging**
- Automatic function entry/exit logging
- Exception tracking with full context
- Correlation ID tracking across async operations

### 3. **Production Readiness**
- JSON structured logs for log aggregation systems
- Log rotation and file management
- Configurable log levels and formats

### 4. **Performance Monitoring**
- Automatic detection of slow operations
- Configurable performance thresholds
- Duration tracking for all operations

## Integration with Existing Systems

### Bot Integration
The logging system integrates seamlessly with the existing Discord bot:

```python
# In bot.py
from core.logging_manager import get_logging_manager, get_logger

# Initialize logging
logging_manager = get_logging_manager(settings.logging)
logger = get_logger("discord_bot")
```

### Cog Integration
Discord cogs can use the logging system for command tracking:

```python
class PredictionCog(commands.Cog):
    def __init__(self, bot):
        self.logger = get_logger(__name__)
    
    @commands.slash_command()
    @log_function_call(include_args=True)
    async def my_command(self, ctx):
        # Command implementation with automatic logging
        pass
```

## Testing

The system includes comprehensive tests covering:
- JSON formatter functionality
- Correlation ID management
- Function decorators (sync and async)
- Performance monitoring
- Concurrent logging scenarios
- Log rotation and file management

**Test Coverage:**
- Unit tests for all components
- Integration tests for real-world scenarios
- Performance tests for high-load situations
- Concurrent logging tests for thread safety

## Configuration Examples

### Development Configuration
```python
LOG_LEVEL=DEBUG
LOG_JSON_FORMAT=false
LOG_CONSOLE_ENABLED=true
LOG_FILE_ENABLED=true
LOG_FILE_PATH=logs/dev.log
```

### Production Configuration
```python
LOG_LEVEL=INFO
LOG_JSON_FORMAT=true
LOG_CONSOLE_ENABLED=false
LOG_FILE_ENABLED=true
LOG_FILE_PATH=/var/log/bot/production.log
LOG_FILE_MAX_BYTES=50000000
LOG_FILE_BACKUP_COUNT=10
```

## Future Enhancements

The logging system is designed to be extensible and can support:

1. **External Log Aggregation**: Integration with ELK stack, Splunk, or cloud logging services
2. **Metrics Export**: Integration with Prometheus or other metrics systems
3. **Alerting**: Integration with alerting systems for error rate monitoring
4. **Distributed Tracing**: OpenTelemetry integration for microservices
5. **Log Sampling**: Configurable log sampling for high-volume scenarios

## Requirements Satisfied

This implementation satisfies the following requirements from the task:

✅ **Configure structured logging with JSON format**
- Complete JSON formatter with structured output
- Configurable JSON vs. human-readable formats

✅ **Implement log rotation and file management**
- Automatic log rotation based on file size
- Configurable backup file retention
- Directory creation and management

✅ **Add contextual logging with correlation IDs**
- Automatic correlation ID generation and tracking
- Context variables for async operation tracking
- Rich contextual information in all log entries

✅ **Create logging decorators for automatic function entry/exit logging**
- `@log_function_call` decorator with full feature set
- `@log_performance` decorator for performance monitoring
- Support for both synchronous and asynchronous functions
- Argument and return value logging with sanitization

The structured logging system is now fully implemented and ready for production use, providing comprehensive observability and debugging capabilities for the Discord Prediction Market Bot.