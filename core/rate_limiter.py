"""
Rate limiting system with sliding window algorithm.

This module provides comprehensive rate limiting functionality for Discord commands
and API operations, supporting per-user and per-guild limits with admin bypass.
"""

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Set, Tuple, Any, List
from datetime import datetime, timedelta
import logging

from config.settings import get_settings


class RateLimitType(str, Enum):
    """Types of rate limits."""
    USER_REQUESTS = "user_requests"
    USER_BETS = "user_bets"
    USER_PREDICTIONS = "user_predictions"
    GUILD_REQUESTS = "guild_requests"
    GUILD_PREDICTIONS = "guild_predictions"


@dataclass
class RateLimitInfo:
    """Information about a rate limit status."""
    limit: int
    remaining: int
    reset_time: float
    window_seconds: int
    is_exceeded: bool = False
    
    @property
    def reset_datetime(self) -> datetime:
        """Get reset time as datetime object."""
        return datetime.fromtimestamp(self.reset_time)
    
    @property
    def seconds_until_reset(self) -> int:
        """Get seconds until rate limit resets."""
        return max(0, int(self.reset_time - time.time()))


@dataclass
class RateLimitWindow:
    """Sliding window for rate limiting."""
    requests: deque = field(default_factory=deque)
    limit: int = 0
    window_seconds: int = 60
    
    def add_request(self, timestamp: float = None) -> None:
        """Add a request to the window."""
        if timestamp is None:
            timestamp = time.time()
        self.requests.append(timestamp)
        self._cleanup_old_requests()
    
    def _cleanup_old_requests(self) -> None:
        """Remove requests outside the current window."""
        current_time = time.time()
        cutoff_time = current_time - self.window_seconds
        
        while self.requests and self.requests[0] < cutoff_time:
            self.requests.popleft()
    
    def get_current_count(self) -> int:
        """Get current number of requests in the window."""
        self._cleanup_old_requests()
        return len(self.requests)
    
    def is_exceeded(self) -> bool:
        """Check if rate limit is exceeded."""
        return self.get_current_count() >= self.limit
    
    def get_reset_time(self) -> float:
        """Get the time when the oldest request will expire."""
        self._cleanup_old_requests()
        if not self.requests:
            return time.time()
        return self.requests[0] + self.window_seconds


class RateLimiter:
    """
    Rate limiter with sliding window algorithm.
    
    Supports per-user and per-guild rate limiting with different limits
    for different types of operations. Includes admin bypass functionality
    and comprehensive monitoring.
    """
    
    def __init__(self):
        """Initialize the rate limiter."""
        self.settings = get_settings()
        self.logger = logging.getLogger(__name__)
        
        # Rate limit windows for different types
        self._user_windows: Dict[Tuple[int, RateLimitType], RateLimitWindow] = {}
        self._guild_windows: Dict[Tuple[int, RateLimitType], RateLimitWindow] = {}
        
        # Admin bypass list
        self._admin_users: Set[int] = set()
        self._admin_roles: Set[int] = set()
        
        # Statistics
        self._stats = {
            'total_requests': 0,
            'blocked_requests': 0,
            'bypassed_requests': 0,
            'rate_limit_violations': defaultdict(int)
        }
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self) -> None:
        """Start the periodic cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self) -> None:
        """Periodically clean up old rate limit windows."""
        while True:
            try:
                await asyncio.sleep(self.settings.rate_limit.rate_limit_cleanup_interval)
                await self._cleanup_old_windows()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in rate limiter cleanup: {e}")
    
    async def _cleanup_old_windows(self) -> None:
        """Clean up old rate limit windows."""
        current_time = time.time()
        
        # Clean up user windows
        expired_user_keys = []
        for key, window in self._user_windows.items():
            window._cleanup_old_requests()
            if not window.requests:
                expired_user_keys.append(key)
        
        for key in expired_user_keys:
            del self._user_windows[key]
        
        # Clean up guild windows
        expired_guild_keys = []
        for key, window in self._guild_windows.items():
            window._cleanup_old_requests()
            if not window.requests:
                expired_guild_keys.append(key)
        
        for key in expired_guild_keys:
            del self._guild_windows[key]
        
        self.logger.debug(f"Cleaned up {len(expired_user_keys)} user windows and {len(expired_guild_keys)} guild windows")
    
    def add_admin_user(self, user_id: int) -> None:
        """Add a user to the admin bypass list."""
        self._admin_users.add(user_id)
        self.logger.info(f"Added user {user_id} to rate limit bypass list")
    
    def remove_admin_user(self, user_id: int) -> None:
        """Remove a user from the admin bypass list."""
        self._admin_users.discard(user_id)
        self.logger.info(f"Removed user {user_id} from rate limit bypass list")
    
    def add_admin_role(self, role_id: int) -> None:
        """Add a role to the admin bypass list."""
        self._admin_roles.add(role_id)
        self.logger.info(f"Added role {role_id} to rate limit bypass list")
    
    def remove_admin_role(self, role_id: int) -> None:
        """Remove a role from the admin bypass list."""
        self._admin_roles.discard(role_id)
        self.logger.info(f"Removed role {role_id} from rate limit bypass list")
    
    def _is_admin_bypass(self, user_id: int, user_roles: Optional[List[int]] = None) -> bool:
        """Check if user should bypass rate limits."""
        if not self.settings.rate_limit.admin_bypass_enabled:
            return False
        
        # Check user bypass
        if user_id in self._admin_users:
            return True
        
        # Check role bypass
        if user_roles:
            for role_id in user_roles:
                if role_id in self._admin_roles:
                    return True
        
        return False
    
    def _get_rate_limit_config(self, limit_type: RateLimitType) -> Tuple[int, int]:
        """Get rate limit configuration for a specific type."""
        config_map = {
            RateLimitType.USER_REQUESTS: (
                self.settings.rate_limit.user_requests_per_minute,
                self.settings.rate_limit.rate_limit_window_seconds
            ),
            RateLimitType.USER_BETS: (
                self.settings.rate_limit.user_bets_per_minute,
                self.settings.rate_limit.rate_limit_window_seconds
            ),
            RateLimitType.USER_PREDICTIONS: (
                self.settings.rate_limit.user_predictions_per_hour,
                3600  # 1 hour in seconds
            ),
            RateLimitType.GUILD_REQUESTS: (
                self.settings.rate_limit.guild_requests_per_minute,
                self.settings.rate_limit.rate_limit_window_seconds
            ),
            RateLimitType.GUILD_PREDICTIONS: (
                self.settings.rate_limit.guild_predictions_per_hour,
                3600  # 1 hour in seconds
            )
        }
        
        return config_map.get(limit_type, (10, 60))  # Default fallback
    
    def _get_or_create_user_window(self, user_id: int, limit_type: RateLimitType) -> RateLimitWindow:
        """Get or create a rate limit window for a user."""
        key = (user_id, limit_type)
        
        if key not in self._user_windows:
            limit, window_seconds = self._get_rate_limit_config(limit_type)
            self._user_windows[key] = RateLimitWindow(
                limit=limit,
                window_seconds=window_seconds
            )
        
        return self._user_windows[key]
    
    def _get_or_create_guild_window(self, guild_id: int, limit_type: RateLimitType) -> RateLimitWindow:
        """Get or create a rate limit window for a guild."""
        key = (guild_id, limit_type)
        
        if key not in self._guild_windows:
            limit, window_seconds = self._get_rate_limit_config(limit_type)
            self._guild_windows[key] = RateLimitWindow(
                limit=limit,
                window_seconds=window_seconds
            )
        
        return self._guild_windows[key]
    
    async def check_rate_limit(
        self,
        user_id: int,
        guild_id: Optional[int] = None,
        limit_type: RateLimitType = RateLimitType.USER_REQUESTS,
        user_roles: Optional[List[int]] = None
    ) -> RateLimitInfo:
        """
        Check if a request should be rate limited.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID (optional)
            limit_type: Type of rate limit to check
            user_roles: List of user role IDs for admin bypass check
            
        Returns:
            RateLimitInfo: Information about the rate limit status
        """
        self._stats['total_requests'] += 1
        
        # Check admin bypass
        if self._is_admin_bypass(user_id, user_roles):
            self._stats['bypassed_requests'] += 1
            limit, window_seconds = self._get_rate_limit_config(limit_type)
            return RateLimitInfo(
                limit=limit,
                remaining=limit,
                reset_time=time.time() + window_seconds,
                window_seconds=window_seconds,
                is_exceeded=False
            )
        
        # Check user rate limit
        user_window = self._get_or_create_user_window(user_id, limit_type)
        user_exceeded = user_window.is_exceeded()
        
        # Check guild rate limit if guild_id provided
        guild_exceeded = False
        guild_window = None
        if guild_id and limit_type in [RateLimitType.GUILD_REQUESTS, RateLimitType.GUILD_PREDICTIONS]:
            guild_limit_type = limit_type
            guild_window = self._get_or_create_guild_window(guild_id, guild_limit_type)
            guild_exceeded = guild_window.is_exceeded()
        
        # Determine if rate limit is exceeded
        is_exceeded = user_exceeded or guild_exceeded
        
        if is_exceeded:
            self._stats['blocked_requests'] += 1
            self._stats['rate_limit_violations'][limit_type] += 1
            
            # Log rate limit violation
            self.logger.warning(
                f"Rate limit exceeded for user {user_id} (guild: {guild_id}), "
                f"type: {limit_type}, user_exceeded: {user_exceeded}, guild_exceeded: {guild_exceeded}"
            )
        
        # Use user window for rate limit info (primary limit)
        return RateLimitInfo(
            limit=user_window.limit,
            remaining=max(0, user_window.limit - user_window.get_current_count()),
            reset_time=user_window.get_reset_time(),
            window_seconds=user_window.window_seconds,
            is_exceeded=is_exceeded
        )
    
    async def consume_rate_limit(
        self,
        user_id: int,
        guild_id: Optional[int] = None,
        limit_type: RateLimitType = RateLimitType.USER_REQUESTS,
        user_roles: Optional[List[int]] = None
    ) -> RateLimitInfo:
        """
        Consume a rate limit slot (record the request).
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID (optional)
            limit_type: Type of rate limit to consume
            user_roles: List of user role IDs for admin bypass check
            
        Returns:
            RateLimitInfo: Information about the rate limit status after consumption
        """
        # Check current status
        rate_limit_info = await self.check_rate_limit(user_id, guild_id, limit_type, user_roles)
        
        # If not exceeded and not bypassed, record the request
        if not rate_limit_info.is_exceeded and not self._is_admin_bypass(user_id, user_roles):
            # Add to user window
            user_window = self._get_or_create_user_window(user_id, limit_type)
            user_window.add_request()
            
            # Add to guild window if applicable
            if guild_id and limit_type in [RateLimitType.GUILD_REQUESTS, RateLimitType.GUILD_PREDICTIONS]:
                guild_window = self._get_or_create_guild_window(guild_id, limit_type)
                guild_window.add_request()
            
            # Update remaining count
            rate_limit_info.remaining = max(0, user_window.limit - user_window.get_current_count())
        
        return rate_limit_info
    
    def get_user_rate_limit_status(self, user_id: int, limit_type: RateLimitType) -> RateLimitInfo:
        """Get current rate limit status for a user."""
        user_window = self._get_or_create_user_window(user_id, limit_type)
        
        return RateLimitInfo(
            limit=user_window.limit,
            remaining=max(0, user_window.limit - user_window.get_current_count()),
            reset_time=user_window.get_reset_time(),
            window_seconds=user_window.window_seconds,
            is_exceeded=user_window.is_exceeded()
        )
    
    def get_guild_rate_limit_status(self, guild_id: int, limit_type: RateLimitType) -> RateLimitInfo:
        """Get current rate limit status for a guild."""
        guild_window = self._get_or_create_guild_window(guild_id, limit_type)
        
        return RateLimitInfo(
            limit=guild_window.limit,
            remaining=max(0, guild_window.limit - guild_window.get_current_count()),
            reset_time=guild_window.get_reset_time(),
            window_seconds=guild_window.window_seconds,
            is_exceeded=guild_window.is_exceeded()
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            'total_requests': self._stats['total_requests'],
            'blocked_requests': self._stats['blocked_requests'],
            'bypassed_requests': self._stats['bypassed_requests'],
            'block_rate': (
                self._stats['blocked_requests'] / max(1, self._stats['total_requests'])
            ) * 100,
            'bypass_rate': (
                self._stats['bypassed_requests'] / max(1, self._stats['total_requests'])
            ) * 100,
            'violations_by_type': dict(self._stats['rate_limit_violations']),
            'active_user_windows': len(self._user_windows),
            'active_guild_windows': len(self._guild_windows),
            'admin_users_count': len(self._admin_users),
            'admin_roles_count': len(self._admin_roles)
        }
    
    def reset_statistics(self) -> None:
        """Reset rate limiter statistics."""
        self._stats = {
            'total_requests': 0,
            'blocked_requests': 0,
            'bypassed_requests': 0,
            'rate_limit_violations': defaultdict(int)
        }
        self.logger.info("Rate limiter statistics reset")
    
    async def shutdown(self) -> None:
        """Shutdown the rate limiter and cleanup resources."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Rate limiter shutdown complete")


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


async def shutdown_rate_limiter() -> None:
    """Shutdown the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is not None:
        await _rate_limiter.shutdown()
        _rate_limiter = None