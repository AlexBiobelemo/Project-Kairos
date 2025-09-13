"""
Caching and Performance Optimization
Implements multi-level caching, compression, and memory optimization.
"""

import time
import json
import gzip
import pickle
import threading
import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import OrderedDict
import weakref
from pathlib import Path

from config import config


@dataclass
class CacheStats:
    """Cache statistics for monitoring"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size_bytes: int = 0
    entry_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def reset(self):
        """Reset all statistics"""
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.size_bytes = 0
        self.entry_count = 0


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    timestamp: datetime
    ttl_seconds: int
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    compressed: bool = False
    size_bytes: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if entry is expired"""
        if self.ttl_seconds <= 0:
            return False
        return datetime.now() > (self.timestamp + timedelta(seconds=self.ttl_seconds))
    
    @property
    def age_seconds(self) -> float:
        """Get entry age in seconds"""
        return (datetime.now() - self.timestamp).total_seconds()
    
    def update_access(self):
        """Update access statistics"""
        self.access_count += 1
        self.last_accessed = datetime.now()


class CompressionManager:
    """Manages data compression for cache entries"""
    
    COMPRESSION_THRESHOLD = 1024  # Compress data larger than 1KB
    
    @staticmethod
    def should_compress(data: Any, threshold: int = None) -> bool:
        """Determine if data should be compressed"""
        if threshold is None:
            threshold = CompressionManager.COMPRESSION_THRESHOLD
        
        try:
            serialized = pickle.dumps(data)
            return len(serialized) > threshold
        except:
            return False
    
    @staticmethod
    def compress(data: Any) -> bytes:
        """Compress data using gzip"""
        try:
            serialized = pickle.dumps(data)
            return gzip.compress(serialized)
        except Exception as e:
            raise ValueError(f"Failed to compress data: {e}")
    
    @staticmethod
    def decompress(compressed_data: bytes) -> Any:
        """Decompress data"""
        try:
            decompressed = gzip.decompress(compressed_data)
            return pickle.loads(decompressed)
        except Exception as e:
            raise ValueError(f"Failed to decompress data: {e}")
    
    @staticmethod
    def get_size(data: Any) -> int:
        """Get approximate size of data in bytes"""
        try:
            if isinstance(data, bytes):
                return len(data)
            return len(pickle.dumps(data))
        except:
            return 0


class LRUCache:
    """Thread-safe LRU cache with TTL and compression"""
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 3600,
        enable_compression: bool = True,
        max_memory_mb: int = 100
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.enable_compression = enable_compression
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = CacheStats()
        self._compression = CompressionManager()
        
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._periodic_cleanup, daemon=True)
        self._cleanup_thread.start()
        
        self.logger = logging.getLogger(f"{__name__}.LRUCache")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache"""
        with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return default
            
            entry = self._cache[key]
            
            # Check if expired
            if entry.is_expired:
                del self._cache[key]
                self._stats.misses += 1
                self._stats.evictions += 1
                return default
            
            # Update access statistics
            entry.update_access()
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            
            self._stats.hits += 1
            
            # Return decompressed value if needed
            if entry.compressed:
                try:
                    return self._compression.decompress(entry.value)
                except ValueError as e:
                    self.logger.error(f"Failed to decompress cached value for key {key}: {e}")
                    del self._cache[key]
                    return default
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        if ttl is None:
            ttl = self.default_ttl
        
        with self._lock:
            # Prepare entry
            now = datetime.now()
            compressed = False
            stored_value = value
            
            # Compress if enabled and beneficial
            if self.enable_compression and self._compression.should_compress(value):
                try:
                    stored_value = self._compression.compress(value)
                    compressed = True
                except ValueError as e:
                    self.logger.warning(f"Failed to compress value for key {key}: {e}")
            
            # Calculate size
            size_bytes = self._compression.get_size(stored_value)
            
            # Create cache entry
            entry = CacheEntry(
                key=key,
                value=stored_value,
                timestamp=now,
                ttl_seconds=ttl,
                compressed=compressed,
                size_bytes=size_bytes
            )
            
            # Remove existing entry if present
            if key in self._cache:
                old_entry = self._cache[key]
                self._stats.size_bytes -= old_entry.size_bytes
            
            # Add new entry
            self._cache[key] = entry
            self._stats.size_bytes += size_bytes
            self._stats.entry_count = len(self._cache)
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            
            # Enforce size limits
            self._enforce_limits()
            
            return True
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                self._stats.size_bytes -= entry.size_bytes
                del self._cache[key]
                self._stats.entry_count = len(self._cache)
                return True
            return False
    
    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()
            self._stats.reset()
    
    def _enforce_limits(self):
        """Enforce cache size and memory limits"""
        # Remove expired entries first
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired
        ]
        
        for key in expired_keys:
            entry = self._cache[key]
            self._stats.size_bytes -= entry.size_bytes
            del self._cache[key]
            self._stats.evictions += 1
        
        # Enforce size limit (LRU eviction)
        while len(self._cache) > self.max_size:
            key, entry = self._cache.popitem(last=False)  # Remove oldest
            self._stats.size_bytes -= entry.size_bytes
            self._stats.evictions += 1
        
        # Enforce memory limit (LRU eviction)
        while self._stats.size_bytes > self.max_memory_bytes and self._cache:
            key, entry = self._cache.popitem(last=False)  # Remove oldest
            self._stats.size_bytes -= entry.size_bytes
            self._stats.evictions += 1
        
        self._stats.entry_count = len(self._cache)
    
    def _periodic_cleanup(self):
        """Periodic cleanup of expired entries"""
        while True:
            try:
                time.sleep(60)  # Check every minute
                with self._lock:
                    self._enforce_limits()
            except Exception as e:
                self.logger.error(f"Cleanup error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            return {
                'hits': self._stats.hits,
                'misses': self._stats.misses,
                'hit_rate': self._stats.hit_rate,
                'evictions': self._stats.evictions,
                'entry_count': self._stats.entry_count,
                'size_bytes': self._stats.size_bytes,
                'size_mb': round(self._stats.size_bytes / 1024 / 1024, 2),
                'max_size': self.max_size,
                'max_memory_mb': round(self.max_memory_bytes / 1024 / 1024, 2)
            }
    
    def get_keys(self) -> List[str]:
        """Get all cache keys"""
        with self._lock:
            return list(self._cache.keys())
    
    def contains(self, key: str) -> bool:
        """Check if key exists and is not expired"""
        with self._lock:
            if key not in self._cache:
                return False
            entry = self._cache[key]
            if entry.is_expired:
                del self._cache[key]
                self._stats.evictions += 1
                return False
            return True


class MultiLevelCache:
    """Multi-level cache system with L1 (memory) and L2 (disk) caches"""
    
    def __init__(
        self,
        l1_max_size: int = 500,
        l1_ttl: int = 300,
        l2_max_size: int = 2000,
        l2_ttl: int = 3600,
        disk_cache_path: Optional[str] = None
    ):
        # L1 Cache (Memory - Fast)
        self.l1_cache = LRUCache(
            max_size=l1_max_size,
            default_ttl=l1_ttl,
            enable_compression=False,  # L1 prioritizes speed
            max_memory_mb=50
        )
        
        # L2 Cache (Memory with compression - Larger)
        self.l2_cache = LRUCache(
            max_size=l2_max_size,
            default_ttl=l2_ttl,
            enable_compression=True,
            max_memory_mb=200
        )
        
        self.logger = logging.getLogger(f"{__name__}.MultiLevelCache")
        
        # Track items promoted from L1 to L2
        self._promotion_count = 0
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from multi-level cache"""
        # Try L1 first
        value = self.l1_cache.get(key, None)
        if value is not None:
            return value
        
        # Try L2 (this is where L2 hits should occur)
        value = self.l2_cache.get(key, None)
        if value is not None:
            # Promote hot data back to L1 if there's space
            if self.l1_cache._stats.entry_count < self.l1_cache.max_size:
                self.l1_cache.set(key, value, ttl=self.l1_cache.default_ttl)
                self._promotion_count += 1
                self.logger.debug(f"Promoted {key} from L2 to L1")
            return value
        
        return default
    
    def _handle_l1_overflow(self):
        """Handle L1 cache overflow by moving items to L2"""
        if self.l1_cache._stats.entry_count >= self.l1_cache.max_size:
            # Get some items from L1 to move to L2
            l1_keys = self.l1_cache.get_keys()
            if l1_keys:
                # Move oldest items to L2 (simple FIFO for demo)
                items_to_move = min(10, len(l1_keys) // 4)  # Move 25% or 10 items, whichever is smaller
                
                for key in l1_keys[:items_to_move]:
                    value = self.l1_cache.get(key, None)
                    if value is not None:
                        # Move to L2 with extended TTL
                        self.l2_cache.set(key, value, ttl=self.l2_cache.default_ttl)
                        self.l1_cache.delete(key)
                        self.logger.debug(f"Moved {key} from L1 to L2 due to overflow")
    
    def set(self, key: str, value: Any, l1_ttl: Optional[int] = None, l2_ttl: Optional[int] = None) -> bool:
        """Set value in multi-level cache"""
        # Handle L1 overflow before adding new items
        self._handle_l1_overflow()
        
        # Primary storage goes to L1
        l1_result = self.l1_cache.set(key, value, l1_ttl)
        
        return l1_result
    
    def delete(self, key: str) -> bool:
        """Delete from all cache levels"""
        l1_result = self.l1_cache.delete(key)
        l2_result = self.l2_cache.delete(key)
        return l1_result or l2_result
    
    def clear(self):
        """Clear all cache levels"""
        self.l1_cache.clear()
        self.l2_cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get combined statistics"""
        return {
            'l1_cache': self.l1_cache.get_stats(),
            'l2_cache': self.l2_cache.get_stats(),
            'total_memory_mb': round(
                (self.l1_cache._stats.size_bytes + self.l2_cache._stats.size_bytes) / 1024 / 1024, 2
            )
        }


class CacheManager:
    """Central cache manager for the application"""
    
    def __init__(self):
        # Different cache instances for different data types
        self.weather_cache = MultiLevelCache(
            l1_max_size=config.cache.max_size_weather,
            l1_ttl=config.cache.weather_ttl,
            l2_max_size=config.cache.max_size_weather * 2,
            l2_ttl=config.cache.weather_ttl * 2
        )
        
        self.alerts_cache = MultiLevelCache(
            l1_max_size=config.cache.max_size_alerts,
            l1_ttl=config.cache.alerts_ttl,
            l2_max_size=config.cache.max_size_alerts * 2,
            l2_ttl=config.cache.alerts_ttl * 2
        )
        
        self.disasters_cache = MultiLevelCache(
            l1_max_size=config.cache.max_size_disasters,
            l1_ttl=config.cache.disasters_ttl,
            l2_max_size=config.cache.max_size_disasters * 2,
            l2_ttl=config.cache.disasters_ttl * 2
        )
        
        # General purpose cache
        self.general_cache = MultiLevelCache(
            l1_max_size=200,
            l1_ttl=600,
            l2_max_size=500,
            l2_ttl=1800
        )
        
        self.logger = logging.getLogger(f"{__name__}.CacheManager")
        
        # Add performance monitor
        self.performance_monitor = PerformanceMonitor(self)
    
    def get_cache(self, cache_type: str) -> MultiLevelCache:
        """Get cache instance by type"""
        cache_map = {
            'weather': self.weather_cache,
            'alerts': self.alerts_cache,
            'disasters': self.disasters_cache,
            'general': self.general_cache
        }
        
        if cache_type not in cache_map:
            raise ValueError(f"Unknown cache type: {cache_type}")
        
        return cache_map[cache_type]
    
    def cached(
        self,
        cache_type: str = 'general',
        ttl: Optional[int] = None,
        key_func: Optional[Callable] = None
    ):
        """Decorator for caching function results"""
        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # Default key generation
                    key_parts = [func.__name__]
                    key_parts.extend([str(arg) for arg in args])
                    key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
                    cache_key = hashlib.md5('|'.join(key_parts).encode()).hexdigest()
                
                # Try to get from cache
                cache = self.get_cache(cache_type)
                result = cache.get(cache_key, None)
                
                if result is not None:
                    self.logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                    return result
                
                # Execute function and cache result
                self.logger.debug(f"Cache miss for {func.__name__}: {cache_key}")
                result = func(*args, **kwargs)
                
                # Cache the result
                cache.set(cache_key, result, l1_ttl=ttl, l2_ttl=ttl)
                
                return result
            
            return wrapper
        return decorator
    
    def invalidate_pattern(self, cache_type: str, pattern: str):
        """Invalidate cache entries matching pattern"""
        cache = self.get_cache(cache_type)
        
        # Get keys from both cache levels
        l1_keys = cache.l1_cache.get_keys()
        l2_keys = cache.l2_cache.get_keys()
        all_keys = set(l1_keys + l2_keys)
        
        # Remove matching keys
        for key in all_keys:
            if pattern in key:
                cache.delete(key)
                self.logger.debug(f"Invalidated cache key: {key}")
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all caches"""
        return {
            'weather': self.weather_cache.get_stats(),
            'alerts': self.alerts_cache.get_stats(),
            'disasters': self.disasters_cache.get_stats(),
            'general': self.general_cache.get_stats(),
            'timestamp': datetime.now().isoformat()
        }
    
    def clear_all(self):
        """Clear all caches"""
        self.weather_cache.clear()
        self.alerts_cache.clear()
        self.disasters_cache.clear()
        self.general_cache.clear()
        self.logger.info("All caches cleared")
    
    def optimize_memory(self):
        """Optimize memory usage across all caches"""
        # Force cleanup on all caches
        for cache_name in ['weather', 'alerts', 'disasters', 'general']:
            cache = self.get_cache(cache_name)
            with cache.l1_cache._lock:
                cache.l1_cache._enforce_limits()
            with cache.l2_cache._lock:
                cache.l2_cache._enforce_limits()
        
        self.logger.info("Memory optimization completed")


class PerformanceMonitor:
    """Monitors cache performance and provides optimization suggestions"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.logger = logging.getLogger(f"{__name__}.PerformanceMonitor")
    
    def analyze_performance(self) -> Dict[str, Any]:
        """Analyze cache performance and provide recommendations"""
        stats = self.cache_manager.get_all_stats()
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'overall_health': 'good',
            'recommendations': [],
            'cache_analysis': {}
        }
        
        for cache_name, cache_stats in stats.items():
            if cache_name == 'timestamp':
                continue
            
            cache_analysis = {
                'hit_rate': {
                    'l1': cache_stats['l1_cache']['hit_rate'],
                    'l2': cache_stats['l2_cache']['hit_rate']
                },
                'memory_usage': cache_stats['total_memory_mb'],
                'status': 'good'
            }
            
            recommendations = []
            
            # Check hit rates with more intelligent analysis
            l1_hit_rate = cache_stats['l1_cache']['hit_rate']
            l2_hit_rate = cache_stats['l2_cache']['hit_rate']
            l1_entry_count = cache_stats['l1_cache']['entry_count']
            l2_entry_count = cache_stats['l2_cache']['entry_count']
            
            if l1_hit_rate < 0.5:
                recommendations.append(f"L1 hit rate is low ({l1_hit_rate:.2%}). Consider increasing TTL or size.")
                cache_analysis['status'] = 'warning'
            
            # L2 cache analysis - it's normal for L2 to have low hit rate if L1 is working well
            if l2_hit_rate == 0.0 and l2_entry_count == 0:
                # L2 is not being used at all - this might be intentional if L1 is sufficient
                if l1_entry_count < cache_stats['l1_cache'].get('max_size', 100) * 0.8:
                    recommendations.append(f"L2 cache unused (normal if L1 sufficient). Current L1 utilization: {l1_entry_count} items.")
                else:
                    recommendations.append(f"L2 cache unused but L1 is near capacity. Cache overflow handling may need tuning.")
                    cache_analysis['status'] = 'warning'
            elif l2_hit_rate > 0 and l2_hit_rate < 0.1:
                recommendations.append(f"L2 hit rate is very low ({l2_hit_rate:.2%}). Data may not be flowing to L2 properly.")
                cache_analysis['status'] = 'warning'
            
            # Check memory usage
            if cache_stats['total_memory_mb'] > 100:
                recommendations.append(f"High memory usage ({cache_stats['total_memory_mb']:.1f} MB). Consider reducing cache sizes.")
                cache_analysis['status'] = 'warning'
            
            # Check eviction rates
            l1_eviction_rate = cache_stats['l1_cache']['evictions'] / max(cache_stats['l1_cache']['entry_count'], 1)
            if l1_eviction_rate > 0.3:
                recommendations.append(f"High L1 eviction rate. Consider increasing cache size.")
                cache_analysis['status'] = 'warning'
            
            cache_analysis['recommendations'] = recommendations
            analysis['cache_analysis'][cache_name] = cache_analysis
            
            # Update overall health
            if cache_analysis['status'] == 'warning' and analysis['overall_health'] == 'good':
                analysis['overall_health'] = 'warning'
            
            analysis['recommendations'].extend(recommendations)
        
        return analysis
    
    def get_optimization_suggestions(self) -> List[str]:
        """Get specific optimization suggestions"""
        analysis = self.analyze_performance()
        suggestions = []
        
        # General suggestions based on analysis
        if analysis['overall_health'] != 'good':
            suggestions.append("Consider running memory optimization")
        
        # Add cache-specific suggestions
        for cache_name, cache_analysis in analysis['cache_analysis'].items():
            if cache_analysis['status'] == 'warning':
                suggestions.extend([
                    f"{cache_name.title()} cache needs attention: " + rec
                    for rec in cache_analysis['recommendations']
                ])
        
        return suggestions


# Global cache manager instance
cache_manager = CacheManager()
performance_monitor = PerformanceMonitor(cache_manager)
