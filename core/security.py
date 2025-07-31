"""
Comprehensive security enhancements for the Discord Prediction Market Bot.

This module provides:
- Advanced input sanitization and validation
- Audit logging for critical operations
- Secure token handling for external APIs
- Data encryption for sensitive information
- Security monitoring and threat detection
"""

import hashlib
import hmac
import secrets
import time
import re
import html
import base64
import json
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .logging_manager import get_logger, LogContext
from .exceptions import SecurityError, ValidationError


class SecurityLevel(str, Enum):
    """Security levels for different operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditEventType(str, Enum):
    """Types of audit events."""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    PREDICTION_CREATED = "prediction_created"
    PREDICTION_RESOLVED = "prediction_resolved"
    BET_PLACED = "bet_placed"
    BET_REFUNDED = "bet_refunded"
    POINTS_TRANSFERRED = "points_transferred"
    ADMIN_ACTION = "admin_action"
    SECURITY_VIOLATION = "security_violation"
    API_ACCESS = "api_access"
    DATA_ACCESS = "data_access"
    CONFIGURATION_CHANGE = "configuration_change"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


@dataclass
class AuditEvent:
    """Audit event data structure."""
    event_type: AuditEventType
    user_id: Optional[int]
    guild_id: Optional[int]
    timestamp: datetime
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    security_level: SecurityLevel = SecurityLevel.MEDIUM
    success: bool = True
    error_message: Optional[str] = None


class InputSanitizer:
    """Advanced input sanitization and validation."""
    
    # Comprehensive patterns for detecting malicious content
    SCRIPT_PATTERNS = [
        re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'data:text/html', re.IGNORECASE),
        re.compile(r'vbscript:', re.IGNORECASE),
        re.compile(r'on\w+\s*=', re.IGNORECASE),
        re.compile(r'<iframe[^>]*>', re.IGNORECASE),
        re.compile(r'<object[^>]*>', re.IGNORECASE),
        re.compile(r'<embed[^>]*>', re.IGNORECASE),
        re.compile(r'<link[^>]*>', re.IGNORECASE),
        re.compile(r'<meta[^>]*>', re.IGNORECASE),
        re.compile(r'<style[^>]*>.*?</style>', re.IGNORECASE | re.DOTALL),
    ]
    
    SQL_INJECTION_PATTERNS = [
        re.compile(r'\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b', re.IGNORECASE),
        re.compile(r'[\'";]', re.IGNORECASE),
        re.compile(r'--[^\r\n]*', re.IGNORECASE),
        re.compile(r'/\*.*?\*/', re.IGNORECASE | re.DOTALL),
        re.compile(r'\bor\s+1\s*=\s*1\b', re.IGNORECASE),
        re.compile(r'\band\s+1\s*=\s*1\b', re.IGNORECASE),
        re.compile(r'\bxp_cmdshell\b', re.IGNORECASE),
    ]
    
    COMMAND_INJECTION_PATTERNS = [
        re.compile(r'[;&|`$(){}[\]<>]'),
        re.compile(r'\b(cat|ls|pwd|whoami|id|uname|ps|netstat|ifconfig)\b', re.IGNORECASE),
        re.compile(r'\.\./', re.IGNORECASE),
        re.compile(r'/etc/passwd', re.IGNORECASE),
        re.compile(r'/proc/', re.IGNORECASE),
    ]
    
    LDAP_INJECTION_PATTERNS = [
        re.compile(r'[()&|!*]'),
        re.compile(r'\\\*'),
        re.compile(r'\\\('),
        re.compile(r'\\\)'),
    ]
    
    # Allowed characters for different input types
    SAFE_USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_.-]{1,32}$')
    SAFE_FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9_.-]{1,255}$')
    SAFE_TEXT_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_.,!?()]+$')
    
    @staticmethod
    def sanitize_text(
        text: str,
        max_length: int = None,
        allow_html: bool = False,
        strict_mode: bool = False
    ) -> str:
        """
        Comprehensive text sanitization.
        
        Args:
            text: Input text to sanitize
            max_length: Maximum allowed length
            allow_html: Whether to allow HTML tags (escaped)
            strict_mode: Enable strict sanitization mode
            
        Returns:
            Sanitized text
            
        Raises:
            SecurityError: If malicious content is detected in strict mode
        """
        if not isinstance(text, str):
            text = str(text)
        
        original_text = text
        
        # Remove null bytes and control characters
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Normalize Unicode
        text = text.encode('utf-8', errors='ignore').decode('utf-8')
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Check for malicious patterns
        malicious_patterns_found = []
        
        # Check for script injection
        for pattern in InputSanitizer.SCRIPT_PATTERNS:
            if pattern.search(text):
                malicious_patterns_found.append("script_injection")
                text = pattern.sub('', text)
        
        # Check for SQL injection
        for pattern in InputSanitizer.SQL_INJECTION_PATTERNS:
            if pattern.search(text):
                malicious_patterns_found.append("sql_injection")
                if strict_mode:
                    raise SecurityError(
                        "SQL injection attempt detected",
                        details={"original_text": original_text, "pattern": pattern.pattern}
                    )
                text = pattern.sub('', text)
        
        # Check for command injection
        for pattern in InputSanitizer.COMMAND_INJECTION_PATTERNS:
            if pattern.search(text):
                malicious_patterns_found.append("command_injection")
                if strict_mode:
                    raise SecurityError(
                        "Command injection attempt detected",
                        details={"original_text": original_text, "pattern": pattern.pattern}
                    )
                text = pattern.sub('', text)
        
        # Check for LDAP injection
        for pattern in InputSanitizer.LDAP_INJECTION_PATTERNS:
            if pattern.search(text):
                malicious_patterns_found.append("ldap_injection")
                text = pattern.sub('', text)
        
        # Handle HTML content
        if not allow_html:
            # Remove HTML tags completely
            text = re.sub(r'<[^>]*>', '', text)
            
            # Remove remaining script-related content
            text = re.sub(r'alert\([^)]*\)', '', text, flags=re.IGNORECASE)
            text = re.sub(r'script[^>]*', '', text, flags=re.IGNORECASE)
        else:
            # Escape HTML entities
            text = html.escape(text)
        
        # Truncate if max_length specified
        if max_length and len(text) > max_length:
            text = text[:max_length].rstrip()
        
        # Log security violations if patterns were found
        if malicious_patterns_found:
            try:
                logger = get_logger(__name__)
                logger.warning(
                    "Malicious patterns detected in input",
                    extra={
                        'patterns_found': malicious_patterns_found,
                        'original_length': len(original_text),
                        'sanitized_length': len(text),
                        'strict_mode': strict_mode
                    }
                )
            except Exception:
                # Fallback if logging is not available (e.g., during testing)
                pass
        
        return text
    
    @staticmethod
    def validate_discord_id(discord_id: Union[str, int]) -> int:
        """Validate and sanitize Discord ID."""
        try:
            id_str = str(discord_id).strip()
            
            # Check for basic format
            if not re.match(r'^\d{17,20}$', id_str):
                raise SecurityError("Invalid Discord ID format")
            
            id_int = int(id_str)
            if id_int <= 0:
                raise SecurityError("Discord ID must be positive")
            
            return id_int
            
        except (ValueError, TypeError) as e:
            raise SecurityError(f"Invalid Discord ID: {str(e)}")
    
    @staticmethod
    def validate_filename(filename: str) -> str:
        """Validate and sanitize filename."""
        if not filename or not filename.strip():
            raise SecurityError("Filename cannot be empty")
        
        filename = filename.strip()
        
        # Check for path traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            raise SecurityError("Path traversal attempt detected in filename")
        
        # Check against safe pattern
        if not InputSanitizer.SAFE_FILENAME_PATTERN.match(filename):
            raise SecurityError("Filename contains invalid characters")
        
        return filename
    
    @staticmethod
    def validate_url(url: str) -> str:
        """Validate and sanitize URL."""
        if not url or not url.strip():
            raise SecurityError("URL cannot be empty")
        
        url = url.strip()
        
        # Check for basic URL format
        if not re.match(r'^https?://', url, re.IGNORECASE):
            raise SecurityError("URL must use HTTP or HTTPS protocol")
        
        # Check for suspicious patterns
        suspicious_patterns = [
            r'javascript:',
            r'data:',
            r'file:',
            r'ftp:',
            r'localhost',
            r'127\.0\.0\.1',
            r'0\.0\.0\.0',
            r'::1',
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                raise SecurityError(f"Suspicious URL pattern detected: {pattern}")
        
        return url


class TokenManager:
    """Secure token handling for external APIs."""
    
    def __init__(self, encryption_key: Optional[bytes] = None):
        """Initialize token manager with encryption key."""
        if encryption_key is None:
            # Generate a new key if none provided
            encryption_key = Fernet.generate_key()
        
        self.cipher = Fernet(encryption_key)
        try:
            self.logger = get_logger(__name__)
        except Exception:
            self.logger = None
    
    def encrypt_token(self, token: str) -> str:
        """Encrypt a token for secure storage."""
        try:
            token_bytes = token.encode('utf-8')
            encrypted_token = self.cipher.encrypt(token_bytes)
            return base64.urlsafe_b64encode(encrypted_token).decode('utf-8')
        except Exception as e:
            if self.logger:
                self.logger.error(f"Token encryption failed: {str(e)}")
            raise SecurityError("Failed to encrypt token")
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt a token for use."""
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_token.encode('utf-8'))
            decrypted_token = self.cipher.decrypt(encrypted_bytes)
            return decrypted_token.decode('utf-8')
        except Exception as e:
            if self.logger:
                self.logger.error(f"Token decryption failed: {str(e)}")
            raise SecurityError("Failed to decrypt token")
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Generate a cryptographically secure random token."""
        return secrets.token_urlsafe(length)
    
    def hash_token(self, token: str, salt: Optional[bytes] = None) -> tuple[str, bytes]:
        """Hash a token with salt for secure comparison."""
        if salt is None:
            salt = secrets.token_bytes(32)
        
        # Use PBKDF2 for key derivation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        token_hash = kdf.derive(token.encode('utf-8'))
        return base64.urlsafe_b64encode(token_hash).decode('utf-8'), salt
    
    def verify_token_hash(self, token: str, token_hash: str, salt: bytes) -> bool:
        """Verify a token against its hash."""
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            
            expected_hash = kdf.derive(token.encode('utf-8'))
            actual_hash = base64.urlsafe_b64decode(token_hash.encode('utf-8'))
            
            return hmac.compare_digest(expected_hash, actual_hash)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Token verification failed: {str(e)}")
            return False


class DataEncryption:
    """Data encryption for sensitive information."""
    
    def __init__(self, password: str):
        """Initialize encryption with password-derived key."""
        self.password = password.encode('utf-8')
        try:
            self.logger = get_logger(__name__)
        except Exception:
            self.logger = None
    
    def _derive_key(self, salt: bytes) -> bytes:
        """Derive encryption key from password and salt."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(self.password))
    
    def encrypt_data(self, data: Union[str, dict, list]) -> str:
        """Encrypt data for secure storage."""
        try:
            # Convert data to JSON string if not already string
            if isinstance(data, (dict, list)):
                data_str = json.dumps(data, ensure_ascii=False)
            else:
                data_str = str(data)
            
            # Generate salt and derive key
            salt = secrets.token_bytes(16)
            key = self._derive_key(salt)
            
            # Encrypt data
            cipher = Fernet(key)
            encrypted_data = cipher.encrypt(data_str.encode('utf-8'))
            
            # Combine salt and encrypted data
            combined = salt + encrypted_data
            return base64.urlsafe_b64encode(combined).decode('utf-8')
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Data encryption failed: {str(e)}")
            raise SecurityError("Failed to encrypt data")
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt data from secure storage."""
        try:
            # Decode and separate salt from encrypted data
            combined = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            salt = combined[:16]
            encrypted_bytes = combined[16:]
            
            # Derive key and decrypt
            key = self._derive_key(salt)
            cipher = Fernet(key)
            decrypted_bytes = cipher.decrypt(encrypted_bytes)
            
            return decrypted_bytes.decode('utf-8')
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Data decryption failed: {str(e)}")
            raise SecurityError("Failed to decrypt data")
    
    def encrypt_sensitive_fields(self, data: dict, sensitive_fields: List[str]) -> dict:
        """Encrypt specific fields in a dictionary."""
        encrypted_data = data.copy()
        
        for field in sensitive_fields:
            if field in encrypted_data and encrypted_data[field] is not None:
                encrypted_data[field] = self.encrypt_data(encrypted_data[field])
        
        return encrypted_data
    
    def decrypt_sensitive_fields(self, data: dict, sensitive_fields: List[str]) -> dict:
        """Decrypt specific fields in a dictionary."""
        decrypted_data = data.copy()
        
        for field in sensitive_fields:
            if field in decrypted_data and decrypted_data[field] is not None:
                try:
                    decrypted_data[field] = self.decrypt_data(decrypted_data[field])
                except SecurityError:
                    # If decryption fails, field might not be encrypted
                    pass
        
        return decrypted_data


class AuditLogger:
    """Comprehensive audit logging for critical operations."""
    
    def __init__(self):
        self.logger = get_logger("audit")
        self.security_logger = get_logger("security")
    
    def log_audit_event(self, event: AuditEvent) -> None:
        """Log an audit event."""
        try:
            # Create log context
            context = LogContext(
                correlation_id=event.correlation_id,
                user_id=event.user_id,
                guild_id=event.guild_id,
                operation=event.event_type.value,
                extra={
                    'audit_event': True,
                    'event_type': event.event_type.value,
                    'security_level': event.security_level.value,
                    'success': event.success,
                    'timestamp': event.timestamp.isoformat(),
                    'ip_address': event.ip_address,
                    'user_agent': event.user_agent,
                    'session_id': event.session_id,
                    'details': event.details
                }
            )
            
            # Log to audit logger
            message = f"Audit Event: {event.event_type.value}"
            if not event.success and event.error_message:
                message += f" - Failed: {event.error_message}"
            
            self.logger.info(message, extra=context.extra)
            
            # Log security events to security logger as well
            if event.security_level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]:
                self.security_logger.warning(
                    f"High-security audit event: {event.event_type.value}",
                    extra=context.extra
                )
            
        except Exception as e:
            # Fallback logging if audit logging fails
            self.logger.error(f"Failed to log audit event: {str(e)}")
    
    def log_user_action(
        self,
        event_type: AuditEventType,
        user_id: int,
        guild_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        security_level: SecurityLevel = SecurityLevel.MEDIUM,
        **kwargs
    ) -> None:
        """Log a user action audit event."""
        event = AuditEvent(
            event_type=event_type,
            user_id=user_id,
            guild_id=guild_id,
            timestamp=datetime.utcnow(),
            details=details or {},
            success=success,
            error_message=error_message,
            security_level=security_level,
            **kwargs
        )
        
        self.log_audit_event(event)
    
    def log_security_violation(
        self,
        violation_type: str,
        user_id: Optional[int] = None,
        guild_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """Log a security violation."""
        event = AuditEvent(
            event_type=AuditEventType.SECURITY_VIOLATION,
            user_id=user_id,
            guild_id=guild_id,
            timestamp=datetime.utcnow(),
            details={
                'violation_type': violation_type,
                **(details or {})
            },
            success=False,
            security_level=SecurityLevel.HIGH,
            **kwargs
        )
        
        self.log_audit_event(event)
    
    def log_api_access(
        self,
        api_endpoint: str,
        user_id: Optional[int] = None,
        success: bool = True,
        response_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """Log API access."""
        event = AuditEvent(
            event_type=AuditEventType.API_ACCESS,
            user_id=user_id,
            guild_id=None,
            timestamp=datetime.utcnow(),
            details={
                'api_endpoint': api_endpoint,
                'response_code': response_code,
                **(details or {})
            },
            success=success,
            security_level=SecurityLevel.LOW,
            **kwargs
        )
        
        self.log_audit_event(event)


class SecurityMonitor:
    """Security monitoring and threat detection."""
    
    def __init__(self):
        try:
            self.logger = get_logger(__name__)
            self.audit_logger = AuditLogger()
        except Exception:
            self.logger = None
            self.audit_logger = None
        self.suspicious_activity = {}  # Track suspicious activity by user
        self.failed_attempts = {}  # Track failed attempts
    
    def track_failed_attempt(
        self,
        user_id: int,
        attempt_type: str,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Track failed attempts and detect suspicious patterns.
        
        Returns:
            True if user should be flagged for suspicious activity
        """
        now = time.time()
        key = f"{user_id}:{attempt_type}"
        
        if key not in self.failed_attempts:
            self.failed_attempts[key] = []
        
        # Add current attempt
        self.failed_attempts[key].append(now)
        
        # Remove attempts older than 1 hour
        cutoff_time = now - 3600
        self.failed_attempts[key] = [
            attempt_time for attempt_time in self.failed_attempts[key]
            if attempt_time > cutoff_time
        ]
        
        # Check for suspicious patterns
        recent_attempts = len(self.failed_attempts[key])
        
        # Flag if more than 5 failed attempts in 1 hour
        if recent_attempts > 5:
            if self.audit_logger:
                self.audit_logger.log_security_violation(
                    violation_type="excessive_failed_attempts",
                    user_id=user_id,
                    details={
                        'attempt_type': attempt_type,
                        'failed_attempts_count': recent_attempts,
                        'time_window_hours': 1,
                        **(details or {})
                    }
                )
            return True
        
        return False
    
    def detect_rate_limit_abuse(
        self,
        user_id: int,
        command: str,
        current_rate: int,
        limit: int
    ) -> None:
        """Detect and log rate limit abuse."""
        if current_rate > limit * 1.5:  # 50% over the limit
            if self.audit_logger:
                self.audit_logger.log_security_violation(
                    violation_type="rate_limit_abuse",
                    user_id=user_id,
                    details={
                        'command': command,
                        'current_rate': current_rate,
                        'limit': limit,
                        'abuse_factor': current_rate / limit
                    }
                )
    
    def detect_input_anomalies(
        self,
        user_id: int,
        input_data: str,
        input_type: str
    ) -> None:
        """Detect anomalies in user input."""
        anomalies = []
        
        # Check for unusually long input
        if len(input_data) > 10000:
            anomalies.append("excessive_length")
        
        # Check for high entropy (possible encoded data)
        entropy = self._calculate_entropy(input_data)
        if entropy > 7.0:  # High entropy threshold
            anomalies.append("high_entropy")
        
        # Check for repeated patterns
        if self._has_repeated_patterns(input_data):
            anomalies.append("repeated_patterns")
        
        # Check for binary data
        if self._contains_binary_data(input_data):
            anomalies.append("binary_data")
        
        if anomalies:
            if self.audit_logger:
                self.audit_logger.log_security_violation(
                    violation_type="input_anomaly",
                    user_id=user_id,
                    details={
                        'input_type': input_type,
                        'input_length': len(input_data),
                        'anomalies': anomalies,
                        'entropy': entropy
                    }
                )
    
    def _calculate_entropy(self, data: str) -> float:
        """Calculate Shannon entropy of string."""
        if not data:
            return 0
        
        # Count character frequencies
        char_counts = {}
        for char in data:
            char_counts[char] = char_counts.get(char, 0) + 1
        
        # Calculate entropy
        entropy = 0
        data_len = len(data)
        for count in char_counts.values():
            probability = count / data_len
            if probability > 0:
                entropy -= probability * (probability.bit_length() - 1)
        
        return entropy
    
    def _has_repeated_patterns(self, data: str, min_pattern_length: int = 10) -> bool:
        """Check for repeated patterns in string."""
        if len(data) < min_pattern_length * 2:
            return False
        
        for pattern_length in range(min_pattern_length, len(data) // 2):
            pattern = data[:pattern_length]
            if data.count(pattern) > 3:  # Pattern repeats more than 3 times
                return True
        
        return False
    
    def _contains_binary_data(self, data: str) -> bool:
        """Check if string contains binary data."""
        try:
            # Try to encode as UTF-8
            data.encode('utf-8')
            
            # Check for high percentage of non-printable characters
            non_printable = sum(1 for char in data if ord(char) < 32 or ord(char) > 126)
            return (non_printable / len(data)) > 0.3 if data else False
            
        except UnicodeEncodeError:
            return True


# Global instances
_token_manager: Optional[TokenManager] = None
_data_encryption: Optional[DataEncryption] = None
_audit_logger: Optional[AuditLogger] = None
_security_monitor: Optional[SecurityMonitor] = None


def get_token_manager(encryption_key: Optional[bytes] = None) -> TokenManager:
    """Get global token manager instance."""
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager(encryption_key)
    return _token_manager


def get_data_encryption(password: Optional[str] = None) -> DataEncryption:
    """Get global data encryption instance."""
    global _data_encryption
    if _data_encryption is None:
        if password is None:
            # Use a default password from environment or generate one
            import os
            password = os.getenv('ENCRYPTION_PASSWORD', 'default_password_change_in_production')
        _data_encryption = DataEncryption(password)
    return _data_encryption


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def get_security_monitor() -> SecurityMonitor:
    """Get global security monitor instance."""
    global _security_monitor
    if _security_monitor is None:
        _security_monitor = SecurityMonitor()
    return _security_monitor


# Convenience functions for common security operations
def sanitize_user_input(
    text: str,
    max_length: int = None,
    strict_mode: bool = False
) -> str:
    """Sanitize user input with security monitoring."""
    try:
        return InputSanitizer.sanitize_text(text, max_length, strict_mode=strict_mode)
    except SecurityError as e:
        # Log security violation
        get_audit_logger().log_security_violation(
            violation_type="input_sanitization_failure",
            details={
                'original_text_length': len(text),
                'error': str(e),
                'strict_mode': strict_mode
            }
        )
        raise


def audit_user_action(
    event_type: AuditEventType,
    user_id: int,
    guild_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    **kwargs
) -> None:
    """Audit a user action."""
    get_audit_logger().log_user_action(
        event_type=event_type,
        user_id=user_id,
        guild_id=guild_id,
        details=details,
        **kwargs
    )


def encrypt_sensitive_data(data: Union[str, dict, list]) -> str:
    """Encrypt sensitive data."""
    return get_data_encryption().encrypt_data(data)


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """Decrypt sensitive data."""
    return get_data_encryption().decrypt_data(encrypted_data)