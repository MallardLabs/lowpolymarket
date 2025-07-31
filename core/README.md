# Dependency Injection Container

This module provides a comprehensive Dependency Injection (DI) container for the Discord Prediction Market Bot, enabling clean architecture, better testability, and improved maintainability.

## Features

- **Service Registration**: Register services with different lifecycles (singleton, transient, scoped)
- **Automatic Dependency Resolution**: Automatically inject dependencies based on constructor parameters
- **Factory Methods**: Support for complex object creation through factory functions
- **Async Support**: Full support for async initialization and disposal
- **Circular Dependency Detection**: Prevents infinite loops during service resolution
- **Service Scopes**: Support for scoped services (e.g., per-request instances)
- **Type Safety**: Full type hints and generic support

## Service Lifecycles

### Singleton
- **Description**: Single instance for the entire application
- **Use Case**: Database connections, configuration, shared services
- **Example**: Configuration settings, database managers

### Transient
- **Description**: New instance created every time the service is requested
- **Use Case**: Stateless services, temporary objects
- **Example**: Validation services, calculators

### Scoped
- **Description**: Single instance per scope (e.g., per Discord interaction)
- **Use Case**: Request-specific services, user sessions
- **Example**: User context, request handlers

## Basic Usage

### 1. Setting Up the Container

```python
from core.container import DIContainer

# Create container
container = DIContainer()

# Register services
container.register_singleton(DatabaseManager)
container.register_transient(ValidationService)
container.register_scoped(UserContext)
```

### 2. Service Registration

```python
# Register with interface and implementation
container.register_singleton(IUserService, UserService)

# Register with factory function
def create_database_manager(settings: Settings) -> DatabaseManager:
    return DatabaseManager(settings.database.url)

container.register_factory(DatabaseManager, create_database_manager)

# Register existing instance
config = Settings()
container.register_instance(Settings, config)
```

### 3. Service Resolution

```python
# Resolve service
user_service = await container.get_service(IUserService)

# Use the service
result = await user_service.get_user(user_id)
```

### 4. Dependency Injection

```python
class PredictionService:
    def __init__(self, database: DatabaseManager, validator: ValidationService):
        self.database = database
        self.validator = validator
    
    async def create_prediction(self, data: dict) -> str:
        # Dependencies are automatically injected
        if not self.validator.validate_prediction(data):
            raise ValueError("Invalid prediction data")
        
        return await self.database.create_prediction(data)

# Register the service
container.register_singleton(PredictionService)

# Dependencies are automatically resolved
service = await container.get_service(PredictionService)
```

## Advanced Usage

### Service Scopes

```python
# Create a scope
scope = container.create_scope()

# Execute within scope
async def handle_request():
    user_context = await container.get_service(UserContext)
    # Same instance within this scope
    same_context = await container.get_service(UserContext)
    assert user_context is same_context

await container.execute_scoped(scope, handle_request)

# Clean up scope
await scope.dispose_async()
```

### Factory Functions with Dependencies

```python
def create_prediction_service(
    database: DatabaseManager,
    points_manager: PointsManager,
    settings: Settings
) -> PredictionService:
    return PredictionService(database, points_manager, settings.business)

container.register_factory(PredictionService, create_prediction_service)
```

### Async Initialization

```python
class AsyncService:
    def __init__(self):
        self.initialized = False
    
    async def initialize_async(self):
        # Perform async initialization
        self.initialized = True
    
    async def dispose_async(self):
        # Perform async cleanup
        pass

container.register_singleton(AsyncService)

# Service will be automatically initialized
service = await container.get_service(AsyncService)
assert service.initialized
```

## Integration with Discord Bot

### 1. Bot Setup

```python
from core.container import DIContainer, get_container

def setup_di_container() -> DIContainer:
    container = DIContainer()
    settings = get_settings()
    
    # Register configuration
    container.register_instance(Settings, settings)
    
    # Register infrastructure
    container.register_singleton(SupabaseManager)
    container.register_singleton(PointsManager)
    
    # Register business services
    container.register_singleton(PredictionService)
    container.register_singleton(BettingService)
    
    return container

# Set global container
container = setup_di_container()
set_container(container)
```

### 2. Enhanced Discord Cog

```python
class PredictionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.prediction_service: PredictionService = None
    
    async def cog_load(self):
        container = get_container()
        self.prediction_service = await container.get_service(PredictionService)
    
    @app_commands.command()
    async def create_prediction(self, interaction: discord.Interaction, ...):
        # Use injected service
        prediction_id = await self.prediction_service.create_prediction(...)
```

## Error Handling

The DI container provides comprehensive error handling:

```python
from core.exceptions import (
    ServiceNotFoundError,
    ServiceRegistrationError,
    CircularDependencyError
)

try:
    service = await container.get_service(UnregisteredService)
except ServiceNotFoundError as e:
    print(f"Service not found: {e.service_name}")

try:
    container.register_singleton(ExistingService)
except ServiceRegistrationError as e:
    print(f"Registration failed: {e}")

# Circular dependencies are automatically detected
try:
    service = await container.get_service(CircularServiceA)
except CircularDependencyError as e:
    print(f"Circular dependency: {' -> '.join(e.dependency_chain)}")
```

## Testing

The DI container makes testing much easier:

```python
import pytest
from unittest.mock import Mock

@pytest.fixture
def test_container():
    container = DIContainer()
    
    # Register mocks for testing
    mock_database = Mock()
    container.register_instance(DatabaseManager, mock_database)
    
    # Register real services
    container.register_singleton(PredictionService)
    
    return container

@pytest.mark.asyncio
async def test_prediction_service(test_container):
    service = await test_container.get_service(PredictionService)
    
    # Test with mocked dependencies
    result = await service.create_prediction(test_data)
    assert result is not None
```

## Best Practices

### 1. Use Interfaces
```python
from typing import Protocol

class IUserService(Protocol):
    async def get_user(self, user_id: int) -> User:
        ...

# Register interface with implementation
container.register_singleton(IUserService, UserService)
```

### 2. Factory Functions for Complex Setup
```python
async def create_database_manager(settings: Settings) -> DatabaseManager:
    manager = DatabaseManager(settings.database.url)
    await manager.initialize()
    return manager

container.register_factory(DatabaseManager, create_database_manager)
```

### 3. Proper Lifecycle Management
```python
# Singleton for shared resources
container.register_singleton(DatabaseManager)

# Transient for stateless services
container.register_transient(ValidationService)

# Scoped for request-specific data
container.register_scoped(UserContext)
```

### 4. Clean Shutdown
```python
async def shutdown():
    container = get_container()
    await container.dispose_async()
```

## Performance Considerations

- **Singleton Resolution**: O(1) after first resolution
- **Dependency Graph**: Built once during registration
- **Memory Usage**: Minimal overhead, weak references where appropriate
- **Async Operations**: Non-blocking service resolution

## Thread Safety

The DI container is designed to be thread-safe:
- Singleton initialization uses async locks
- Service resolution is atomic
- Scope management is isolated per scope

This DI container provides a solid foundation for building maintainable, testable, and scalable Discord bots with clean architecture principles.