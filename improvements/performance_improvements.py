"""
Performance and Caching Improvements
"""

import asyncio
import time
from typing import Any, Optional, Callable, TypeVar, Generic
from dataclasses import dataclass
from functools import wraps
import hashlib
import json
from collections import OrderedDict
import weakref

T = TypeVar('T')

# 1. ADVANCED CACHING SYSTEM
class CacheEntry(Generic[T]):
    def __init__(self, value: T, ttl: float, created_at: float = None):
        self.value = value
        self.ttl = ttl
        self.created_at = created_at or time.time()
    
    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl

class LRUCache(Generic[T]):
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[T]:
        async with self._lock:
            if key not in self.cache:
                return None
            
            entry = self.cache[key]
            if entry.is_expired:
                del self.cache[key]
                return None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return entry.value
    
    async def set(self, key: str, value: T, ttl: float = 300):
        async with self._lock:
            if key in self.cache:
                del self.cache[key]
            elif len(self.cache) >= self.max_size:
                # Remove least recently used
                self.cache.popitem(last=False)
            
            self.cache[key] = CacheEntry(value, ttl)
    
    async def invalidate(self, key: str):
        async with self._lock:
            self.cache.pop(key, None)
    
    async def clear(self):
        async with self._lock:
            self.cache.clear()

# 2. CACHE DECORATORS
def cached(ttl: float = 300, key_func: Callable = None):
    def decorator(func):
        cache = LRUCache[Any](max_size=500)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = _generate_cache_key(func.__name__, args, kwargs)
            
            # Try to get from cache
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl)
            return result
        
        wrapper.cache = cache
        return wrapper
    return decorator

def _generate_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Generate a cache key from function name and arguments"""
    key_data = {
        'func': func_name,
        'args': args,
        'kwargs': sorted(kwargs.items())
    }
    key_str = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.md5(key_str.encode()).hexdigest()

# 3. DATABASE QUERY OPTIMIZATION
class QueryOptimizer:
    def __init__(self, db_pool):
        self.db_pool = db_pool
        self.query_cache = LRUCache[Any](max_size=200)
    
    @cached(ttl=60)  # Cache for 1 minute
    async def get_prediction_with_stats(self, prediction_id: str) -> dict:
        """Optimized query that gets prediction with all stats in one go"""
        async with self.db_pool.acquire() as conn:
            return await conn.fetchrow("""
                SELECT 
                    p.*,
                    COUNT(DISTINCT b.user_id) as unique_bettors,
                    COALESCE(SUM(b.amount_bet), 0) as total_volume,
                    json_agg(
                        DISTINCT jsonb_build_object(
                            'option', lp.option_name,
                            'liquidity', lp.current_liquidity,
                            'total_bets', COALESCE(bet_totals.total, 0),
                            'bet_count', COALESCE(bet_totals.count, 0)
                        )
                    ) as option_stats
                FROM predictions p
                LEFT JOIN bets b ON p.id = b.prediction_id
                LEFT JOIN liquidity_pools lp ON p.id = lp.prediction_id
                LEFT JOIN (
                    SELECT 
                        prediction_id,
                        option_name,
                        SUM(amount_bet) as total,
                        COUNT(*) as count
                    FROM bets
                    GROUP BY prediction_id, option_name
                ) bet_totals ON lp.prediction_id = bet_totals.prediction_id 
                    AND lp.option_name = bet_totals.option_name
                WHERE p.id = $1
                GROUP BY p.id
            """, prediction_id)
    
    async def get_user_portfolio(self, user_id: int, guild_id: int) -> list[dict]:
        """Get user's complete betting portfolio efficiently"""
        async with self.db_pool.acquire() as conn:
            return await conn.fetch("""
                SELECT 
                    p.question,
                    p.status,
                    p.result,
                    b.option_name,
                    SUM(b.amount_bet) as total_bet,
                    SUM(b.shares_owned) as total_shares,
                    CASE 
                        WHEN p.status = 'resolved' AND p.result = b.option_name 
                        THEN 'won'
                        WHEN p.status = 'resolved' 
                        THEN 'lost'
                        WHEN p.status = 'refunded' 
                        THEN 'refunded'
                        ELSE 'active'
                    END as bet_status
                FROM bets b
                JOIN predictions p ON b.prediction_id = p.id
                WHERE b.user_id = $1 AND b.guild_id = $2
                GROUP BY p.id, p.question, p.status, p.result, b.option_name
                ORDER BY p.created_at DESC
            """, user_id, guild_id)

# 4. BATCH OPERATIONS
class BatchProcessor:
    def __init__(self, batch_size: int = 100, flush_interval: float = 5.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.pending_operations: list = []
        self._last_flush = time.time()
        self._lock = asyncio.Lock()
    
    async def add_operation(self, operation: dict):
        async with self._lock:
            self.pending_operations.append(operation)
            
            if (len(self.pending_operations) >= self.batch_size or 
                time.time() - self._last_flush > self.flush_interval):
                await self._flush()
    
    async def _flush(self):
        if not self.pending_operations:
            return
        
        operations = self.pending_operations.copy()
        self.pending_operations.clear()
        self._last_flush = time.time()
        
        # Process operations in batches
        await self._process_batch(operations)
    
    async def _process_batch(self, operations: list):
        # Group operations by type
        grouped = {}
        for op in operations:
            op_type = op.get('type')
            if op_type not in grouped:
                grouped[op_type] = []
            grouped[op_type].append(op)
        
        # Process each type
        for op_type, ops in grouped.items():
            if op_type == 'update_liquidity':
                await self._batch_update_liquidity(ops)
            elif op_type == 'log_event':
                await self._batch_log_events(ops)
    
    async def _batch_update_liquidity(self, operations: list):
        # Batch update liquidity pools
        pass
    
    async def _batch_log_events(self, operations: list):
        # Batch log events
        pass

# 5. CONNECTION POOLING OPTIMIZATION
class OptimizedConnectionPool:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None
        self._connection_stats = {
            'active': 0,
            'total_created': 0,
            'total_queries': 0
        }
    
    async def initialize(self):
        self.pool = await asyncpg.create_pool(
            self.database_url,
            min_size=5,
            max_size=20,
            max_queries=50000,  # Recycle connections after 50k queries
            max_inactive_connection_lifetime=300,  # 5 minutes
            command_timeout=30,
            server_settings={
                'jit': 'off',  # Disable JIT for faster simple queries
                'application_name': 'prediction_bot'
            }
        )
    
    async def execute_query(self, query: str, *args):
        async with self.pool.acquire() as conn:
            self._connection_stats['total_queries'] += 1
            return await conn.fetch(query, *args)
    
    def get_stats(self) -> dict:
        return {
            **self._connection_stats,
            'pool_size': self.pool.get_size() if self.pool else 0,
            'idle_connections': self.pool.get_idle_size() if self.pool else 0
        }

# 6. MEMORY OPTIMIZATION
class WeakReferenceCache:
    """Cache that doesn't prevent garbage collection"""
    def __init__(self):
        self._cache = weakref.WeakValueDictionary()
    
    def get(self, key: str) -> Optional[Any]:
        return self._cache.get(key)
    
    def set(self, key: str, value: Any):
        self._cache[key] = value

# 7. ASYNC TASK OPTIMIZATION
class TaskManager:
    def __init__(self, max_concurrent_tasks: int = 50):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.active_tasks: set = set()
    
    async def run_task(self, coro):
        async with self.semaphore:
            task = asyncio.create_task(coro)
            self.active_tasks.add(task)
            try:
                result = await task
                return result
            finally:
                self.active_tasks.discard(task)
    
    async def shutdown(self):
        """Gracefully shutdown all tasks"""
        if self.active_tasks:
            await asyncio.gather(*self.active_tasks, return_exceptions=True)

# 8. PERFORMANCE MONITORING
class PerformanceMonitor:
    def __init__(self):
        self.metrics = {
            'query_times': [],
            'cache_hits': 0,
            'cache_misses': 0,
            'active_connections': 0
        }
    
    def record_query_time(self, duration: float):
        self.metrics['query_times'].append(duration)
        # Keep only last 1000 measurements
        if len(self.metrics['query_times']) > 1000:
            self.metrics['query_times'] = self.metrics['query_times'][-1000:]
    
    def record_cache_hit(self):
        self.metrics['cache_hits'] += 1
    
    def record_cache_miss(self):
        self.metrics['cache_misses'] += 1
    
    def get_stats(self) -> dict:
        query_times = self.metrics['query_times']
        return {
            'avg_query_time': sum(query_times) / len(query_times) if query_times else 0,
            'max_query_time': max(query_times) if query_times else 0,
            'cache_hit_rate': (
                self.metrics['cache_hits'] / 
                (self.metrics['cache_hits'] + self.metrics['cache_misses'])
                if (self.metrics['cache_hits'] + self.metrics['cache_misses']) > 0 else 0
            ),
            'total_queries': len(query_times)
        }

# Usage Example:
"""
class OptimizedPredictionService:
    def __init__(self, db_pool):
        self.query_optimizer = QueryOptimizer(db_pool)
        self.batch_processor = BatchProcessor()
        self.task_manager = TaskManager()
        self.performance_monitor = PerformanceMonitor()
    
    @cached(ttl=60, key_func=lambda self, pred_id: f"prediction:{pred_id}")
    async def get_prediction_data(self, prediction_id: str):
        start_time = time.time()
        try:
            result = await self.query_optimizer.get_prediction_with_stats(prediction_id)
            self.performance_monitor.record_cache_miss()
            return result
        finally:
            duration = time.time() - start_time
            self.performance_monitor.record_query_time(duration)
"""