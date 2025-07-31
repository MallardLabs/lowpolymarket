"""
Dependency Injection Container for managing application services.

This module provides a comprehensive DI container with support for:
- Service registration and resolution
- Lifecycle management (singleton, transient, scoped)
- Factory methods for complex object creation
- Circular dependency detection
- Async service initialization and cleanup
"""

import asyncio
import inspect
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import (
    Any, Callable, Dict, List, Optional, Type, TypeVar, Union,
    get_type_hints, get_origin, get_args
)
from weakref import WeakSet

from .exceptions import (
    DIContainerError,
    ServiceNotFoundError, 
    ServiceRegistrationError,
    CircularDependencyError
)

T = TypeVar('T')
logger = logging.getLogger(__name__)


class ServiceLifecycle(Enum):
    """Service lifecycle management options."""
    SINGLETON = "singleton"  # Single instance for the entire application
    TRANSIENT = "transient"  # New instance every time
    SCOPED = "scoped"       # Single instance per scope (e.g., per request)


class ServiceDescriptor:
    """Describes how a service should be created and managed."""
    
    def __init__(
        self,
        service_type: Type[T],
        implementation: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None,
        lifecycle: ServiceLifecycle = ServiceLifecycle.SINGLETON,
        dependencies: Optional[Dict[str, str]] = None
    ):
        self.service_type = service_type
        self.implementation = implementation or service_type
        self.factory = factory
        self.lifecycle = lifecycle
        self.dependencies = dependencies or {}
        self.instance: Optional[T] = None
        self.is_initializing = False


class IServiceScope(ABC):
    """Interface for service scopes."""
    
    @abstractmethod
    def get_scoped_instance(self, service_name: str) -> Optional[Any]:
        """Get a scoped instance of a service."""
        pass
    
    @abstractmethod
    def set_scoped_instance(self, service_name: str, instance: Any) -> None:
        """Set a scoped instance of a service."""
        pass
    
    @abstractmethod
    async def dispose_async(self) -> None:
        """Dispose of all scoped instances."""
        pass


class ServiceScope(IServiceScope):
    """Default implementation of service scope."""
    
    def __init__(self):
        self._instances: Dict[str, Any] = {}
        self._disposed = False
    
    def get_scoped_instance(self, service_name: str) -> Optional[Any]:
        if self._disposed:
            raise DIContainerError("Cannot access disposed scope")
        return self._instances.get(service_name)
    
    def set_scoped_instance(self, service_name: str, instance: Any) -> None:
        if self._disposed:
            raise DIContainerError("Cannot set instance in disposed scope")
        self._instances[service_name] = instance
    
    async def dispose_async(self) -> None:
        """Dispose of all scoped instances."""
        if self._disposed:
            return
        
        self._disposed = True
        
        # Dispose instances that support async disposal
        for instance in self._instances.values():
            if hasattr(instance, 'dispose_async'):
                try:
                    await instance.dispose_async()
                except Exception as e:
                    logger.error(f"Error disposing instance {type(instance).__name__}: {e}")
            elif hasattr(instance, 'dispose'):
                try:
                    instance.dispose()
                except Exception as e:
                    logger.error(f"Error disposing instance {type(instance).__name__}: {e}")
        
        self._instances.clear()


class DIContainer:
    """
    Dependency Injection Container for managing application services.
    
    Provides service registration, resolution, and lifecycle management
    with support for singleton, transient, and scoped services.
    """
    
    def __init__(self):
        self._services: Dict[str, ServiceDescriptor] = {}
        self._resolution_stack: List[str] = []
        self._current_scope: Optional[IServiceScope] = None
        self._disposed = False
        self._initialization_lock = asyncio.Lock()
        
        # Register the container itself
        self.register_instance(DIContainer, self)
    
    def register_singleton(
        self, 
        service_type: Type[T], 
        implementation: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None
    ) -> 'DIContainer':
        """
        Register a service as singleton (single instance for entire application).
        
        Args:
            service_type: The service interface/type
            implementation: The concrete implementation (optional if same as service_type)
            factory: Factory function to create the service (optional)
            
        Returns:
            Self for method chaining
        """
        return self._register_service(
            service_type, implementation, factory, ServiceLifecycle.SINGLETON
        )
    
    def register_transient(
        self,
        service_type: Type[T],
        implementation: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None
    ) -> 'DIContainer':
        """
        Register a service as transient (new instance every time).
        
        Args:
            service_type: The service interface/type
            implementation: The concrete implementation (optional if same as service_type)
            factory: Factory function to create the service (optional)
            
        Returns:
            Self for method chaining
        """
        return self._register_service(
            service_type, implementation, factory, ServiceLifecycle.TRANSIENT
        )
    
    def register_scoped(
        self,
        service_type: Type[T],
        implementation: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None
    ) -> 'DIContainer':
        """
        Register a service as scoped (single instance per scope).
        
        Args:
            service_type: The service interface/type
            implementation: The concrete implementation (optional if same as service_type)
            factory: Factory function to create the service (optional)
            
        Returns:
            Self for method chaining
        """
        return self._register_service(
            service_type, implementation, factory, ServiceLifecycle.SCOPED
        )
    
    def register_instance(self, service_type: Type[T], instance: T) -> 'DIContainer':
        """
        Register an existing instance as a singleton service.
        
        Args:
            service_type: The service interface/type
            instance: The service instance
            
        Returns:
            Self for method chaining
        """
        service_name = self._get_service_name(service_type)
        
        if service_name in self._services:
            raise ServiceRegistrationError(
                service_name, 
                "Service is already registered"
            )
        
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation=type(instance),
            lifecycle=ServiceLifecycle.SINGLETON
        )
        descriptor.instance = instance
        
        self._services[service_name] = descriptor
        logger.debug(f"Registered instance for service: {service_name}")
        
        return self
    
    def register_factory(
        self,
        service_type: Type[T],
        factory: Callable[..., T],
        lifecycle: ServiceLifecycle = ServiceLifecycle.SINGLETON
    ) -> 'DIContainer':
        """
        Register a factory function for creating services.
        
        Args:
            service_type: The service interface/type
            factory: Factory function to create the service
            lifecycle: Service lifecycle management
            
        Returns:
            Self for method chaining
        """
        return self._register_service(service_type, None, factory, lifecycle)
    
    async def get_service(self, service_type: Type[T]) -> T:
        """
        Resolve and return a service instance.
        
        Args:
            service_type: The service type to resolve
            
        Returns:
            The service instance
            
        Raises:
            ServiceNotFoundError: If the service is not registered
            CircularDependencyError: If circular dependencies are detected
        """
        if self._disposed:
            raise DIContainerError("Container has been disposed")
        
        service_name = self._get_service_name(service_type)
        return await self._resolve_service(service_name)
    
    async def get_service_by_name(self, service_name: str) -> Any:
        """
        Resolve and return a service instance by name.
        
        Args:
            service_name: The service name to resolve
            
        Returns:
            The service instance
        """
        if self._disposed:
            raise DIContainerError("Container has been disposed")
        
        return await self._resolve_service(service_name)
    
    def create_scope(self) -> IServiceScope:
        """
        Create a new service scope for scoped services.
        
        Returns:
            A new service scope
        """
        return ServiceScope()
    
    async def execute_scoped(self, scope: IServiceScope, func: Callable) -> Any:
        """
        Execute a function within a service scope.
        
        Args:
            scope: The service scope to use
            func: The function to execute
            
        Returns:
            The function result
        """
        previous_scope = self._current_scope
        self._current_scope = scope
        
        try:
            if asyncio.iscoroutinefunction(func):
                return await func()
            else:
                return func()
        finally:
            self._current_scope = previous_scope
    
    def is_registered(self, service_type: Type[T]) -> bool:
        """
        Check if a service type is registered.
        
        Args:
            service_type: The service type to check
            
        Returns:
            True if registered, False otherwise
        """
        service_name = self._get_service_name(service_type)
        return service_name in self._services
    
    def get_registered_services(self) -> List[str]:
        """
        Get a list of all registered service names.
        
        Returns:
            List of service names
        """
        return list(self._services.keys())
    
    async def initialize_all_singletons(self) -> None:
        """
        Initialize all registered singleton services.
        
        This is useful for eager initialization of critical services.
        """
        async with self._initialization_lock:
            singleton_services = [
                name for name, descriptor in self._services.items()
                if descriptor.lifecycle == ServiceLifecycle.SINGLETON
            ]
            
            for service_name in singleton_services:
                try:
                    await self._resolve_service(service_name)
                    logger.debug(f"Initialized singleton service: {service_name}")
                except Exception as e:
                    logger.error(f"Failed to initialize singleton service {service_name}: {e}")
                    raise
    
    async def dispose_async(self) -> None:
        """
        Dispose of the container and all managed services.
        """
        if self._disposed:
            return
        
        self._disposed = True
        logger.info("Disposing DI container...")
        
        # Dispose singleton instances
        for descriptor in self._services.values():
            if descriptor.instance and descriptor.lifecycle == ServiceLifecycle.SINGLETON:
                await self._dispose_instance(descriptor.instance)
        
        # Clear all services
        self._services.clear()
        self._resolution_stack.clear()
        
        logger.info("DI container disposed")
    
    def _register_service(
        self,
        service_type: Type[T],
        implementation: Optional[Type[T]],
        factory: Optional[Callable[..., T]],
        lifecycle: ServiceLifecycle
    ) -> 'DIContainer':
        """Internal method to register a service."""
        service_name = self._get_service_name(service_type)
        
        if service_name in self._services:
            raise ServiceRegistrationError(
                service_name,
                "Service is already registered"
            )
        
        # Validate registration
        if factory is None and implementation is None:
            implementation = service_type
        
        if factory is None and not inspect.isclass(implementation):
            raise ServiceRegistrationError(
                service_name,
                "Implementation must be a class when no factory is provided"
            )
        
        # Extract dependencies from constructor or factory
        dependencies = self._extract_dependencies(factory or implementation)
        
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation=implementation,
            factory=factory,
            lifecycle=lifecycle,
            dependencies=dependencies
        )
        
        self._services[service_name] = descriptor
        logger.debug(f"Registered service: {service_name} ({lifecycle.value})")
        
        return self
    
    async def _resolve_service(self, service_name: str) -> Any:
        """Internal method to resolve a service."""
        if service_name not in self._services:
            raise ServiceNotFoundError(service_name)
        
        # Check for circular dependencies
        if service_name in self._resolution_stack:
            chain = self._resolution_stack + [service_name]
            raise CircularDependencyError(chain)
        
        descriptor = self._services[service_name]
        
        # Handle different lifecycles
        if descriptor.lifecycle == ServiceLifecycle.SINGLETON:
            return await self._resolve_singleton(service_name, descriptor)
        elif descriptor.lifecycle == ServiceLifecycle.SCOPED:
            return await self._resolve_scoped(service_name, descriptor)
        else:  # TRANSIENT
            return await self._create_instance(service_name, descriptor)
    
    async def _resolve_singleton(self, service_name: str, descriptor: ServiceDescriptor) -> Any:
        """Resolve a singleton service."""
        if descriptor.instance is not None:
            return descriptor.instance
        
        # Prevent concurrent initialization
        if descriptor.is_initializing:
            # Wait for initialization to complete
            while descriptor.is_initializing:
                await asyncio.sleep(0.01)
            return descriptor.instance
        
        descriptor.is_initializing = True
        
        try:
            instance = await self._create_instance(service_name, descriptor)
            descriptor.instance = instance
            return instance
        finally:
            descriptor.is_initializing = False
    
    async def _resolve_scoped(self, service_name: str, descriptor: ServiceDescriptor) -> Any:
        """Resolve a scoped service."""
        if self._current_scope is None:
            raise DIContainerError(
                f"Cannot resolve scoped service '{service_name}' outside of a scope"
            )
        
        # Check if instance already exists in current scope
        instance = self._current_scope.get_scoped_instance(service_name)
        if instance is not None:
            return instance
        
        # Create new instance for this scope
        instance = await self._create_instance(service_name, descriptor)
        self._current_scope.set_scoped_instance(service_name, instance)
        
        return instance
    
    async def _create_instance(self, service_name: str, descriptor: ServiceDescriptor) -> Any:
        """Create a new service instance."""
        self._resolution_stack.append(service_name)
        
        try:
            # Resolve dependencies
            dependencies = {}
            for param_name, service_type_name in descriptor.dependencies.items():
                dependencies[param_name] = await self._resolve_service(service_type_name)
            
            # Create instance
            if descriptor.factory:
                # Use factory function
                if asyncio.iscoroutinefunction(descriptor.factory):
                    instance = await descriptor.factory(**dependencies)
                else:
                    instance = descriptor.factory(**dependencies)
            else:
                # Use constructor
                instance = descriptor.implementation(**dependencies)
            
            # Initialize if needed
            if hasattr(instance, 'initialize_async'):
                await instance.initialize_async()
            elif hasattr(instance, 'initialize'):
                instance.initialize()
            
            logger.debug(f"Created instance for service: {service_name}")
            return instance
            
        finally:
            self._resolution_stack.pop()
    
    def _extract_dependencies(self, target: Union[Type, Callable]) -> Dict[str, str]:
        """Extract dependency parameter names and their service types from constructor or factory function."""
        try:
            if inspect.isclass(target):
                # Get constructor signature
                sig = inspect.signature(target.__init__)
                # Skip 'self' parameter
                params = list(sig.parameters.values())[1:]
            else:
                # Get function signature
                sig = inspect.signature(target)
                params = list(sig.parameters.values())
            
            dependencies = {}
            for param in params:
                if param.annotation != inspect.Parameter.empty:
                    # Use type annotation to determine service name
                    service_name = self._get_service_name(param.annotation)
                    dependencies[param.name] = service_name
                else:
                    # Use parameter name as service name
                    dependencies[param.name] = param.name
            
            return dependencies
            
        except Exception as e:
            logger.warning(f"Could not extract dependencies from {target}: {e}")
            return {}
    
    def _get_service_name(self, service_type: Type) -> str:
        """Get the service name for a given type."""
        if hasattr(service_type, '__name__'):
            return service_type.__name__
        else:
            return str(service_type)
    
    async def _dispose_instance(self, instance: Any) -> None:
        """Dispose of a service instance."""
        try:
            if hasattr(instance, 'dispose_async'):
                await instance.dispose_async()
            elif hasattr(instance, 'dispose'):
                instance.dispose()
        except Exception as e:
            logger.error(f"Error disposing instance {type(instance).__name__}: {e}")


# Global container instance
_container: Optional[DIContainer] = None


def get_container() -> DIContainer:
    """
    Get the global DI container instance.
    
    Returns:
        The global DI container
    """
    global _container
    if _container is None:
        _container = DIContainer()
    return _container


def set_container(container: DIContainer) -> None:
    """
    Set the global DI container instance.
    
    Args:
        container: The DI container to set as global
    """
    global _container
    _container = container