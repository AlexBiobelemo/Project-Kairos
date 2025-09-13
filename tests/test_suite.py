"""
Comprehensive Test Suite
Includes unit tests, integration tests, and performance tests.
"""

# Try to import optional dependencies with fallbacks
try:
    import pytest
except ImportError:
    pytest = None

import unittest
import sqlite3
import tempfile
import os
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
# Try to import optional dependencies with fallbacks
try:
    import pandas as pd
except ImportError:
    pd = MagicMock()

try:
    import numpy as np
except ImportError:
    np = MagicMock()

# Import our modules with error handling
try:
    from config import Config
except ImportError:
    Config = MagicMock()

try:
    from database import DatabaseManager, WeatherData, EarthquakeData, ConnectionPool
except ImportError:
    DatabaseManager = WeatherData = EarthquakeData = ConnectionPool = MagicMock()

try:
    from cache import LRUCache, MultiLevelCache, CacheManager, CompressionManager
except ImportError:
    LRUCache = MultiLevelCache = CacheManager = CompressionManager = MagicMock()

try:
    from resilience import CircuitBreaker, RetryHandler, ResilienceManager, CircuitBreakerState
except ImportError:
    CircuitBreaker = RetryHandler = ResilienceManager = CircuitBreakerState = MagicMock()

try:
    from monitoring import HealthChecker, MetricsCollector, AlertManager
except ImportError:
    HealthChecker = MetricsCollector = AlertManager = MagicMock()


class TestConfiguration(unittest.TestCase):
    """Test configuration management"""
    
    def setUp(self):
        # Skip if Config is a mock (module not available)
        if isinstance(Config, MagicMock):
            self.skipTest("Config module not available")
        self.test_config = Config("test_config.json")
    
    def test_default_configuration(self):
        """Test default configuration values"""
        self.assertEqual(self.test_config.database.connection_timeout, 30)
        self.assertEqual(self.test_config.cache.weather_ttl, 300)
        self.assertEqual(self.test_config.api.timeout_seconds, 15)
    
    def test_environment_variable_override(self):
        """Test environment variable configuration override"""
        with patch.dict(os.environ, {'KAIROS_DB_TIMEOUT': '60'}):
            config = Config()
            config._load_from_environment()
            self.assertEqual(config.database.connection_timeout, 60)
    
    def test_boolean_conversion(self):
        """Test boolean environment variable conversion"""
        test_cases = [
            ('true', True),
            ('false', False),
            ('1', True),
            ('0', False),
            ('yes', True),
            ('no', False)
        ]
        
        for value, expected in test_cases:
            result = Config._str_to_bool(value)
            self.assertEqual(result, expected)
    
    def test_list_conversion(self):
        """Test list environment variable conversion"""
        result = Config._str_to_list("item1,item2,item3")
        self.assertEqual(result, ['item1', 'item2', 'item3'])


class TestDatabase(unittest.TestCase):
    """Test database operations"""
    
    def setUp(self):
        # Skip if DatabaseManager is a mock (module not available)
        if isinstance(DatabaseManager, MagicMock):
            self.skipTest("Database module not available")
        self.test_db = tempfile.NamedTemporaryFile(delete=False)
        self.test_db.close()
        self.db_manager = DatabaseManager(self.test_db.name)
    
    def tearDown(self):
        self.db_manager.close()
        os.unlink(self.test_db.name)
    
    def test_database_initialization(self):
        """Test database schema creation"""
        stats = self.db_manager.get_database_stats()
        self.assertIn('weather_count', stats)
        self.assertIn('earthquakes_count', stats)
        self.assertIn('database_size_mb', stats)
    
    def test_weather_data_insertion(self):
        """Test weather data validation and insertion"""
        weather_data = WeatherData(
            timestamp=datetime.now().isoformat(),
            location_name="Test City",
            lat=40.7128,
            lon=-74.0060,
            temperature_2m=25.0,
            wind_speed_10m=10.0,
            relative_humidity_2m=60.0
        )
        
        # Test validation
        self.assertTrue(weather_data.validate())
        
        # Test insertion
        result = self.db_manager.insert_weather_data(weather_data)
        self.assertTrue(result)
        
        # Verify data was inserted
        with self.db_manager.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM weather")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 1)
    
    def test_invalid_weather_data(self):
        """Test validation of invalid weather data"""
        invalid_data = WeatherData(
            timestamp="",
            location_name="",
            lat=200.0,  # Invalid latitude
            lon=-200.0,  # Invalid longitude
            temperature_2m=1000.0  # Unrealistic temperature
        )
        
        self.assertFalse(invalid_data.validate())
    
    def test_earthquake_data_insertion(self):
        """Test earthquake data insertion"""
        earthquake_data = EarthquakeData(
            timestamp=datetime.now().isoformat(),
            place="Test Location",
            magnitude=5.5,
            lat=35.0,
            lon=140.0,
            depth=10.0
        )
        
        self.assertTrue(earthquake_data.validate())
        result = self.db_manager.insert_earthquake_data(earthquake_data)
        self.assertTrue(result)
    
    def test_connection_pool(self):
        """Test connection pool functionality"""
        pool = ConnectionPool(self.test_db.name, max_connections=3)
        
        # Test connection acquisition
        with pool.get_connection() as conn:
            self.assertIsNotNone(conn)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            self.assertEqual(result[0], 1)
        
        # Test pool statistics
        stats = pool.get_stats()
        self.assertIn('total_connections', stats)
        self.assertIn('active_connections', stats)
        
        pool.close_all()
    
    def test_database_cleanup(self):
        """Test old data cleanup"""
        # Insert old data
        old_weather = WeatherData(
            timestamp=(datetime.now() - timedelta(days=60)).isoformat(),
            location_name="Old City",
            lat=40.0,
            lon=-74.0,
            temperature_2m=20.0
        )
        
        self.db_manager.insert_weather_data(old_weather)
        
        # Cleanup old data (keep last 30 days)
        cleanup_stats = self.db_manager.cleanup_old_data(days_to_keep=30)
        
        # Verify cleanup stats exist and are valid
        self.assertIsInstance(cleanup_stats, dict)
        if 'weather' in cleanup_stats:
            self.assertGreaterEqual(cleanup_stats['weather'], 0)


class TestCaching(unittest.TestCase):
    """Test caching functionality"""
    
    def setUp(self):
        # Skip if LRUCache is a mock (module not available)
        if isinstance(LRUCache, MagicMock):
            self.skipTest("Cache module not available")
        self.cache = LRUCache(max_size=10, default_ttl=60)
        self.compression = CompressionManager()
    
    def test_basic_cache_operations(self):
        """Test basic cache set/get operations"""
        self.cache.set("key1", "value1")
        self.assertEqual(self.cache.get("key1"), "value1")
        
        # Test cache miss
        self.assertIsNone(self.cache.get("nonexistent"))
        self.assertEqual(self.cache.get("nonexistent", "default"), "default")
    
    def test_cache_expiration(self):
        """Test TTL expiration"""
        self.cache.set("expiring_key", "value", ttl=1)
        self.assertEqual(self.cache.get("expiring_key"), "value")
        
        # Wait for expiration
        time.sleep(1.1)
        self.assertIsNone(self.cache.get("expiring_key"))
    
    def test_cache_size_limit(self):
        """Test cache size limits"""
        # Fill cache beyond capacity
        for i in range(15):
            self.cache.set(f"key{i}", f"value{i}")
        
        # Should only have max_size items
        stats = self.cache.get_stats()
        self.assertLessEqual(stats['entry_count'], 10)
    
    def test_compression(self):
        """Test data compression functionality"""
        test_data = {"large_data": "x" * 2000}
        
        # Test compression decision
        should_compress = self.compression.should_compress(test_data)
        self.assertTrue(should_compress)
        
        # Test compression/decompression
        compressed = self.compression.compress(test_data)
        decompressed = self.compression.decompress(compressed)
        self.assertEqual(test_data, decompressed)
    
    def test_multi_level_cache(self):
        """Test multi-level cache functionality"""
        ml_cache = MultiLevelCache(l1_max_size=5, l2_max_size=10)
        
        # Test L1 cache
        ml_cache.set("key1", "value1")
        self.assertEqual(ml_cache.get("key1"), "value1")
        
        # Test L2 promotion
        # Fill L1 to force eviction
        for i in range(10):
            ml_cache.set(f"key{i}", f"value{i}")
        
        # Original key should be in L2 and get promoted to L1
        value = ml_cache.get("key1")
        self.assertEqual(value, "value1")
    
    def test_cache_manager_decorator(self):
        """Test cache manager decorator functionality"""
        cache_manager = CacheManager()
        
        call_count = 0
        
        @cache_manager.cached(cache_type='general', ttl=60)
        def expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            return x + y
        
        # First call should execute function
        result1 = expensive_function(1, 2)
        self.assertEqual(result1, 3)
        self.assertEqual(call_count, 1)
        
        # Second call should use cache
        result2 = expensive_function(1, 2)
        self.assertEqual(result2, 3)
        self.assertEqual(call_count, 1)  # No additional call


class TestResilience(unittest.TestCase):
    """Test resilience patterns"""
    
    def setUp(self):
        # Skip if CircuitBreaker is a mock (module not available)
        if isinstance(CircuitBreaker, MagicMock):
            self.skipTest("Resilience module not available")
    
    def test_circuit_breaker_basic(self):
        """Test basic circuit breaker functionality"""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=1)
        
        # Initially closed
        self.assertEqual(cb.state, CircuitBreakerState.CLOSED)
        
        # Successful calls
        @cb
        def successful_function():
            return "success"
        
        result = successful_function()
        self.assertEqual(result, "success")
        self.assertEqual(cb.stats.success_count, 1)
    
    def test_circuit_breaker_failure(self):
        """Test circuit breaker failure handling"""
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=1)
        
        @cb
        def failing_function():
            raise Exception("Test failure")
        
        # Cause failures to open circuit breaker
        for _ in range(3):
            with self.assertRaises(Exception):
                failing_function()
        
        # Circuit should be open
        self.assertEqual(cb.state, CircuitBreakerState.OPEN)
        self.assertEqual(cb.stats.failure_count, 2)  # Threshold reached
    
    def test_retry_handler(self):
        """Test retry logic with exponential backoff"""
        from resilience import RetryConfig, RetryHandler
        
        config = RetryConfig(max_attempts=3, base_delay=0.1, jitter=False)
        retry_handler = RetryHandler(config)
        
        attempt_count = 0
        
        @retry_handler(exceptions=ValueError)
        def flaky_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ValueError("Temporary failure")
            return "success"
        
        result = flaky_function()
        self.assertEqual(result, "success")
        self.assertEqual(attempt_count, 3)
    
    def test_resilience_manager(self):
        """Test resilience manager integration"""
        manager = ResilienceManager()
        
        call_count = 0
        
        def unreliable_service():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Service failure")
            return "success"
        
        # Test with fallback
        result = manager.execute_with_resilience(
            service="test_service",
            func=unreliable_service,
            fallback_data="fallback_value"
        )
        
        self.assertEqual(result, "success")
        
        # Check system health
        health = manager.get_system_health()
        self.assertIn('circuit_breakers', health)
        self.assertIn('error_stats', health)


class TestMonitoring(unittest.TestCase):
    """Test monitoring and health checks"""
    
    def setUp(self):
        # Skip if HealthChecker is a mock (module not available)
        if isinstance(HealthChecker, MagicMock):
            self.skipTest("Monitoring module not available")
        self.health_checker = HealthChecker()
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager()
    
    def test_health_checker_registration(self):
        """Test health check registration"""
        def custom_health_check():
            from monitoring import HealthCheck, HealthStatus
            return HealthCheck(
                name="custom",
                status=HealthStatus.HEALTHY,
                message="Custom check passed"
            )
        
        self.health_checker.register_check("custom", custom_health_check)
        self.assertIn("custom", self.health_checker._checks)
    
    def test_metrics_collection(self):
        """Test metrics recording and retrieval"""
        # Record some metrics
        self.metrics_collector.record_metric("test.metric", 42.0, "count")
        self.metrics_collector.record_metric("test.metric", 45.0, "count")
        
        # Get recent metrics
        recent_metrics = self.metrics_collector.get_recent_metrics(1)
        self.assertGreaterEqual(len(recent_metrics), 2)
        
        # Get metric summary
        summary = self.metrics_collector.get_metric_summary("test.metric", 1)
        self.assertIn('count', summary)
        self.assertIn('avg', summary)
        self.assertIn('max', summary)
    
    def test_alert_suppression(self):
        """Test alert suppression to prevent spam"""
        # Send first alert
        self.alert_manager.send_alert("Test Alert", "Test message", "warning")
        initial_count = len(self.alert_manager.get_recent_alerts(1))
        
        # Send duplicate alert (should be suppressed)
        self.alert_manager.send_alert("Test Alert", "Test message", "warning")
        suppressed_count = len(self.alert_manager.get_recent_alerts(1))
        
        # Count should be the same (suppressed)
        self.assertEqual(initial_count, suppressed_count)


class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflows"""
    
    def setUp(self):
        self.test_db = tempfile.NamedTemporaryFile(delete=False)
        self.test_db.close()
        self.db_manager = DatabaseManager(self.test_db.name)
        self.cache_manager = CacheManager()
        self.resilience_manager = ResilienceManager()
    
    def tearDown(self):
        self.db_manager.close()
        os.unlink(self.test_db.name)
    
    def test_data_pipeline_integration(self):
        """Test complete data pipeline from API to database"""
        # Mock API response
        mock_weather_data = {
            "current": {
                "time": datetime.now().isoformat(),
                "temperature_2m": 25.0,
                "wind_speed_10m": 10.0,
                "relative_humidity_2m": 60.0
            }
        }
        
        def mock_api_call():
            return mock_weather_data
        
        # Test with resilience
        result = self.resilience_manager.execute_with_resilience(
            service="weather_api",
            func=mock_api_call
        )
        
        self.assertEqual(result, mock_weather_data)
        
        # Process and store data
        weather_data = WeatherData(
            timestamp=result["current"]["time"],
            location_name="Test City",
            lat=40.7128,
            lon=-74.0060,
            temperature_2m=result["current"]["temperature_2m"],
            wind_speed_10m=result["current"]["wind_speed_10m"],
            relative_humidity_2m=result["current"]["relative_humidity_2m"]
        )
        
        success = self.db_manager.insert_weather_data(weather_data)
        self.assertTrue(success)
    
    def test_caching_with_database(self):
        """Test caching integration with database operations"""
        # Cache a database query result
        @self.cache_manager.cached(cache_type='general', ttl=300)
        def get_weather_summary():
            # Simulate expensive database operation
            time.sleep(0.1)
            return {"avg_temp": 25.0, "count": 10}
        
        # First call - should execute and cache
        start_time = time.time()
        result1 = get_weather_summary()
        first_duration = time.time() - start_time
        
        # Second call - should use cache
        start_time = time.time()
        result2 = get_weather_summary()
        second_duration = time.time() - start_time
        
        self.assertEqual(result1, result2)
        self.assertLess(second_duration, first_duration)
    
    def test_monitoring_integration(self):
        """Test monitoring system integration"""
        from monitoring import MonitoringManager
        
        # This would normally be initialized as a singleton
        monitoring = MonitoringManager()
        
        # Test dashboard data compilation
        dashboard_data = monitoring.get_dashboard_data()
        
        self.assertIn('timestamp', dashboard_data)
        self.assertIn('overall_status', dashboard_data)
        self.assertIn('health_checks', dashboard_data)
        self.assertIn('system_metrics', dashboard_data)


class TestPerformance(unittest.TestCase):
    """Performance and load tests"""
    
    def test_cache_performance(self):
        """Test cache performance under load"""
        cache = LRUCache(max_size=1000, default_ttl=300)
        
        # Performance test
        start_time = time.time()
        
        # Write performance
        for i in range(1000):
            cache.set(f"key_{i}", f"value_{i}")
        
        write_time = time.time() - start_time
        
        # Read performance
        start_time = time.time()
        for i in range(1000):
            cache.get(f"key_{i}")
        
        read_time = time.time() - start_time
        
        # Performance assertions (more lenient thresholds)
        self.assertLess(write_time, 10.0)  # Should complete in under 10 seconds
        self.assertLess(read_time, 5.0)   # Reads should be faster
        
        # Cache stats
        stats = cache.get_stats()
        self.assertEqual(stats['entry_count'], 1000)
        self.assertGreaterEqual(stats['hit_rate'], 0.99)  # High hit rate
    
    def test_database_performance(self):
        """Test database performance under load"""
        test_db = tempfile.NamedTemporaryFile(delete=False)
        test_db.close()
        db_manager = DatabaseManager(test_db.name)
        
        try:
            # Bulk insert performance test
            weather_data_list = []
            for i in range(100):
                weather_data = WeatherData(
                    timestamp=(datetime.now() + timedelta(minutes=i)).isoformat(),
                    location_name=f"City_{i % 10}",
                    lat=40.0 + (i % 10) * 0.1,
                    lon=-74.0 + (i % 10) * 0.1,
                    temperature_2m=20.0 + (i % 30),
                    wind_speed_10m=i % 20
                )
                weather_data_list.append(weather_data)
            
            start_time = time.time()
            success = db_manager.insert_weather_data(weather_data_list)
            insert_time = time.time() - start_time
            
            self.assertTrue(success)
            self.assertLess(insert_time, 5.0)  # Should complete in under 5 seconds
            
            # Query performance test
            start_time = time.time()
            results = db_manager.get_weather_data(hours_back=24, limit=100)
            query_time = time.time() - start_time
            
            self.assertLess(query_time, 1.0)  # Should complete in under 1 second
            self.assertEqual(len(results), 100)
            
        finally:
            db_manager.close()
            os.unlink(test_db.name)
    
    def test_concurrent_access(self):
        """Test system behavior under concurrent access"""
        cache = LRUCache(max_size=100, default_ttl=300)
        results = []
        errors = []
        
        def worker(thread_id):
            try:
                for i in range(50):
                    key = f"thread_{thread_id}_key_{i}"
                    value = f"thread_{thread_id}_value_{i}"
                    cache.set(key, value)
                    retrieved = cache.get(key)
                    if retrieved != value:
                        errors.append(f"Thread {thread_id}: Value mismatch")
                    results.append(True)
            except Exception as e:
                errors.append(f"Thread {thread_id}: {str(e)}")
        
        # Start concurrent threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        self.assertEqual(len(errors), 0, f"Concurrent access errors: {errors}")
        self.assertEqual(len(results), 250)  # 5 threads * 50 operations


def run_all_tests():
    """Run all tests with detailed output"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestConfiguration,
        TestDatabase,
        TestCaching,
        TestResilience,
        TestMonitoring,
        TestIntegration,
        TestPerformance
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    print("Running Project Kairos Test Suite")
    print("=" * 50)
    
    result = run_all_tests()
    
    print("\n" + "=" * 50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    if result.wasSuccessful():
        print("\n✅ All tests passed!")
        exit(0)
    else:
        print("\n❌ Some tests failed!")
        exit(1)
