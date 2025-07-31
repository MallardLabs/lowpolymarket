"""
Example usage of the rate limiting system.

This example demonstrates how to use the rate limiting system
in Discord commands and other parts of the application.
"""

import asyncio
import discord
from discord.ext import commands

from core.rate_limiter import RateLimitType, get_rate_limiter
from core.rate_limit_middleware import (
    rate_limit, user_request_limit, user_bet_limit, user_prediction_limit,
    get_rate_limit_middleware
)
from core.exceptions import RateLimitExceededError


class PredictionCog(commands.Cog):
    """Example cog showing rate limiting usage."""
    
    def __init__(self, bot):
        self.bot = bot
        self.rate_limiter = get_rate_limiter()
        self.rate_middleware = get_rate_limit_middleware()
    
    @commands.command(name="create_prediction")
    @user_prediction_limit("🚦 You're creating predictions too quickly! Please wait before creating another.")
    async def create_prediction(self, ctx, *, question: str):
        """Create a new prediction with rate limiting."""
        # The rate limiting is handled by the decorator
        # This command will be rate limited automatically
        
        await ctx.send(f"✅ Created prediction: {question}")
    
    @commands.command(name="place_bet")
    @user_bet_limit()  # Uses default error message
    async def place_bet(self, ctx, prediction_id: str, option: str, amount: int):
        """Place a bet with rate limiting."""
        # The rate limiting is handled by the decorator
        
        await ctx.send(f"✅ Placed bet of {amount} on '{option}' for prediction {prediction_id}")
    
    @commands.command(name="list_predictions")
    @user_request_limit()
    async def list_predictions(self, ctx):
        """List predictions with general request rate limiting."""
        # This uses the general request rate limit
        
        await ctx.send("📋 Here are the active predictions...")
    
    @commands.command(name="manual_rate_check")
    async def manual_rate_check(self, ctx):
        """Example of manual rate limit checking."""
        try:
            # Manually check rate limit before processing
            rate_info = await self.rate_middleware.check_rate_limit(
                user_id=ctx.author.id,
                guild_id=ctx.guild.id if ctx.guild else None,
                limit_type=RateLimitType.USER_REQUESTS,
                user_roles=[role.id for role in ctx.author.roles] if hasattr(ctx.author, 'roles') else None
            )
            
            if rate_info.is_exceeded:
                await ctx.send(f"⏰ Rate limit exceeded! Try again in {rate_info.seconds_until_reset} seconds.")
                return
            
            # Consume the rate limit slot
            await self.rate_middleware.consume_rate_limit(
                user_id=ctx.author.id,
                guild_id=ctx.guild.id if ctx.guild else None,
                limit_type=RateLimitType.USER_REQUESTS,
                user_roles=[role.id for role in ctx.author.roles] if hasattr(ctx.author, 'roles') else None
            )
            
            # Process the command
            await ctx.send(f"✅ Command processed! You have {rate_info.remaining - 1} requests remaining.")
            
        except RateLimitExceededError as e:
            await ctx.send(f"🚦 {e.user_message}")
    
    @commands.command(name="rate_status")
    async def rate_status(self, ctx):
        """Show current rate limit status for the user."""
        user_id = ctx.author.id
        
        # Get status for different rate limit types
        request_status = self.rate_limiter.get_user_rate_limit_status(user_id, RateLimitType.USER_REQUESTS)
        bet_status = self.rate_limiter.get_user_rate_limit_status(user_id, RateLimitType.USER_BETS)
        prediction_status = self.rate_limiter.get_user_rate_limit_status(user_id, RateLimitType.USER_PREDICTIONS)
        
        embed = discord.Embed(title="📊 Your Rate Limit Status", color=0x00ff00)
        
        embed.add_field(
            name="🔄 General Requests",
            value=f"{request_status.remaining}/{request_status.limit} remaining\n"
                  f"Resets in {request_status.seconds_until_reset}s",
            inline=True
        )
        
        embed.add_field(
            name="💰 Betting",
            value=f"{bet_status.remaining}/{bet_status.limit} remaining\n"
                  f"Resets in {bet_status.seconds_until_reset}s",
            inline=True
        )
        
        embed.add_field(
            name="📝 Predictions",
            value=f"{prediction_status.remaining}/{prediction_status.limit} remaining\n"
                  f"Resets in {prediction_status.seconds_until_reset}s",
            inline=True
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="admin_bypass")
    @commands.has_permissions(administrator=True)
    async def admin_bypass(self, ctx, user: discord.Member = None):
        """Add/remove admin bypass for rate limiting."""
        if user is None:
            user = ctx.author
        
        # Toggle admin bypass
        if user.id in self.rate_limiter._admin_users:
            self.rate_middleware.remove_admin_user(user.id)
            await ctx.send(f"❌ Removed rate limit bypass for {user.mention}")
        else:
            self.rate_middleware.add_admin_user(user.id)
            await ctx.send(f"✅ Added rate limit bypass for {user.mention}")


class CustomRateLimitExample:
    """Example of custom rate limiting logic."""
    
    def __init__(self):
        self.rate_limiter = get_rate_limiter()
    
    async def process_api_request(self, user_id: int, guild_id: int = None):
        """Example of processing an API request with rate limiting."""
        try:
            # Check rate limit first
            rate_info = await self.rate_limiter.check_rate_limit(
                user_id=user_id,
                guild_id=guild_id,
                limit_type=RateLimitType.USER_REQUESTS
            )
            
            if rate_info.is_exceeded:
                return {
                    "success": False,
                    "error": "Rate limit exceeded",
                    "retry_after": rate_info.seconds_until_reset
                }
            
            # Consume rate limit slot
            await self.rate_limiter.consume_rate_limit(
                user_id=user_id,
                guild_id=guild_id,
                limit_type=RateLimitType.USER_REQUESTS
            )
            
            # Process the actual request
            result = await self._do_api_work()
            
            return {
                "success": True,
                "data": result,
                "rate_limit": {
                    "remaining": rate_info.remaining - 1,
                    "reset_time": rate_info.reset_time
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _do_api_work(self):
        """Simulate API work."""
        await asyncio.sleep(0.1)  # Simulate processing time
        return {"message": "API request processed successfully"}


async def batch_processing_example():
    """Example of handling batch operations with rate limiting."""
    rate_limiter = get_rate_limiter()
    user_id = 12345
    
    # Process multiple items with rate limiting
    items = ["item1", "item2", "item3", "item4", "item5"]
    results = []
    
    for item in items:
        try:
            # Check if we can process this item
            rate_info = await rate_limiter.consume_rate_limit(
                user_id=user_id,
                limit_type=RateLimitType.USER_REQUESTS
            )
            
            if rate_info.is_exceeded:
                # Wait until rate limit resets
                wait_time = rate_info.seconds_until_reset
                print(f"Rate limit exceeded, waiting {wait_time} seconds...")
                await asyncio.sleep(wait_time)
                
                # Try again
                rate_info = await rate_limiter.consume_rate_limit(
                    user_id=user_id,
                    limit_type=RateLimitType.USER_REQUESTS
                )
            
            # Process the item
            result = f"Processed {item}"
            results.append(result)
            print(f"✅ {result} (Remaining: {rate_info.remaining})")
            
        except Exception as e:
            print(f"❌ Error processing {item}: {e}")
            results.append(f"Error: {item}")
    
    return results


async def monitoring_example():
    """Example of monitoring rate limiter statistics."""
    rate_limiter = get_rate_limiter()
    
    # Get current statistics
    stats = rate_limiter.get_statistics()
    
    print("📊 Rate Limiter Statistics:")
    print(f"Total requests: {stats['total_requests']}")
    print(f"Blocked requests: {stats['blocked_requests']}")
    print(f"Bypassed requests: {stats['bypassed_requests']}")
    print(f"Block rate: {stats['block_rate']:.2f}%")
    print(f"Bypass rate: {stats['bypass_rate']:.2f}%")
    print(f"Active user windows: {stats['active_user_windows']}")
    print(f"Active guild windows: {stats['active_guild_windows']}")
    print(f"Admin users: {stats['admin_users_count']}")
    print(f"Admin roles: {stats['admin_roles_count']}")
    
    if stats['violations_by_type']:
        print("\n🚫 Violations by type:")
        for limit_type, count in stats['violations_by_type'].items():
            print(f"  {limit_type}: {count}")


async def main():
    """Main example function."""
    print("🚀 Rate Limiting Examples")
    
    # Example 1: Batch processing with rate limiting
    print("\n1. Batch Processing Example:")
    results = await batch_processing_example()
    print(f"Processed {len(results)} items")
    
    # Example 2: Custom API request handling
    print("\n2. Custom API Request Example:")
    api_handler = CustomRateLimitExample()
    result = await api_handler.process_api_request(user_id=12345, guild_id=67890)
    print(f"API Result: {result}")
    
    # Example 3: Monitoring
    print("\n3. Monitoring Example:")
    await monitoring_example()
    
    # Cleanup
    from core.rate_limiter import shutdown_rate_limiter
    await shutdown_rate_limiter()


if __name__ == "__main__":
    asyncio.run(main())