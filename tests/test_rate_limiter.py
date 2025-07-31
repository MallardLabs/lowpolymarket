"""
Tests for the rate limiting system.
"""

import asyncio
import pytest
import pytest_asyncio
import time
import os
from unittest.mock import Mock, patch

# Set test environment
os.environ.update({
    'DISCORD_TOKEN': 'test_token_12345678901234567890123456789012345678901234567890',
    'DATABASE_URL': 'postgresql://test:test@localhost:5432/test_db',
    'DATABASE_SUPABASE_URL': 'https://test.supabase.co',
    'DATABASE_SUPABASE_PUBLISHABLE_KEY': 'sb_publishable_test_key',
    'DATABASE_SUPABASE_SECRET_KEY': 'sb_secret_test_key',
    'API_API_KEY': 'test_api_key',
    'API_REALM_ID': 'test_realm_id'
})

from core.rate_limiter import (
    RateLimiter, RateLimitType, RateLimitInfo, RateLimitWindow,
    get_rate_limiter, shutdown_rate_limiter
)
from core.exceptions import RateLimitExceededError


class TestRateLimitWindow:
    """Test the RateLimitWindow class."""
    
    def test_window_initialization(self):
        """Test window initialization."""
        window = RateLimitWindow(limit=10, window_seconds=60)
        assert window.limit == 10
        assert window.window_seconds == 60
        assert len(window.requests) == 0
    
    def test_add_request(self):
        """Test adding requests to window."""
        window = RateLimitWindow(limit=10, window_seconds=60)
        
        # Add a request
        window.add_request()
        assert window.get_current_count() == 1
        
        # Add another request
        window.add_request()
        assert window.get_current_count() == 2
    
    def test_window_cleanup(self):
        """Test cleanup of old requests."""
        window = RateLimitWindow(limit=10, window_seconds=1)
        
        # Add requests with specific timestamps
        old_time = time.time() - 2  # 2 seconds ago
        current_time = time.time()
        
        # Manually add to deque to avoid automatic cleanup
        window.requests.append(old_time)
        window.requests.append(current_time)
        
        # Should have 2 requests initially
        assert len(window.requests) == 2
        
        # After cleanup, should only have 1 (the recent one)
        window._cleanup_old_requests()
        assert window.get_current_count() == 1
    
    def test_is_exceeded(self):
        """Test rate limit exceeded detection."""
        window = RateLimitWindow(limit=2, window_seconds=60)
        
        # Not exceeded initially
        assert not window.is_exceeded()
        
        # Add requests up to limit
        window.add_request()
        assert not window.is_exceeded()
        
        window.add_request()
        assert window.is_exceeded()  # At limit
        
        window.add_request()
        assert window.is_exceeded()  # Over limit
    
    def test_get_reset_time(self):
        """Test reset time calculation."""
        window = RateLimitWindow(limit=10, window_seconds=60)
        
        # No requests - reset time should be current time
        reset_time = window.get_reset_time()
        assert abs(reset_time - time.time()) < 1
        
        # Add a request
        request_time = time.time()
        window.add_request(request_time)
        
        # Reset time should be request time + window
        expected_reset = request_time + window.window_seconds
        assert abs(window.get_reset_time() - expected_reset) < 1


class TestRateLimitInfo:
    """Test the RateLimitInfo class."""
    
    def test_info_initialization(self):
        """Test rate limit info initialization."""
        info = RateLimitInfo(
            limit=10,
            remaining=5,
            reset_time=time.time() + 60,
            window_seconds=60
        )
        
        assert info.limit == 10
        assert info.remaining == 5
        assert info.window_seconds == 60
        assert not info.is_exceeded
    
    def test_seconds_until_reset(self):
        """Test seconds until reset calculation."""
        future_time = time.time() + 30
        info = RateLimitInfo(
            limit=10,
            remaining=5,
            reset_time=future_time,
            window_seconds=60
        )
        
        # Should be approximately 30 seconds
        assert 25 <= info.seconds_until_reset <= 35
    
    def test_reset_datetime(self):
        """Test reset datetime property."""
        reset_time = time.time() + 60
        info = RateLimitInfo(
            limit=10,
            remaining=5,
            reset_time=reset_time,
            window_seconds=60
        )
        
        # Should convert timestamp to datetime
        assert info.reset_datetime.timestamp() == pytest.approx(reset_time, abs=1)


@pytest_asyncio.fixture
async def rate_limiter():
    """Create a rate limiter for testing."""
    # Mock settings to avoid configuration validation issues
    from unittest.mock import Mock, patch
    
    mock_settings = Mock()
    mock_settings.rate_limit = Mock()
    mock_settings.rate_limit.user_requests_per_minute = 10
    mock_settings.rate_limit.user_bets_per_minute = 5
    mock_settings.rate_limit.user_predictions_per_hour = 3
    mock_settings.rate_limit.guild_requests_per_minute = 100
    mock_settings.rate_limit.guild_predictions_per_hour = 10
    mock_settings.rate_limit.rate_limit_window_seconds = 60
    mock_settings.rate_limit.rate_limit_cleanup_interval = 300
    mock_settings.rate_limit.admin_bypass_enabled = True
    
    with patch('core.rate_limiter.get_settings', return_value=mock_settings):
        limiter = RateLimiter()
        yield limiter
        await limiter.shutdown()


class TestRateLimiter:
    """Test the RateLimiter class."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, rate_limiter):
        """Test rate limiter initialization."""
        assert rate_limiter is not None
        assert len(rate_limiter._user_windows) == 0
        assert len(rate_limiter._guild_windows) == 0
    
    @pytest.mark.asyncio
    async def test_admin_bypass_users(self, rate_limiter):
        """Test admin user bypass functionality."""
        user_id = 12345
        
        # Add admin user
        rate_limiter.add_admin_user(user_id)
        assert user_id in rate_limiter._admin_users
        
        # Check bypass
        assert rate_limiter._is_admin_bypass(user_id)
        
        # Remove admin user
        rate_limiter.remove_admin_user(user_id)
        assert user_id not in rate_limiter._admin_users
        assert not rate_limiter._is_admin_bypass(user_id)
    
    @pytest.mark.asyncio
    async def test_admin_bypass_roles(self, rate_limiter):
        """Test admin role bypass functionality."""
        user_id = 12345
        admin_role_id = 67890
        
        # Add admin role
        rate_limiter.add_admin_role(admin_role_id)
        assert admin_role_id in rate_limiter._admin_roles
        
        # Check bypass with role
        assert rate_limiter._is_admin_bypass(user_id, [admin_role_id])
        assert not rate_limiter._is_admin_bypass(user_id, [99999])  # Different role
        
        # Remove admin role
        rate_limiter.remove_admin_role(admin_role_id)
        assert admin_role_id not in rate_limiter._admin_roles
        assert not rate_limiter._is_admin_bypass(user_id, [admin_role_id])
    
    @pytest.mark.asyncio
    async def test_user_rate_limiting(self, rate_limiter):
        """Test user rate limiting."""
        user_id = 12345
        
        # First request should be allowed
        info = await rate_limiter.consume_rate_limit(
            user_id=user_id,
            limit_type=RateLimitType.USER_REQUESTS
        )
        assert not info.is_exceeded
        assert info.remaining == info.limit - 1
        
        # Consume all remaining requests
        for _ in range(info.remaining):
            info = await rate_limiter.consume_rate_limit(
                user_id=user_id,
                limit_type=RateLimitType.USER_REQUESTS
            )
        
        # Next request should be rate limited
        info = await rate_limiter.consume_rate_limit(
            user_id=user_id,
            limit_type=RateLimitType.USER_REQUESTS
        )
        assert info.is_exceeded
        assert info.remaining == 0
    
    @pytest.mark.asyncio
    async def test_guild_rate_limiting(self, rate_limiter):
        """Test guild rate limiting."""
        user_id = 12345
        guild_id = 67890
        
        # Test guild request limiting
        info = await rate_limiter.consume_rate_limit(
            user_id=user_id,
            guild_id=guild_id,
            limit_type=RateLimitType.GUILD_REQUESTS
        )
        assert not info.is_exceeded
    
    @pytest.mark.asyncio
    async def test_different_limit_types(self, rate_limiter):
        """Test different rate limit types."""
        user_id = 12345
        
        # Test user requests
        info1 = await rate_limiter.consume_rate_limit(
            user_id=user_id,
            limit_type=RateLimitType.USER_REQUESTS
        )
        
        # Test user bets (should be independent)
        info2 = await rate_limiter.consume_rate_limit(
            user_id=user_id,
            limit_type=RateLimitType.USER_BETS
        )
        
        # Both should be allowed
        assert not info1.is_exceeded
        assert not info2.is_exceeded
        
        # Limits should be different
        assert info1.limit != info2.limit or info1.window_seconds != info2.window_seconds
    
    @pytest.mark.asyncio
    async def test_admin_bypass_in_rate_limiting(self, rate_limiter):
        """Test admin bypass during rate limiting."""
        user_id = 12345
        
        # Add user as admin
        rate_limiter.add_admin_user(user_id)
        
        # Should always be allowed regardless of limit
        for _ in range(20):  # More than any reasonable limit
            info = await rate_limiter.consume_rate_limit(
                user_id=user_id,
                limit_type=RateLimitType.USER_REQUESTS
            )
            assert not info.is_exceeded
    
    @pytest.mark.asyncio
    async def test_rate_limit_status_check(self, rate_limiter):
        """Test rate limit status checking without consumption."""
        user_id = 12345
        
        # Check status without consuming
        info1 = await rate_limiter.check_rate_limit(
            user_id=user_id,
            limit_type=RateLimitType.USER_REQUESTS
        )
        
        # Check again - should be the same
        info2 = await rate_limiter.check_rate_limit(
            user_id=user_id,
            limit_type=RateLimitType.USER_REQUESTS
        )
        
        assert info1.remaining == info2.remaining
        assert not info1.is_exceeded
        assert not info2.is_exceeded
    
    @pytest.mark.asyncio
    async def test_statistics(self, rate_limiter):
        """Test rate limiter statistics."""
        user_id = 12345
        
        # Initial stats
        stats = rate_limiter.get_statistics()
        initial_requests = stats['total_requests']
        
        # Make some requests
        await rate_limiter.consume_rate_limit(user_id=user_id)
        await rate_limiter.consume_rate_limit(user_id=user_id)
        
        # Check updated stats
        stats = rate_limiter.get_statistics()
        assert stats['total_requests'] == initial_requests + 2
        assert stats['active_user_windows'] >= 1
    
    @pytest.mark.asyncio
    async def test_cleanup_old_windows(self, rate_limiter):
        """Test cleanup of old rate limit windows."""
        user_id = 12345
        
        # Create a window
        await rate_limiter.consume_rate_limit(user_id=user_id)
        assert len(rate_limiter._user_windows) >= 1
        
        # Manually trigger cleanup
        await rate_limiter._cleanup_old_windows()
        
        # Windows should still exist (not old enough)
        assert len(rate_limiter._user_windows) >= 1
    
    @pytest.mark.asyncio
    async def test_get_rate_limit_config(self, rate_limiter):
        """Test rate limit configuration retrieval."""
        # Test different limit types
        user_req_config = rate_limiter._get_rate_limit_config(RateLimitType.USER_REQUESTS)
        user_bet_config = rate_limiter._get_rate_limit_config(RateLimitType.USER_BETS)
        user_pred_config = rate_limiter._get_rate_limit_config(RateLimitType.USER_PREDICTIONS)
        
        # Should return tuples of (limit, window_seconds)
        assert len(user_req_config) == 2
        assert len(user_bet_config) == 2
        assert len(user_pred_config) == 2
        
        # Predictions should have longer window (1 hour)
        assert user_pred_config[1] == 3600


@pytest.mark.asyncio
async def test_global_rate_limiter():
    """Test global rate limiter instance."""
    # Get global instance
    limiter1 = get_rate_limiter()
    limiter2 = get_rate_limiter()
    
    # Should be the same instance
    assert limiter1 is limiter2
    
    # Shutdown
    await shutdown_rate_limiter()
    
    # New instance after shutdown
    limiter3 = get_rate_limiter()
    assert limiter3 is not limiter1


class TestRateLimitIntegration:
    """Integration tests for rate limiting."""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test concurrent rate limit requests."""
        limiter = RateLimiter()
        user_id = 12345
        
        async def make_request():
            return await limiter.consume_rate_limit(
                user_id=user_id,
                limit_type=RateLimitType.USER_REQUESTS
            )
        
        # Make concurrent requests
        tasks = [make_request() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        
        # Some should succeed, some might be rate limited
        exceeded_count = sum(1 for result in results if result.is_exceeded)
        success_count = sum(1 for result in results if not result.is_exceeded)
        
        assert success_count > 0  # At least some should succeed
        assert success_count + exceeded_count == 5  # All should be accounted for
        
        await limiter.shutdown()
    
    @pytest.mark.asyncio
    async def test_time_window_expiry(self):
        """Test that rate limits reset after time window."""
        # Use a very short window for testing
        limiter = RateLimiter()
        user_id = 12345
        
        # Mock the rate limit config to use short window
        original_config = limiter._get_rate_limit_config
        
        def mock_config(limit_type):
            if limit_type == RateLimitType.USER_REQUESTS:
                return (2, 1)  # 2 requests per 1 second
            return original_config(limit_type)
        
        limiter._get_rate_limit_config = mock_config
        
        try:
            # Consume all requests
            info1 = await limiter.consume_rate_limit(
                user_id=user_id,
                limit_type=RateLimitType.USER_REQUESTS
            )
            info2 = await limiter.consume_rate_limit(
                user_id=user_id,
                limit_type=RateLimitType.USER_REQUESTS
            )
            
            # Should be at limit
            assert not info1.is_exceeded
            # Second request should be at or over limit
            assert info2.is_exceeded or info2.remaining == 0
            
            # Wait for window to expire
            await asyncio.sleep(1.1)
            
            # Should be able to make requests again
            info3 = await limiter.consume_rate_limit(
                user_id=user_id,
                limit_type=RateLimitType.USER_REQUESTS
            )
            assert not info3.is_exceeded
            
        finally:
            limiter._get_rate_limit_config = original_config
            await limiter.shutdown()


@pytest.mark.asyncio
async def test_rate_limit_middleware_integration():
    """Test integration with rate limit middleware."""
    from core.rate_limit_middleware import get_rate_limit_middleware
    
    middleware = get_rate_limit_middleware()
    user_id = 12345
    guild_id = 67890
    
    # Test rate limit check
    info = await middleware.check_rate_limit(
        user_id=user_id,
        guild_id=guild_id,
        limit_type=RateLimitType.USER_REQUESTS
    )
    
    assert not info.is_exceeded
    assert info.remaining > 0
    
    # Test rate limit consumption
    info2 = await middleware.consume_rate_limit(
        user_id=user_id,
        guild_id=guild_id,
        limit_type=RateLimitType.USER_REQUESTS
    )
    
    assert info2.remaining == info.remaining - 1


if __name__ == "__main__":
    pytest.main([__file__])