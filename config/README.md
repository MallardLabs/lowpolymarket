# Configuration System

This directory contains the centralized configuration management system for the Discord Prediction Market Bot. The system uses Pydantic BaseSettings for type-safe configuration loading with validation and support for different environments.

## Features

- **Type-safe configuration** with Pydantic validation
- **Environment-specific settings** (development, staging, production)
- **Comprehensive validation** with helpful error messages
- **Hierarchical configuration** organized by component
- **Environment variable support** with prefixes
- **Configuration validation utilities**

## Configuration Structure

The configuration is organized into logical sections:

- **DiscordSettings**: Discord bot configuration
- **DatabaseSettings**: Database and Supabase configuration
- **CacheSettings**: Caching configuration (Redis/Memory)
- **BusinessLogicSettings**: Business rules and limits
- **RateLimitSettings**: Rate limiting configuration
- **DripApiSettings**: DRIP API integration settings
- **LoggingSettings**: Logging configuration

## Environment Files

The system supports multiple environment files:

- `.env` - Base configuration
- `.env.development` - Development overrides
- `.env.staging` - Staging overrides  
- `.env.production` - Production overrides
- `.env.local` - Local overrides (not committed)

## Usage

### Basic Usage

```python
from config import get_settings

# Get validated settings
settings = get_settings()

# Access configuration sections
print(f"Environment: {settings.environment}")
print(f"Max bet amount: {settings.business.max_bet_amount}")
print(f"Cache TTL: {settings.cache.default_ttl}")
```

### Validation

```python
from config import validate_configuration, ConfigurationError

try:
    settings = validate_configuration()
    print("✅ Configuration is valid")
except ConfigurationError as e:
    print(f"❌ Configuration error: {e}")
```

### Configuration Summary

```python
from config import print_configuration_summary

settings = get_settings()
print_configuration_summary(settings)
```

## Environment Variables

### Required Variables

```bash
# Discord Configuration
DISCORD_TOKEN=your_discord_bot_token

# Database Configuration  
DATABASE_URL=postgresql://postgres.ref:pass@aws-0-us-east-2.pooler.supabase.com:6543/postgres
DATABASE_SUPABASE_URL=https://your-project.supabase.co
DATABASE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_your_key_here
DATABASE_SUPABASE_SECRET_KEY=sb_secret_your_key_here

# DRIP API Configuration
API_API_KEY=your_drip_api_key
API_REALM_ID=your_drip_realm_id
```

### Optional Variables

```bash
# Environment
ENVIRONMENT=development  # development, staging, production
DEBUG=false

# Cache Configuration
CACHE_REDIS_URL=redis://localhost:6379
CACHE_DEFAULT_TTL=300

# Business Logic
BUSINESS_MAX_BET_AMOUNT=1000000
BUSINESS_MIN_RESOLUTION_VOTES=2

# Rate Limiting
RATE_LIMIT_USER_REQUESTS_PER_MINUTE=10
RATE_LIMIT_USER_BETS_PER_MINUTE=5

# Logging
LOG_LEVEL=INFO
LOG_FILE_PATH=logs/discord.log
```

## Validation Script

Use the validation script to check your configuration:

```bash
# Basic validation
python scripts/validate_config.py

# Check for missing environment variables
python scripts/validate_config.py --check-env-vars

# Validate specific environment
python scripts/validate_config.py --environment production

# Show detailed configuration summary
python scripts/validate_config.py --show-summary
```

## Environment-Specific Configuration

### Development
- Debug mode enabled
- Lenient rate limits
- Console logging with colors
- Memory-only caching

### Staging  
- Production-like settings
- JSON logging
- Moderate rate limits
- Optional Redis caching

### Production
- Debug mode disabled
- Strict rate limits
- JSON logging with rotation
- Redis caching required
- Enhanced security validation

## Adding New Configuration

1. **Add to appropriate settings class**:
```python
class BusinessLogicSettings(BaseSettings):
    new_setting: int = Field(100, description="Description of new setting")
    
    model_config = SettingsConfigDict(env_prefix="BUSINESS_")
```

2. **Add environment variable**:
```bash
BUSINESS_NEW_SETTING=200
```

3. **Add validation if needed**:
```python
@field_validator('new_setting')
@classmethod
def validate_new_setting(cls, v):
    if v <= 0:
        raise ValueError("New setting must be positive")
    return v
```

4. **Update documentation and examples**

## Error Handling

The configuration system provides detailed error messages:

```
❌ Configuration validation failed:
  • discord -> token: Discord token must be provided and be at least 50 characters long
    Hint: Set DISCORD_TOKEN in your .env file
  • database -> url: Database URL must be a valid PostgreSQL connection string
    Hint: Set DATABASE_URL with a valid PostgreSQL connection string
```

## Best Practices

1. **Use environment-specific files** for different deployment environments
2. **Validate configuration early** in application startup
3. **Use type hints** for all configuration fields
4. **Provide helpful descriptions** for all fields
5. **Add validation** for critical settings
6. **Keep sensitive data** in environment variables, not code
7. **Use the validation script** in CI/CD pipelines

## Testing

The configuration system includes comprehensive tests:

```bash
# Run configuration tests
python test_config.py

# Test specific environment
ENVIRONMENT=production python test_config.py
```

## Troubleshooting

### Common Issues

1. **Missing environment variables**: Use `--check-env-vars` flag
2. **Invalid values**: Check validation error messages
3. **Environment file not loaded**: Ensure file exists and is readable
4. **Prefix mismatches**: Check environment variable names match prefixes

### Debug Mode

Enable debug mode for detailed configuration loading:

```bash
DEBUG=true python scripts/validate_config.py --show-summary
```

This will show exactly which configuration files are loaded and which environment variables are used.