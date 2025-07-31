"""
Unit tests for the Dependency Injection Container.
"""

import asyncio
import pytest
from typing import Protocol
from unittest.mock import Mock, AsyncMock

from core.container import DIContainer, ServiceLifecycle
from core.exceptions import (
    ServiceNotFoundError,
    ServiceRegistrationError,
    CircularDependencyError
)


# Test interfaces and implementations
class ITestService(Protocol):
    def get_value(self) -> str:
        ...


class MockTestService:
    def __init__(self):
        self.value = "test_service"
    
    def get_value(self) -> str:
        return self.value


class MockTestServiceWithDependency:
    def __init__(self, test_service: MockTestService):
        self.test_service = test_service
        self.value = "dependent_service"
    
    def get_value(self) -> str:
        return f"{self.value}_{self.test_service.get_value()}"


class MockAsyncTestService:
    def __init__(self):
        self.initialized = False
        self.disposed = False
    
    async def initialize_async(self):
        self.initialized = True
    
    async def dispose_async(self):
        self.disposed = True
    
    def get_value(self) -> str:
        return "async_service"


class MockCircularDependencyA:
    def __init__(self, circular_b: 'MockCircularDependencyB'):
        self.circular_b = circular_b


class MockCircularDependencyB:
    def __init__(self, circular_a: MockCircularDependencyA):
        self.circular_a = circular_a


@pytest.fixture
def container():
    """Create a fresh DI container for each test."""
    return DIContainer()


class TestDIContainerBasics:
    """Test basic DI container functionality."""
    
    def test_container_creation(self, container):
        """Test that container can be created."""
        assert container is not None
        assert isinstance(container, DIContainer)
    
    def test_register_instance(self, container):
        """Test registering an existing instance."""
        service = MockTestService()
        container.register_instance(MockTestService, service)
        
        assert container.is_registered(MockTestService)
        assert MockTestService.__name__ in container.get_registered_services()
    
    @pytest.mark.asyncio
    async def test_resolve_instance(self, container):
        """Test resolving a registered instance."""
        service = MockTestService()
        container.register_instance(MockTestService, service)
        
        resolved = await container.get_service(MockTestService)
        assert resolved is service
        assert resolved.get_value() == "test_service"
    
    def test_register_singleton(self, container):
        """Test registering a singleton service."""
        container.register_singleton(MockTestService)
        
        assert container.is_registered(MockTestService)
    
    @pytest.mark.asyncio
    async def test_resolve_singleton(self, container):
        """Test that singleton returns same instance."""
        container.register_singleton(MockTestService)
        
        instance1 = await container.get_service(MockTestService)
        instance2 = await container.get_service(MockTestService)
        
        assert instance1 is instance2
        assert instance1.get_value() == "test_service"
    
    def test_register_transient(self, container):
        """Test registering a transient service."""
        container.register_transient(MockTestService)
        
        assert container.is_registered(MockTestService)
    
    @pytest.mark.asyncio
    async def test_resolve_transient(self, container):
        """Test that transient returns different instances."""
        container.register_transient(MockTestService)
        
        instance1 = await container.get_service(MockTestService)
        instance2 = await container.get_service(MockTestService)
        
        assert instance1 is not instance2
        assert instance1.get_value() == "test_service"
        assert instance2.get_value() == "test_service"
    
    def test_register_scoped(self, container):
        """Test registering a scoped service."""
        container.register_scoped(MockTestService)
        
        assert container.is_registered(MockTestService)
    
    @pytest.mark.asyncio
    async def test_resolve_scoped(self, container):
        """Test that scoped returns same instance within scope."""
        container.register_scoped(MockTestService)
        
        scope = container.create_scope()
        
        async def test_func():
            instance1 = await container.get_service(MockTestService)
            instance2 = await container.get_service(MockTestService)
            return instance1, instance2
        
        instance1, instance2 = await container.execute_scoped(scope, test_func)
        
        assert instance1 is instance2
        assert instance1.get_value() == "test_service"
        
        await scope.dispose_async()


class TestDependencyInjection:
    """Test dependency injection functionality."""
    
    @pytest.mark.asyncio
    async def test_dependency_injection(self, container):
        """Test that dependencies are properly injected."""
        container.register_singleton(MockTestService)
        container.register_singleton(MockTestServiceWithDependency)
        
        service = await container.get_service(MockTestServiceWithDependency)
        
        assert service.get_value() == "dependent_service_test_service"
        assert isinstance(service.test_service, MockTestService)
    
    @pytest.mark.asyncio
    async def test_circular_dependency_detection(self, container):
        """Test that circular dependencies are detected."""
        container.register_singleton(MockCircularDependencyA)
        container.register_singleton(MockCircularDependencyB)
        
        with pytest.raises(CircularDependencyError) as exc_info:
            await container.get_service(MockCircularDependencyA)
        
        assert "MockCircularDependencyA" in str(exc_info.value)
        assert "MockCircularDependencyB" in str(exc_info.value)


class TestFactoryMethods:
    """Test factory method functionality."""
    
    @pytest.mark.asyncio
    async def test_factory_registration(self, container):
        """Test registering services with factory methods."""
        def create_test_service() -> MockTestService:
            service = MockTestService()
            service.value = "factory_created"
            return service
        
        container.register_factory(MockTestService, create_test_service)
        
        service = await container.get_service(MockTestService)
        assert service.get_value() == "factory_created"
    
    @pytest.mark.asyncio
    async def test_async_factory_registration(self, container):
        """Test registering services with async factory methods."""
        async def create_async_service() -> MockAsyncTestService:
            service = MockAsyncTestService()
            await service.initialize_async()
            return service
        
        container.register_factory(MockAsyncTestService, create_async_service)
        
        service = await container.get_service(MockAsyncTestService)
        assert service.initialized
        assert service.get_value() == "async_service"
    
    @pytest.mark.asyncio
    async def test_factory_with_dependencies(self, container):
        """Test factory methods with dependencies."""
        container.register_singleton(MockTestService)
        
        def create_dependent_service(test_service: MockTestService) -> MockTestServiceWithDependency:
            return MockTestServiceWithDependency(test_service)
        
        container.register_factory(MockTestServiceWithDependency, create_dependent_service)
        
        service = await container.get_service(MockTestServiceWithDependency)
        assert service.get_value() == "dependent_service_test_service"


class TestAsyncInitialization:
    """Test async initialization and disposal."""
    
    @pytest.mark.asyncio
    async def test_async_initialization(self, container):
        """Test that async initialization is called."""
        container.register_singleton(MockAsyncTestService)
        
        service = await container.get_service(MockAsyncTestService)
        assert service.initialized
    
    @pytest.mark.asyncio
    async def test_initialize_all_singletons(self, container):
        """Test initializing all singleton services."""
        container.register_singleton(MockTestService)
        container.register_singleton(MockAsyncTestService)
        # Don't register MockTestService again as transient - use a different service
        
        await container.initialize_all_singletons()
        
        # Verify singletons are created
        test_service = await container.get_service(MockTestService)
        async_service = await container.get_service(MockAsyncTestService)
        
        assert test_service is not None
        assert async_service.initialized
    
    @pytest.mark.asyncio
    async def test_container_disposal(self, container):
        """Test that container disposal works correctly."""
        container.register_singleton(MockAsyncTestService)
        
        service = await container.get_service(MockAsyncTestService)
        assert not service.disposed
        
        await container.dispose_async()
        assert service.disposed


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_service_not_found(self, container):
        """Test that ServiceNotFoundError is raised for unregistered services."""
        with pytest.raises(ServiceNotFoundError) as exc_info:
            await container.get_service(MockTestService)
        
        assert "MockTestService" in str(exc_info.value)
    
    def test_duplicate_registration(self, container):
        """Test that duplicate registration raises error."""
        container.register_singleton(MockTestService)
        
        with pytest.raises(ServiceRegistrationError) as exc_info:
            container.register_singleton(MockTestService)
        
        assert "already registered" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_scoped_without_scope(self, container):
        """Test that scoped services require a scope."""
        container.register_scoped(MockTestService)
        
        with pytest.raises(Exception):  # Should raise an error about missing scope
            await container.get_service(MockTestService)


class TestServiceScopes:
    """Test service scope functionality."""
    
    @pytest.mark.asyncio
    async def test_different_scopes_different_instances(self, container):
        """Test that different scopes get different instances."""
        container.register_scoped(MockTestService)
        
        scope1 = container.create_scope()
        scope2 = container.create_scope()
        
        async def get_service():
            return await container.get_service(MockTestService)
        
        instance1 = await container.execute_scoped(scope1, get_service)
        instance2 = await container.execute_scoped(scope2, get_service)
        
        assert instance1 is not instance2
        
        await scope1.dispose_async()
        await scope2.dispose_async()
    
    @pytest.mark.asyncio
    async def test_scope_disposal(self, container):
        """Test that scope disposal works correctly."""
        container.register_scoped(MockAsyncTestService)
        
        scope = container.create_scope()
        
        async def get_service():
            return await container.get_service(MockAsyncTestService)
        
        service = await container.execute_scoped(scope, get_service)
        assert not service.disposed
        
        await scope.dispose_async()
        assert service.disposed


if __name__ == "__main__":
    pytest.main([__file__])