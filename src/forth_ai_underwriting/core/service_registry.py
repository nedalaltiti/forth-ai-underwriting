"""
Service registry for managing all services in the Forth AI Underwriting System.
Ensures proper initialization, dependency injection, and service lifecycle management.
"""

from typing import Dict, Any, Optional, Type, TypeVar, Callable
from loguru import logger
import asyncio
from dataclasses import dataclass

from forth_ai_underwriting.config.settings import settings


T = TypeVar('T')


@dataclass
class ServiceInfo:
    """Information about a registered service."""
    name: str
    service_class: Type
    instance: Optional[Any] = None
    dependencies: list = None
    initialized: bool = False
    health_check_method: Optional[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class ServiceRegistry:
    """
    Central registry for all services in the application.
    Manages service lifecycle, dependencies, and health monitoring.
    """
    
    def __init__(self):
        self._services: Dict[str, ServiceInfo] = {}
        self._initialization_order: list = []
        self._initialized = False
        logger.info("ServiceRegistry initialized")
    
    def register(
        self,
        name: str,
        service_class: Type[T],
        dependencies: Optional[list] = None,
        health_check_method: Optional[str] = None
    ) -> None:
        """
        Register a service with the registry.
        
        Args:
            name: Service name
            service_class: Service class or factory function
            dependencies: List of service names this service depends on
            health_check_method: Name of health check method (if any)
        """
        if name in self._services:
            logger.warning(f"Service {name} already registered, overwriting")
        
        self._services[name] = ServiceInfo(
            name=name,
            service_class=service_class,
            dependencies=dependencies or [],
            health_check_method=health_check_method
        )
        
        logger.debug(f"Registered service: {name}")
    
    def get(self, name: str, auto_initialize: bool = True) -> Any:
        """
        Get a service instance by name.
        
        Args:
            name: Service name
            auto_initialize: Whether to auto-initialize if not already done
            
        Returns:
            Service instance
        """
        if name not in self._services:
            raise ValueError(f"Service {name} not registered")
        
        service_info = self._services[name]
        
        if not service_info.initialized and auto_initialize:
            self._initialize_service(name)
        
        return service_info.instance
    
    def _initialize_service(self, name: str) -> None:
        """Initialize a single service and its dependencies."""
        if name not in self._services:
            raise ValueError(f"Service {name} not registered")
        
        service_info = self._services[name]
        
        if service_info.initialized:
            return
        
        # Initialize dependencies first
        for dep_name in service_info.dependencies:
            if dep_name not in self._services:
                raise ValueError(f"Dependency {dep_name} not registered for service {name}")
            self._initialize_service(dep_name)
        
        # Initialize the service
        try:
            if callable(service_info.service_class):
                # Handle both classes and factory functions
                if hasattr(service_info.service_class, '__call__') and not hasattr(service_info.service_class, '__init__'):
                    # Factory function
                    service_info.instance = service_info.service_class()
                else:
                    # Class constructor
                    service_info.instance = service_info.service_class()
            else:
                raise ValueError(f"Service class for {name} is not callable")
            
            service_info.initialized = True
            logger.info(f"Initialized service: {name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize service {name}: {e}")
            raise
    
    def initialize_all(self) -> None:
        """Initialize all registered services in dependency order."""
        if self._initialized:
            logger.debug("Services already initialized")
            return
        
        # Calculate initialization order
        self._calculate_initialization_order()
        
        # Initialize services in order
        for service_name in self._initialization_order:
            self._initialize_service(service_name)
        
        self._initialized = True
        logger.info(f"All services initialized: {list(self._services.keys())}")
    
    def _calculate_initialization_order(self) -> None:
        """Calculate the order to initialize services based on dependencies."""
        visited = set()
        temp_visited = set()
        self._initialization_order = []
        
        def visit(service_name: str):
            if service_name in temp_visited:
                raise ValueError(f"Circular dependency detected involving {service_name}")
            if service_name in visited:
                return
            
            temp_visited.add(service_name)
            
            service_info = self._services[service_name]
            for dep_name in service_info.dependencies:
                visit(dep_name)
            
            temp_visited.remove(service_name)
            visited.add(service_name)
            self._initialization_order.append(service_name)
        
        for service_name in self._services:
            if service_name not in visited:
                visit(service_name)
    
    async def health_check_all(self) -> Dict[str, Any]:
        """
        Perform health checks on all services.
        
        Returns:
            Dictionary with health status of all services
        """
        health_results = {}
        
        for name, service_info in self._services.items():
            try:
                if not service_info.initialized:
                    health_results[name] = {
                        "status": "not_initialized",
                        "error": "Service not initialized"
                    }
                    continue
                
                if service_info.health_check_method:
                    health_method = getattr(service_info.instance, service_info.health_check_method, None)
                    if health_method:
                        if asyncio.iscoroutinefunction(health_method):
                            result = await health_method()
                        else:
                            result = health_method()
                        health_results[name] = result
                    else:
                        health_results[name] = {
                            "status": "healthy",
                            "note": "No health check method available"
                        }
                else:
                    health_results[name] = {
                        "status": "healthy",
                        "note": "Service initialized successfully"
                    }
            
            except Exception as e:
                health_results[name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                logger.error(f"Health check failed for service {name}: {e}")
        
        overall_status = "healthy" if all(
            result.get("status") == "healthy" 
            for result in health_results.values()
        ) else "degraded"
        
        return {
            "overall_status": overall_status,
            "services": health_results,
            "initialized_count": len([s for s in self._services.values() if s.initialized]),
            "total_count": len(self._services)
        }
    
    def get_service_info(self, name: str) -> Optional[ServiceInfo]:
        """Get service information by name."""
        return self._services.get(name)
    
    def list_services(self) -> Dict[str, Dict[str, Any]]:
        """List all registered services and their status."""
        return {
            name: {
                "initialized": info.initialized,
                "dependencies": info.dependencies,
                "has_health_check": bool(info.health_check_method)
            }
            for name, info in self._services.items()
        }
    
    def shutdown(self) -> None:
        """Shutdown all services gracefully."""
        logger.info("Shutting down all services")
        
        # Shutdown in reverse order
        shutdown_order = list(reversed(self._initialization_order))
        
        for service_name in shutdown_order:
            service_info = self._services[service_name]
            if service_info.initialized and service_info.instance:
                try:
                    # Call shutdown method if available
                    if hasattr(service_info.instance, 'shutdown'):
                        shutdown_method = getattr(service_info.instance, 'shutdown')
                        if asyncio.iscoroutinefunction(shutdown_method):
                            # Handle async shutdown in sync context
                            try:
                                loop = asyncio.get_event_loop()
                                loop.run_until_complete(shutdown_method())
                            except RuntimeError:
                                # No event loop running
                                pass
                        else:
                            shutdown_method()
                    
                    logger.debug(f"Shutdown service: {service_name}")
                    
                except Exception as e:
                    logger.error(f"Error shutting down service {service_name}: {e}")
        
        self._initialized = False
        logger.info("All services shutdown completed")


# Global service registry instance
_service_registry: Optional[ServiceRegistry] = None


def get_service_registry() -> ServiceRegistry:
    """Get the global service registry instance."""
    global _service_registry
    if _service_registry is None:
        _service_registry = ServiceRegistry()
    return _service_registry


def register_all_services() -> None:
    """Register all application services with the registry."""
    registry = get_service_registry()
    
    # Import services here to avoid circular imports
    from forth_ai_underwriting.services.llm_service import get_llm_service
    from forth_ai_underwriting.services.gemini_service import get_gemini_service
    from forth_ai_underwriting.services.process import get_document_processor
    from forth_ai_underwriting.infrastructure.ai_parser import get_ai_parser_service
    from forth_ai_underwriting.services.validation import ValidationService
    from forth_ai_underwriting.services.teams_bot import TeamsBot
    from forth_ai_underwriting.prompts import get_prompt_manager
    
    # Register services with dependencies
    registry.register(
        name="prompt_manager",
        service_class=get_prompt_manager,
        dependencies=[],
        health_check_method=None
    )
    
    registry.register(
        name="llm_service",
        service_class=get_llm_service,
        dependencies=["prompt_manager"],
        health_check_method="health_check"
    )
    
    registry.register(
        name="gemini_service", 
        service_class=get_gemini_service,
        dependencies=["llm_service"],
        health_check_method="health_check"
    )
    
    registry.register(
        name="document_processor",
        service_class=get_document_processor,
        dependencies=[],
        health_check_method="health_check"
    )
    
    registry.register(
        name="ai_parser_service",
        service_class=get_ai_parser_service,
        dependencies=["document_processor", "gemini_service"],
        health_check_method="health_check"
    )
    
    registry.register(
        name="validation_service",
        service_class=ValidationService,
        dependencies=["gemini_service"],
        health_check_method=None
    )
    
    registry.register(
        name="teams_bot",
        service_class=TeamsBot,
        dependencies=[],
        health_check_method=None
    )
    
    logger.info("All services registered with service registry")


def initialize_application() -> None:
    """Initialize the entire application with all services."""
    logger.info("Initializing Forth AI Underwriting application")
    
    # Register all services
    register_all_services()
    
    # Initialize all services
    registry = get_service_registry()
    registry.initialize_all()
    
    logger.info("Application initialization completed successfully")


async def health_check_application() -> Dict[str, Any]:
    """Perform application-wide health check."""
    registry = get_service_registry()
    return await registry.health_check_all()


def shutdown_application() -> None:
    """Shutdown the entire application gracefully."""
    logger.info("Shutting down Forth AI Underwriting application")
    
    registry = get_service_registry()
    registry.shutdown()
    
    logger.info("Application shutdown completed") 