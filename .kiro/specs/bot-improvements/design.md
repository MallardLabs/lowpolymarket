# Design Document

## Overview

This design document outlines the comprehensive modernization of the Discord Prediction Market Bot, transforming it from a basic implementation into a production-ready, enterprise-grade system. The design focuses on clean architecture, performance optimization, reliability, and scalability while maintaining all existing functionality.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Discord Bot Layer                        │
├─────────────────────────────────────────────────────────────────┤
│                     Presentation Layer                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Discord Cogs  │  │  Error Handler  │  │  Rate Limiter   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                      Service Layer                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Prediction Svc  │  │  Betting Svc    │  │  Points Svc     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                     Domain Layer                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Prediction    │  │      Bet        │  │     Market      │ │
│  │     Model       │  │     Model       │  │     Model       │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                   Infrastructure Layer                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Repository    │  │     Cache       │  │   Event Bus     │ │
│  │    Pattern      │  │    Manager      │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                      Data Layer                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │    Supabase     │  │      Redis      │  │   External      │ │
│  │   PostgreSQL    │  │     Cache       │  │   APIs (DRIP)   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Dependency Injection Container

```python
# Core container managing all dependencies
class DIContainer:
    - DatabaseManager
    - CacheManager
    - EventBus
    - ConfigurationManager
    - LoggingManager
    - HealthMonitor
    - RateLimiter
```

## Components and Interfaces

### 1. Configuration Management

**ConfigurationManager**
- Loads settings from environment variables and files
- Validates configuration on startup
- Provides type-safe access to settings
- Supports different environments (dev, staging, prod)

```python
class Settings(BaseSettings):
    # Discord Configuration
    discord_token: str
    
    # Database Configuration
    database_url: str
    supabase_url: str
    supabase_anon_key: str
    
    # Performance Settings
    max_concurrent_bets: int = 50
    cache_ttl: int = 300
    connection_pool_size: int = 20
    
    # Business Logic
    max_bet_amount: int = 1_000_000
    auto_refund_hours: int = 120
    min_resolution_votes: int = 2
    
    # Rate Limiting
    rate_limit_requests: int = 10
    rate_limit_window: int = 60
```

### 2. Error Handling System

**ErrorHandler**
- Custom exception hierarchy for different error types
- Retry logic with exponential backoff
- Circuit breaker pattern for external services
- User-friendly error messages for Discord interactions
- Comprehensive error logging with unique IDs

```python
class PredictionMarketError(Exception):
    - error_code: str
    - details: dict
    - user_message: str

class ErrorHandler:
    - handle_discord_interaction_error()
    - handle_database_error()
    - handle_external_api_error()
    - log_error_with_id()
```

### 3. Performance Optimization

**CacheManager**
- LRU cache with TTL support
- Distributed caching with Redis
- Cache warming strategies
- Intelligent cache invalidation

```python
class CacheManager:
    - get(key: str) -> Optional[Any]
    - set(key: str, value: Any, ttl: int)
    - invalidate(key: str)
    - clear_pattern(pattern: str)
    - get_stats() -> CacheStats
```

**QueryOptimizer**
- Optimized database queries
- Batch operations
- Connection pooling
- Query performance monitoring

```python
class QueryOptimizer:
    - get_prediction_with_stats()
    - get_user_portfolio()
    - batch_update_liquidity()
    - monitor_query_performance()
```

### 4. Service Layer

**PredictionService**
- Business logic for prediction management
- Validation and error handling
- Event publishing for real-time updates

```python
class PredictionService:
    - create_prediction() -> Result[str, str]
    - get_active_predictions() -> Result[List[Prediction], str]
    - resolve_prediction() -> Result[bool, str]
    - validate_prediction_data()
```

**BettingService**
- Bet placement with atomic operations
- AMM calculations and pricing
- Balance validation and point management

```python
class BettingService:
    - place_bet() -> Result[bool, str]
    - calculate_shares() -> float
    - get_current_prices() -> Dict[str, PriceInfo]
    - validate_bet_request()
```

### 5. Repository Pattern

**PredictionRepository**
- Abstract data access layer
- Database operation encapsulation
- Error handling and retry logic

```python
class PredictionRepository(ABC):
    - find_by_id() -> Optional[Prediction]
    - find_active_by_guild() -> List[Prediction]
    - save() -> bool
    - delete() -> bool
```

### 6. Event-Driven Architecture

**EventBus**
- Publish/subscribe pattern for real-time updates
- Async event processing
- Event persistence and replay

```python
class EventBus:
    - publish(event: Event)
    - subscribe(event_type: Type, handler: Callable)
    - unsubscribe(event_type: Type, handler: Callable)
```

**Events**
```python
@dataclass
class BetPlacedEvent(Event):
    prediction_id: str
    user_id: int
    option: str
    amount: int
    timestamp: float

@dataclass
class PredictionResolvedEvent(Event):
    prediction_id: str
    winning_option: str
    resolved_by: int
    timestamp: float
```

## Data Models

### Enhanced Domain Models

**Prediction Model**
```python
@dataclass(frozen=True)
class Prediction:
    id: str
    guild_id: int
    question: str
    options: List[str]
    creator_id: int
    end_time: datetime
    category: Optional[str]
    status: PredictionStatus
    initial_liquidity: int
    k_constant: int
    
    # Business methods
    def is_active() -> bool
    def can_place_bet() -> bool
    def calculate_shares() -> float
    def get_current_odds() -> Dict[str, float]
```

**Bet Model**
```python
@dataclass(frozen=True)
class Bet:
    id: str
    prediction_id: str
    user_id: int
    guild_id: int
    option: str
    amount: int
    shares: float
    price_per_share: float
    created_at: datetime
```

**Market State**
```python
@dataclass(frozen=True)
class MarketState:
    prediction_id: str
    liquidity_pools: Dict[str, int]
    total_volume: int
    unique_bettors: int
    current_odds: Dict[str, float]
    last_updated: datetime
```

### Validation Models

**Request Models with Pydantic**
```python
class CreatePredictionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    options: List[str] = Field(..., min_items=2, max_items=10)
    duration_minutes: int = Field(..., gt=0, le=43200)
    category: Optional[str] = Field(None, max_length=50)

class PlaceBetRequest(BaseModel):
    prediction_id: str
    option: str
    amount: int = Field(..., gt=0, le=1_000_000)
```

## Error Handling

### Exception Hierarchy

```python
PredictionMarketError
├── ValidationError
├── InsufficientBalanceError
├── PredictionNotFoundError
├── PredictionClosedError
├── DatabaseError
├── ExternalAPIError
├── RateLimitExceededError
└── ConfigurationError
```

### Error Response Format

```python
@dataclass
class ErrorResponse:
    error_code: str
    message: str
    details: Optional[Dict]
    error_id: str
    timestamp: datetime
```

### Retry Strategy

```python
@retry_with_backoff(max_retries=3, base_delay=1.0)
async def database_operation():
    # Database operations with automatic retry
    pass
```

### Circuit Breaker

```python
class CircuitBreaker:
    - failure_threshold: int = 5
    - timeout: float = 60.0
    - state: CircuitBreakerState
    
    async def call(func, *args, **kwargs)
    def _on_success()
    def _on_failure()
```

## Testing Strategy

### Test Architecture

```
tests/
├── unit/
│   ├── test_prediction_service.py
│   ├── test_betting_service.py
│   ├── test_validation.py
│   └── test_amm_calculations.py
├── integration/
│   ├── test_prediction_flow.py
│   ├── test_database_operations.py
│   └── test_discord_interactions.py
├── performance/
│   ├── test_concurrent_betting.py
│   ├── test_cache_performance.py
│   └── test_database_load.py
├── fixtures/
│   ├── mock_discord.py
│   ├── mock_database.py
│   └── test_factories.py
└── conftest.py
```

### Test Coverage Requirements

- **Unit Tests**: 90%+ coverage for business logic
- **Integration Tests**: All major user flows
- **Performance Tests**: Load testing for 1000+ concurrent users
- **Property-Based Tests**: Input validation edge cases

### Mock Framework

```python
@pytest.fixture
async def mock_database():
    db = AsyncMock()
    db.get_prediction_by_id.return_value = test_prediction_data
    return db

@pytest.fixture
async def prediction_service(mock_database, mock_points_manager):
    return PredictionService(mock_database, mock_points_manager, mock_event_bus)
```

## Performance Considerations

### Caching Strategy

**Multi-Level Caching**
1. **L1 Cache**: In-memory LRU cache (5-second TTL)
2. **L2 Cache**: Redis distributed cache (5-minute TTL)
3. **L3 Cache**: Database query result cache (1-hour TTL)

**Cache Keys**
```python
# Prediction data
prediction:{prediction_id}
predictions:guild:{guild_id}:active
predictions:guild:{guild_id}:all

# Market data
market:{prediction_id}:prices
market:{prediction_id}:liquidity
market:{prediction_id}:stats

# User data
user:{user_id}:balance
user:{user_id}:bets:{guild_id}
```

### Database Optimization

**Connection Pooling**
- Min connections: 5
- Max connections: 20
- Connection timeout: 30 seconds
- Query timeout: 30 seconds

**Query Optimization**
- Single queries instead of N+1 problems
- Proper indexing on frequently queried columns
- Materialized views for complex aggregations
- Read replicas for query distribution

**Batch Operations**
- Batch size: 100 operations
- Flush interval: 5 seconds
- Automatic batching for high-frequency operations

### Memory Management

**Weak References**
- Use weak references for cached objects
- Automatic garbage collection of unused data
- Memory usage monitoring and alerts

**Resource Cleanup**
- Automatic cleanup of expired cache entries
- Connection pool management
- Task cancellation on shutdown

## Security Measures

### Input Validation

**Sanitization**
- HTML/SQL injection prevention
- Input length limits
- Character set validation
- Type checking and conversion

**Rate Limiting**
```python
# Per user limits
user_rate_limit: 10 requests/minute
bet_rate_limit: 5 bets/minute

# Per guild limits
guild_rate_limit: 100 requests/minute
creation_rate_limit: 10 predictions/hour
```

### Audit Logging

**Logged Events**
- All bet placements
- Prediction creations and resolutions
- Administrative actions
- Error occurrences
- Rate limit violations

**Log Format**
```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "event_type": "bet_placed",
  "user_id": 123456789,
  "guild_id": 987654321,
  "prediction_id": "pred-123",
  "amount": 100,
  "option": "Yes",
  "ip_address": "192.168.1.1",
  "user_agent": "Discord Bot"
}
```

### Data Encryption

**At Rest**
- Database encryption for sensitive data
- Encrypted configuration files
- Secure key management

**In Transit**
- TLS 1.3 for all external communications
- Encrypted internal service communication
- Certificate management and rotation

## Monitoring and Observability

### Health Checks

**Endpoints**
```python
/health/live     # Liveness probe
/health/ready    # Readiness probe
/health/database # Database connectivity
/health/cache    # Cache connectivity
/health/external # External API status
```

**Health Check Response**
```json
{
  "status": "healthy",
  "checks": [
    {
      "name": "database",
      "status": "healthy",
      "response_time": 0.025,
      "details": {}
    }
  ],
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Metrics Collection

**System Metrics**
- CPU usage
- Memory usage
- Disk I/O
- Network I/O

**Application Metrics**
- Request rate
- Response time
- Error rate
- Cache hit rate
- Database query time
- Active connections

**Business Metrics**
- Predictions created per hour
- Bets placed per hour
- Total volume traded
- Active users
- Market resolution time

### Logging Strategy

**Log Levels**
- DEBUG: Detailed debugging information
- INFO: General operational messages
- WARNING: Warning conditions
- ERROR: Error conditions
- CRITICAL: Critical error conditions

**Structured Logging**
```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "logger": "prediction_service",
  "message": "Prediction created successfully",
  "prediction_id": "pred-123",
  "user_id": 123456789,
  "guild_id": 987654321,
  "duration": 0.125
}
```

### Alerting

**Alert Conditions**
- Error rate > 1%
- Response time > 1 second
- Database connection failures
- Cache miss rate > 50%
- Memory usage > 80%
- Disk usage > 90%

**Alert Channels**
- Email notifications
- Slack integration
- Discord webhook
- PagerDuty integration

This design provides a comprehensive foundation for transforming the prediction market bot into a production-ready, scalable system while maintaining all existing functionality and improving user experience significantly.