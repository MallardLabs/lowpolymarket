"""
Structured logging system with JSON format, correlation IDs, and decorators.

This module provides a comprehensive logging solution with:
- JSON structured logging
- Log rotation and file management
- Contextual logging with correlation IDs
- Automatic function entry/exit logging decorators
- Performance monitoring integration
"""

import json
import logging
import logging.handlers
import os
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union
from dataclasses import dataclass, asdict

from config.settings import LoggingSettings


# Context variable for correlation ID tracking
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


@dataclass
class LogContext:
    """Context information for structured logging."""
    correlation_id: Optional[str] = None
    user_id: Optional[int] = None
    guild_id: Optional[int] = None
    prediction_id: Optional[str] = None
    operation: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class CorrelationIdFilter(logging.Filter):
    """Filter to add correlation ID to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to the log record."""
        record.correlation_id = correlation_id.get() or 'none'
        return True


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def __init__(self, include_extra_fields: bool = True):
        super().__init__()
        self.include_extra_fields = include_extra_fields
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'correlation_id': getattr(record, 'correlation_id', 'none')
        }
        
        # Add exception information if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }
        
        # Add extra fields if enabled
        if self.include_extra_fields and hasattr(record, '__dict__'):
            extra_fields = {}
            for key, value in record.__dict__.items():
                if key not in {
                    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                    'filename', 'module', 'lineno', 'funcName', 'created',
                    'msecs', 'relativeCreated', 'thread', 'threadName',
                    'processName', 'process', 'getMessage', 'exc_info',
                    'exc_text', 'stack_info', 'correlation_id'
                }:
                    try:
                        # Only include JSON-serializable values
                        json.dumps(value)
                        extra_fields[key] = value
                    except (TypeError, ValueError):
                        extra_fields[key] = str(value)
            
            if extra_fields:
                log_entry['extra'] = extra_fields
        
        return json.dumps(log_entry, ensure_ascii=False)


class ContextualFormatter(logging.Formatter):
    """Human-readable formatter with contextual information."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with contextual information."""
        correlation_id_str = getattr(record, 'correlation_id', 'none')
        
        # Base format
        base_format = (
            "[{asctime}] [{levelname:<8}] [{correlation_id}] "
            "{name}:{funcName}:{lineno} - {message}"
        )
        
        # Add extra context if available
        extra_context = []
        if hasattr(record, 'user_id') and record.user_id:
            extra_context.append(f"user:{record.user_id}")
        if hasattr(record, 'guild_id') and record.guild_id:
            extra_context.append(f"guild:{record.guild_id}")
        if hasattr(record, 'prediction_id') and record.prediction_id:
            extra_context.append(f"pred:{record.prediction_id}")
        if hasattr(record, 'operation') and record.operation:
            extra_context.append(f"op:{record.operation}")
        
        if extra_context:
            base_format += f" [{':'.join(extra_context)}]"
        
        formatter = logging.Formatter(
            base_format.format(correlation_id=correlation_id_str),
            datefmt="%Y-%m-%d %H:%M:%S",
            style="{"
        )
        
        return formatter.format(record)


class LoggingManager:
    """Centralized logging manager with structured logging capabilities."""
    
    def __init__(self, settings: LoggingSettings):
        self.settings = settings
        self._loggers: Dict[str, logging.Logger] = {}
        self._setup_root_logger()
    
    def _setup_root_logger(self) -> None:
        """Setup the root logger configuration."""
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.settings.level))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Add correlation ID filter to all handlers
        correlation_filter = CorrelationIdFilter()
        
        # Setup console handler
        if self.settings.console_enabled:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.addFilter(correlation_filter)
            
            if self.settings.json_format:
                console_handler.setFormatter(
                    JSONFormatter(self.settings.include_extra_fields)
                )
            else:
                console_handler.setFormatter(ContextualFormatter())
            
            root_logger.addHandler(console_handler)
        
        # Setup file handler with rotation
        if self.settings.file_enabled:
            self._setup_file_handler(root_logger, correlation_filter)
    
    def _setup_file_handler(
        self, 
        logger: logging.Logger, 
        correlation_filter: CorrelationIdFilter
    ) -> None:
        """Setup rotating file handler."""
        # Ensure log directory exists
        log_path = Path(self.settings.file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            filename=self.settings.file_path,
            maxBytes=self.settings.file_max_bytes,
            backupCount=self.settings.file_backup_count,
            encoding='utf-8'
        )
        
        file_handler.addFilter(correlation_filter)
        
        # Always use JSON format for file logging for better parsing
        file_handler.setFormatter(
            JSONFormatter(self.settings.include_extra_fields)
        )
        
        logger.addHandler(file_handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a logger with the specified name."""
        if name not in self._loggers:
            logger = logging.getLogger(name)
            self._loggers[name] = logger
        
        return self._loggers[name]
    
    def set_correlation_id(self, corr_id: Optional[str] = None) -> str:
        """Set correlation ID for the current context."""
        if corr_id is None:
            corr_id = str(uuid.uuid4())
        
        correlation_id.set(corr_id)
        return corr_id
    
    def get_correlation_id(self) -> Optional[str]:
        """Get the current correlation ID."""
        return correlation_id.get()
    
    def clear_correlation_id(self) -> None:
        """Clear the current correlation ID."""
        correlation_id.set(None)
    
    def log_with_context(
        self,
        logger: logging.Logger,
        level: int,
        message: str,
        context: Optional[LogContext] = None,
        **kwargs
    ) -> None:
        """Log a message with contextual information."""
        extra = {}
        
        if context:
            if context.correlation_id:
                correlation_id.set(context.correlation_id)
            
            # Add context fields as extra data
            for field, value in asdict(context).items():
                if value is not None and field != 'extra':
                    extra[field] = value
            
            # Add extra fields from context
            if context.extra:
                extra.update(context.extra)
        
        # Add any additional kwargs as extra data
        extra.update(kwargs)
        
        logger.log(level, message, extra=extra)


# Global logging manager instance
_logging_manager: Optional[LoggingManager] = None


def get_logging_manager(settings: Optional[LoggingSettings] = None) -> LoggingManager:
    """Get the global logging manager instance."""
    global _logging_manager
    
    if _logging_manager is None:
        if settings is None:
            from config.settings import get_settings
            settings = get_settings().logging
        
        _logging_manager = LoggingManager(settings)
    
    return _logging_manager


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name."""
    return get_logging_manager().get_logger(name)


def set_correlation_id(corr_id: Optional[str] = None) -> str:
    """Set correlation ID for the current context."""
    return get_logging_manager().set_correlation_id(corr_id)


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID."""
    return get_logging_manager().get_correlation_id()


def clear_correlation_id() -> None:
    """Clear the current correlation ID."""
    get_logging_manager().clear_correlation_id()


def log_function_call(
    logger: Optional[logging.Logger] = None,
    level: int = logging.DEBUG,
    include_args: bool = False,
    include_result: bool = False,
    include_duration: bool = True
) -> Callable:
    """
    Decorator for automatic function entry/exit logging.
    
    Args:
        logger: Logger to use (defaults to function's module logger)
        level: Log level to use
        include_args: Whether to log function arguments
        include_result: Whether to log function result
        include_duration: Whether to log execution duration
    
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Get logger if not provided
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(func.__module__)
            
            # Generate correlation ID if not present
            try:
                corr_id = get_correlation_id()
                if corr_id is None:
                    corr_id = set_correlation_id()
            except:
                # Fallback if global logging manager is not available
                corr_id = str(uuid.uuid4())
            
            # Prepare log context
            context_data = {
                'function_name': func.__name__,
                'function_module': func.__module__,
                'correlation_id': corr_id
            }
            
            if include_args and (args or kwargs):
                # Sanitize arguments for logging
                safe_args = []
                for arg in args:
                    try:
                        json.dumps(arg)
                        safe_args.append(arg)
                    except (TypeError, ValueError):
                        safe_args.append(str(type(arg).__name__))
                
                safe_kwargs = {}
                for key, value in kwargs.items():
                    try:
                        json.dumps(value)
                        safe_kwargs[key] = value
                    except (TypeError, ValueError):
                        safe_kwargs[key] = str(type(value).__name__)
                
                context_data['function_args'] = safe_args
                context_data['function_kwargs'] = safe_kwargs
            
            # Log function entry
            logger.log(
                level,
                f"Entering function {func.__name__}",
                extra=context_data
            )
            
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Log function exit
                exit_context = context_data.copy()
                if include_duration:
                    exit_context['duration'] = time.time() - start_time
                
                if include_result:
                    try:
                        json.dumps(result)
                        exit_context['result'] = result
                    except (TypeError, ValueError):
                        exit_context['result'] = str(type(result).__name__)
                
                logger.log(
                    level,
                    f"Exiting function {func.__name__}",
                    extra=exit_context
                )
                
                return result
                
            except Exception as e:
                # Log function exception
                error_context = context_data.copy()
                if include_duration:
                    error_context['duration'] = time.time() - start_time
                error_context['error'] = str(e)
                error_context['error_type'] = type(e).__name__
                
                logger.log(
                    logging.ERROR,
                    f"Exception in function {func.__name__}: {e}",
                    extra=error_context
                )
                
                raise
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get logger if not provided
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(func.__module__)
            
            # Generate correlation ID if not present
            try:
                corr_id = get_correlation_id()
                if corr_id is None:
                    corr_id = set_correlation_id()
            except:
                # Fallback if global logging manager is not available
                corr_id = str(uuid.uuid4())
            
            # Prepare log context
            context_data = {
                'function_name': func.__name__,
                'function_module': func.__module__,
                'correlation_id': corr_id,
                'async': True
            }
            
            if include_args and (args or kwargs):
                # Sanitize arguments for logging
                safe_args = []
                for arg in args:
                    try:
                        json.dumps(arg)
                        safe_args.append(arg)
                    except (TypeError, ValueError):
                        safe_args.append(str(type(arg).__name__))
                
                safe_kwargs = {}
                for key, value in kwargs.items():
                    try:
                        json.dumps(value)
                        safe_kwargs[key] = value
                    except (TypeError, ValueError):
                        safe_kwargs[key] = str(type(value).__name__)
                
                context_data['function_args'] = safe_args
                context_data['function_kwargs'] = safe_kwargs
            
            # Log function entry
            logger.log(
                level,
                f"Entering async function {func.__name__}",
                extra=context_data
            )
            
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                
                # Log function exit
                exit_context = context_data.copy()
                if include_duration:
                    exit_context['duration'] = time.time() - start_time
                
                if include_result:
                    try:
                        json.dumps(result)
                        exit_context['result'] = result
                    except (TypeError, ValueError):
                        exit_context['result'] = str(type(result).__name__)
                
                logger.log(
                    level,
                    f"Exiting async function {func.__name__}",
                    extra=exit_context
                )
                
                return result
                
            except Exception as e:
                # Log function exception
                error_context = context_data.copy()
                if include_duration:
                    error_context['duration'] = time.time() - start_time
                error_context['error'] = str(e)
                error_context['error_type'] = type(e).__name__
                
                logger.log(
                    logging.ERROR,
                    f"Exception in async function {func.__name__}: {e}",
                    extra=error_context
                )
                
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def log_performance(
    logger: Optional[logging.Logger] = None,
    threshold_seconds: float = 1.0,
    level: int = logging.WARNING
) -> Callable:
    """
    Decorator to log performance warnings for slow functions.
    
    Args:
        logger: Logger to use (defaults to function's module logger)
        threshold_seconds: Threshold in seconds to trigger warning
        level: Log level for performance warnings
    
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            if duration > threshold_seconds:
                nonlocal logger
                if logger is None:
                    logger = logging.getLogger(func.__module__)
                
                try:
                    corr_id = get_correlation_id()
                except:
                    corr_id = 'none'
                
                logger.log(
                    level,
                    f"Slow function execution: {func.__name__} took {duration:.3f}s",
                    extra={
                        'function_name': func.__name__,
                        'function_module': func.__module__,
                        'duration': duration,
                        'threshold': threshold_seconds,
                        'correlation_id': corr_id
                    }
                )
            
            return result
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            
            if duration > threshold_seconds:
                nonlocal logger
                if logger is None:
                    logger = logging.getLogger(func.__module__)
                
                try:
                    corr_id = get_correlation_id()
                except:
                    corr_id = 'none'
                
                logger.log(
                    level,
                    f"Slow async function execution: {func.__name__} took {duration:.3f}s",
                    extra={
                        'function_name': func.__name__,
                        'function_module': func.__module__,
                        'duration': duration,
                        'threshold': threshold_seconds,
                        'async': True,
                        'correlation_id': corr_id
                    }
                )
            
            return result
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator