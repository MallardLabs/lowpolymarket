"""
Security middleware for Discord commands with comprehensive protection.

This middleware integrates with the validation middleware to provide:
- Advanced input sanitization
- Audit logging for all operations
- Security monitoring and threat detection
- Rate limit abuse detection
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable, Any, Union
from functools import wraps
from datetime import datetime

import discord
from discord.ext import commands

from .security import (
    InputSanitizer, AuditLogger, SecurityMonitor, AuditEventType, 
    SecurityLevel, get_audit_logger, get_security_monitor,
    sanitize_user_input, audit_user_action
)
from .validation_middleware import ValidationMiddleware
from .exceptions import SecurityError, ValidationError
from .logging_manager import get_logger, set_correlation_id


class SecurityMiddleware:
    """Security middleware for Discord commands."""
    
    def __init__(self):
        self.audit_logger = get_audit_logger()
        self.security_monitor = get_security_monitor()
        self.logger = get_logger(__name__)
        self.sanitizer = InputSanitizer()
    
    def secure_command(
        self,
        audit_event_type: AuditEventType = None,
        security_level: SecurityLevel = SecurityLevel.MEDIUM,
        sanitize_inputs: bool = True,
        strict_sanitization: bool = False,
        monitor_anomalies: bool = True,
        log_access: bool = True,
        sensitive_params: List[str] = None
    ):
        """
        Comprehensive security decorator for Discord commands.
        
        Args:
            audit_event_type: Type of audit event to log
            security_level: Security level for the operation
            sanitize_inputs: Whether to sanitize string inputs
            strict_sanitization: Enable strict sanitization mode
            monitor_anomalies: Whether to monitor for input anomalies
            log_access: Whether to log command access
            sensitive_params: List of parameter names containing sensitive data
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(cog_self, interaction: discord.Interaction, *args, **kwargs):
                # Set correlation ID for tracking
                correlation_id = set_correlation_id()
                
                start_time = time.time()
                success = True
                error_message = None
                
                try:
                    # 1. Log command access if enabled
                    if log_access:
                        self.audit_logger.log_api_access(
                            api_endpoint=f"discord_command:{func.__name__}",
                            user_id=interaction.user.id,
                            success=True,
                            details={
                                'guild_id': interaction.guild.id if interaction.guild else None,
                                'channel_id': interaction.channel.id if interaction.channel else None,
                                'command_name': func.__name__
                            },
                            correlation_id=correlation_id
                        )
                    
                    # 2. Input sanitization and anomaly detection
                    if sanitize_inputs or monitor_anomalies:
                        args, kwargs = await self._process_inputs(
                            func, interaction, args, kwargs,
                            sanitize_inputs, strict_sanitization, monitor_anomalies,
                            sensitive_params or []
                        )
                    
                    # 3. Execute the command
                    result = await func(cog_self, interaction, *args, **kwargs)
                    
                    # 4. Log successful audit event
                    if audit_event_type:
                        self.audit_logger.log_user_action(
                            event_type=audit_event_type,
                            user_id=interaction.user.id,
                            guild_id=interaction.guild.id if interaction.guild else None,
                            details={
                                'command_name': func.__name__,
                                'execution_time': time.time() - start_time,
                                'args_count': len(args),
                                'kwargs_count': len(kwargs)
                            },
                            success=True,
                            security_level=security_level,
                            correlation_id=correlation_id
                        )
                    
                    return result
                
                except SecurityError as e:
                    success = False
                    error_message = str(e)
                    
                    # Log security violation
                    self.audit_logger.log_security_violation(
                        violation_type="command_security_error",
                        user_id=interaction.user.id,
                        guild_id=interaction.guild.id if interaction.guild else None,
                        details={
                            'command_name': func.__name__,
                            'error': str(e),
                            'error_details': e.details if hasattr(e, 'details') else None
                        },
                        correlation_id=correlation_id
                    )
                    
                    await self._handle_security_error(interaction, e)
                
                except ValidationError as e:
                    success = False
                    error_message = str(e)
                    
                    # Log validation failure
                    self.audit_logger.log_user_action(
                        event_type=AuditEventType.SECURITY_VIOLATION,
                        user_id=interaction.user.id,
                        guild_id=interaction.guild.id if interaction.guild else None,
                        details={
                            'command_name': func.__name__,
                            'validation_error': str(e),
                            'error_type': 'validation_error'
                        },
                        success=False,
                        security_level=SecurityLevel.MEDIUM,
                        correlation_id=correlation_id
                    )
                    
                    await self._handle_validation_error(interaction, e)
                
                except Exception as e:
                    success = False
                    error_message = str(e)
                    
                    # Log unexpected error
                    self.logger.error(
                        f"Unexpected error in secured command {func.__name__}: {str(e)}",
                        extra={
                            'user_id': interaction.user.id,
                            'guild_id': interaction.guild.id if interaction.guild else None,
                            'command_name': func.__name__,
                            'correlation_id': correlation_id
                        }
                    )
                    
                    await self._handle_generic_error(interaction, e)
                
                finally:
                    # Log failed audit event if applicable
                    if not success and audit_event_type:
                        self.audit_logger.log_user_action(
                            event_type=audit_event_type,
                            user_id=interaction.user.id,
                            guild_id=interaction.guild.id if interaction.guild else None,
                            details={
                                'command_name': func.__name__,
                                'execution_time': time.time() - start_time,
                                'error_message': error_message
                            },
                            success=False,
                            error_message=error_message,
                            security_level=security_level,
                            correlation_id=correlation_id
                        )
            
            return wrapper
        return decorator
    
    async def _process_inputs(
        self,
        func: Callable,
        interaction: discord.Interaction,
        args: tuple,
        kwargs: dict,
        sanitize_inputs: bool,
        strict_sanitization: bool,
        monitor_anomalies: bool,
        sensitive_params: List[str]
    ) -> tuple:
        """Process and sanitize function inputs."""
        # Get parameter names
        param_names = list(func.__code__.co_varnames[:func.__code__.co_argcount])
        
        # Skip 'self' and 'interaction' parameters
        if param_names and param_names[0] == 'self':
            param_names = param_names[1:]
        if param_names and param_names[0] == 'interaction':
            param_names = param_names[1:]
        
        # Create parameter mapping
        params = dict(zip(param_names, args))
        params.update(kwargs)
        
        # Process each parameter
        sanitized_args = list(args)
        sanitized_kwargs = kwargs.copy()
        
        for i, (param_name, value) in enumerate(zip(param_names[:len(args)], args)):
            if isinstance(value, str):
                # Monitor for anomalies
                if monitor_anomalies:
                    self.security_monitor.detect_input_anomalies(
                        user_id=interaction.user.id,
                        input_data=value,
                        input_type=f"command_arg:{param_name}"
                    )
                
                # Sanitize input
                if sanitize_inputs:
                    try:
                        sanitized_value = self.sanitizer.sanitize_text(
                            value,
                            strict_mode=strict_sanitization
                        )
                        sanitized_args[i] = sanitized_value
                        
                        # Log if sanitization changed the input
                        if sanitized_value != value:
                            self.logger.info(
                                f"Input sanitized for parameter {param_name}",
                                extra={
                                    'user_id': interaction.user.id,
                                    'parameter': param_name,
                                    'original_length': len(value),
                                    'sanitized_length': len(sanitized_value),
                                    'command': func.__name__
                                }
                            )
                    
                    except SecurityError as e:
                        # Log security violation for malicious input
                        self.audit_logger.log_security_violation(
                            violation_type="malicious_input_detected",
                            user_id=interaction.user.id,
                            guild_id=interaction.guild.id if interaction.guild else None,
                            details={
                                'parameter': param_name,
                                'command': func.__name__,
                                'error': str(e),
                                'input_length': len(value)
                            }
                        )
                        raise
        
        # Process kwargs
        for param_name, value in kwargs.items():
            if isinstance(value, str):
                # Monitor for anomalies
                if monitor_anomalies:
                    self.security_monitor.detect_input_anomalies(
                        user_id=interaction.user.id,
                        input_data=value,
                        input_type=f"command_kwarg:{param_name}"
                    )
                
                # Sanitize input
                if sanitize_inputs:
                    try:
                        sanitized_value = self.sanitizer.sanitize_text(
                            value,
                            strict_mode=strict_sanitization
                        )
                        sanitized_kwargs[param_name] = sanitized_value
                        
                        # Log if sanitization changed the input
                        if sanitized_value != value:
                            self.logger.info(
                                f"Input sanitized for parameter {param_name}",
                                extra={
                                    'user_id': interaction.user.id,
                                    'parameter': param_name,
                                    'original_length': len(value),
                                    'sanitized_length': len(sanitized_value),
                                    'command': func.__name__
                                }
                            )
                    
                    except SecurityError as e:
                        # Log security violation for malicious input
                        self.audit_logger.log_security_violation(
                            violation_type="malicious_input_detected",
                            user_id=interaction.user.id,
                            guild_id=interaction.guild.id if interaction.guild else None,
                            details={
                                'parameter': param_name,
                                'command': func.__name__,
                                'error': str(e),
                                'input_length': len(value)
                            }
                        )
                        raise
        
        # Mask sensitive parameters in logs
        if sensitive_params:
            for param_name in sensitive_params:
                if param_name in params:
                    self.logger.info(
                        f"Sensitive parameter {param_name} processed",
                        extra={
                            'user_id': interaction.user.id,
                            'parameter': param_name,
                            'command': func.__name__,
                            'sensitive_data': True
                        }
                    )
        
        return tuple(sanitized_args), sanitized_kwargs
    
    async def _handle_security_error(self, interaction: discord.Interaction, error: SecurityError):
        """Handle security errors."""
        message = "🔒 **Security Error**\nYour request was blocked for security reasons."
        
        # Don't reveal specific security details to users
        if hasattr(error, 'user_message') and error.user_message:
            message += f"\n\n{error.user_message}"
        
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    
    async def _handle_validation_error(self, interaction: discord.Interaction, error: ValidationError):
        """Handle validation errors."""
        message = f"❌ **Validation Error**\n{str(error)}"
        
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    
    async def _handle_generic_error(self, interaction: discord.Interaction, error: Exception):
        """Handle generic errors."""
        message = "❌ An unexpected error occurred while processing your command."
        
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


class CombinedSecurityMiddleware:
    """Combined security and validation middleware."""
    
    def __init__(self):
        self.security_middleware = SecurityMiddleware()
        self.validation_middleware = ValidationMiddleware()
    
    def secure_and_validate(
        self,
        # Security parameters
        audit_event_type: AuditEventType = None,
        security_level: SecurityLevel = SecurityLevel.MEDIUM,
        strict_sanitization: bool = False,
        monitor_anomalies: bool = True,
        sensitive_params: List[str] = None,
        
        # Validation parameters
        rate_limit_config: Dict[str, Any] = None,
        permission_config: Dict[str, Any] = None,
        input_validation: Dict[str, Callable] = None,
        sanitize_inputs: bool = True
    ):
        """
        Combined security and validation decorator.
        
        This decorator applies both security enhancements and validation
        in the correct order for comprehensive protection.
        """
        def decorator(func):
            # Apply security middleware first
            secured_func = self.security_middleware.secure_command(
                audit_event_type=audit_event_type,
                security_level=security_level,
                sanitize_inputs=sanitize_inputs,
                strict_sanitization=strict_sanitization,
                monitor_anomalies=monitor_anomalies,
                log_access=True,
                sensitive_params=sensitive_params
            )(func)
            
            # Then apply validation middleware
            validated_func = self.validation_middleware.validate_command(
                rate_limit_config=rate_limit_config,
                permission_config=permission_config,
                input_validation=input_validation,
                sanitize_inputs=False  # Already handled by security middleware
            )(secured_func)
            
            return validated_func
        
        return decorator


# Global middleware instance
_security_middleware: Optional[SecurityMiddleware] = None
_combined_middleware: Optional[CombinedSecurityMiddleware] = None


def get_security_middleware() -> SecurityMiddleware:
    """Get global security middleware instance."""
    global _security_middleware
    if _security_middleware is None:
        _security_middleware = SecurityMiddleware()
    return _security_middleware


def get_combined_middleware() -> CombinedSecurityMiddleware:
    """Get global combined middleware instance."""
    global _combined_middleware
    if _combined_middleware is None:
        _combined_middleware = CombinedSecurityMiddleware()
    return _combined_middleware


# Convenience decorators for common security patterns
def secure_prediction_command(
    audit_event_type: AuditEventType = AuditEventType.PREDICTION_CREATED,
    security_level: SecurityLevel = SecurityLevel.HIGH,
    **kwargs
):
    """Security decorator for prediction-related commands."""
    return get_security_middleware().secure_command(
        audit_event_type=audit_event_type,
        security_level=security_level,
        strict_sanitization=True,
        monitor_anomalies=True,
        **kwargs
    )


def secure_betting_command(
    audit_event_type: AuditEventType = AuditEventType.BET_PLACED,
    security_level: SecurityLevel = SecurityLevel.HIGH,
    **kwargs
):
    """Security decorator for betting-related commands."""
    return get_security_middleware().secure_command(
        audit_event_type=audit_event_type,
        security_level=security_level,
        strict_sanitization=True,
        monitor_anomalies=True,
        sensitive_params=['amount'],
        **kwargs
    )


def secure_admin_command(
    audit_event_type: AuditEventType = AuditEventType.ADMIN_ACTION,
    security_level: SecurityLevel = SecurityLevel.CRITICAL,
    **kwargs
):
    """Security decorator for admin commands."""
    return get_combined_middleware().secure_and_validate(
        audit_event_type=audit_event_type,
        security_level=security_level,
        strict_sanitization=True,
        monitor_anomalies=True,
        permission_config={'admin_only': True},
        rate_limit_config={'limit': 5, 'window': 300},  # 5 per 5 minutes
        **kwargs
    )


def secure_user_command(
    audit_event_type: AuditEventType = None,
    security_level: SecurityLevel = SecurityLevel.MEDIUM,
    **kwargs
):
    """Security decorator for regular user commands."""
    return get_combined_middleware().secure_and_validate(
        audit_event_type=audit_event_type,
        security_level=security_level,
        strict_sanitization=False,
        monitor_anomalies=True,
        rate_limit_config={'limit': 10, 'window': 60},  # 10 per minute
        **kwargs
    )