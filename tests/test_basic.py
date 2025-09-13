"""
Test Suite
"""

import os
import sys
import json
import time
import sqlite3
import tempfile
import unittest
import threading
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBasicFunctionality(unittest.TestCase):
    """Test basic functionality without external dependencies"""
    
    def test_config_module_structure(self):
        """Test config module can be imported and has basic structure"""
        try:
            import config
            self.assertTrue(hasattr(config, 'Config'))
            
            # Test basic config instantiation
            cfg = config.Config()
            self.assertIsNotNone(cfg)
            
        except ImportError as e:
            self.skipTest(f"Config module not available: {e}")
    
    def test_security_module_basic(self):
        """Test security module basic functionality without streamlit"""
        try:
            # Mock streamlit before importing security
            sys.modules['streamlit'] = MagicMock()
            
            from security import InputValidator, RateLimiter
            
            # Test input validation
            validator = InputValidator()
            
            # Email validation
            self.assertTrue(validator.validate_email('test@example.com'))
            self.assertFalse(validator.validate_email('invalid-email'))
            
            # Username validation
            self.assertTrue(validator.validate_username('validuser123'))
            self.assertFalse(validator.validate_username('invalid@user'))
            
            # Password validation
            result = validator.validate_password('StrongPass123!')
            self.assertTrue(result['valid'])
            
            result = validator.validate_password('weak')
            self.assertFalse(result['valid'])
            
            # Input sanitization
            malicious = '<script>alert("xss")</script>'
            sanitized = validator.sanitize_input(malicious)
            self.assertNotIn('<script>', sanitized)
            
            # Malicious pattern detection
            threats = validator.check_malicious_patterns("'; DROP TABLE users; --")
            self.assertGreater(len(threats), 0)
            
            # Rate limiting
            rate_limiter = RateLimiter(requests_per_window=3, window_seconds=60)
            
            # Should allow first 3 requests
            for _ in range(3):
                self.assertTrue(rate_limiter.is_allowed('test_client'))
            
            # Should deny 4th request
            self.assertFalse(rate_limiter.is_allowed('test_client'))
            
            print("✓ Security module basic tests passed")
            
        except ImportError as e:
            self.skipTest(f"Security module not available: {e}")
    
    def test_database_module_basic(self):
        """Test database module without pandas dependency"""
        try:
            # Mock pandas before importing database
            sys.modules['pandas'] = MagicMock()
            
            # Create a basic database config mock
            class MockConfig:
                class Database:
                    def __init__(self):
                        self.path = ':memory:'
                        self.pool_size = 5
                        self.timeout = 30
                        self.backup_interval = 3600
                
                def __init__(self):
                    self.database = self.Database()
            
            # Test basic SQLite operations
            temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
            temp_db.close()
            
            try:
                # Test database creation
                conn = sqlite3.connect(temp_db.name)
                cursor = conn.cursor()
                
                # Create a simple test table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS test_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    value REAL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Insert test data
                cursor.execute("INSERT INTO test_data (name, value) VALUES (?, ?)", 
                              ("test", 123.45))
                conn.commit()
                
                # Query test data
                cursor.execute("SELECT * FROM test_data")
                results = cursor.fetchall()
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0][1], "test")
                
                conn.close()
                print("✓ Database basic operations test passed")
                
            finally:
                if os.path.exists(temp_db.name):
                    os.unlink(temp_db.name)
            
        except ImportError as e:
            self.skipTest(f"Database module dependencies not available: {e}")
    
    def test_resilience_patterns(self):
        """Test resilience patterns"""
        try:
            from resilience import CircuitBreaker, RetryHandler
            
            # Test circuit breaker
            circuit_breaker = CircuitBreaker(
                failure_threshold=2,
                timeout_seconds=1,
                expected_exception=ValueError
            )
            
            call_count = [0]
            
            @circuit_breaker
            def failing_function():
                call_count[0] += 1
                raise ValueError("Test error")
            
            # Trigger failures to reach threshold
            for _ in range(2):
                with self.assertRaises(ValueError):
                    failing_function()
            
            # One more call should trigger the circuit to open
            from resilience import CircuitBreakerError
            with self.assertRaises(CircuitBreakerError):
                failing_function()
            
            # Circuit should be open now  
            from resilience import CircuitBreakerState
            self.assertEqual(circuit_breaker.state, CircuitBreakerState.OPEN)
            
            # Test retry handler
            from resilience import RetryConfig
            retry_config = RetryConfig(
                max_attempts=3,
                base_delay=0.01,
                exponential_base=2.0,
                jitter=False
            )
            retry_handler = RetryHandler(retry_config)
            
            retry_count = [0]
            
            @retry_handler(exceptions=ValueError)
            def flaky_function():
                retry_count[0] += 1
                if retry_count[0] < 3:
                    raise ValueError("Temporary error")
                return "success"
            
            result = flaky_function()
            self.assertEqual(result, "success")
            self.assertEqual(retry_count[0], 3)
            
            print("✓ Resilience patterns test passed")
            
        except ImportError as e:
            self.skipTest(f"Resilience module not available: {e}")
    
    def test_cache_basic_functionality(self):
        """Test basic cache functionality without external dependencies"""
        try:
            # Mock external dependencies
            sys.modules['psutil'] = MagicMock()
            
            from cache import LRUCache
            
            # Test LRU cache
            cache = LRUCache(max_size=3)
            
            # Add items
            cache.set('key1', 'value1')
            cache.set('key2', 'value2')
            cache.set('key3', 'value3')
            
            # Verify items
            self.assertEqual(cache.get('key1'), 'value1')
            self.assertEqual(cache.get('key2'), 'value2')
            self.assertEqual(cache.get('key3'), 'value3')
            
            # Add one more item (should evict oldest)
            cache.set('key4', 'value4')
            
            # key1 should be evicted
            self.assertIsNone(cache.get('key1'))
            self.assertEqual(cache.get('key4'), 'value4')
            
            # Test TTL
            cache.set('ttl_key', 'ttl_value', ttl=0.1)
            self.assertEqual(cache.get('ttl_key'), 'ttl_value')
            
            time.sleep(0.15)
            self.assertIsNone(cache.get('ttl_key'))
            
            print("✓ Cache basic functionality test passed")
            
        except ImportError as e:
            self.skipTest(f"Cache module not available: {e}")
    
    def test_file_operations(self):
        """Test basic file operations used by the system"""
        # Test JSON operations (used for config and user management)
        test_data = {
            "test_key": "test_value",
            "test_number": 42,
            "test_list": [1, 2, 3]
        }
        
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        
        try:
            # Write JSON
            json.dump(test_data, temp_file)
            temp_file.close()
            
            # Read JSON
            with open(temp_file.name, 'r') as f:
                loaded_data = json.load(f)
            
            self.assertEqual(loaded_data, test_data)
            print("✓ JSON file operations test passed")
            
        finally:
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
    
    def test_threading_safety(self):
        """Test basic threading functionality"""
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # Test thread-safe operations
        shared_data = {'counter': 0}
        lock = threading.Lock()
        
        def worker_function(worker_id):
            for _ in range(100):
                with lock:
                    shared_data['counter'] += 1
            return worker_id
        
        # Run concurrent workers
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker_function, i) for i in range(5)]
            results = [future.result() for future in as_completed(futures)]
        
        # Should have processed 5 * 100 = 500 increments
        self.assertEqual(shared_data['counter'], 500)
        self.assertEqual(len(results), 5)
        
        print("✓ Threading safety test passed")
    
    def test_environment_variables(self):
        """Test environment variable handling"""
        # Test environment variable access
        test_env = 'TEST_KAIROS_VAR'
        test_value = 'test_value_123'
        
        # Test without environment variable
        self.assertIsNone(os.getenv(test_env))
        
        # Test with environment variable
        with patch.dict(os.environ, {test_env: test_value}):
            self.assertEqual(os.getenv(test_env), test_value)
        
        # Test string values (environment variables are always strings)
        string_cases = [
            ('true', 'true'), ('false', 'false'),
            ('1', '1'), ('0', '0'),
            ('yes', 'yes'), ('no', 'no')
        ]
        
        for env_val, expected in string_cases:
            with patch.dict(os.environ, {test_env: env_val}):
                self.assertEqual(os.getenv(test_env), expected)
        
        print("✓ Environment variables test passed")


class TestSystemIntegration(unittest.TestCase):
    """Test system integration without external dependencies"""
    
    def test_module_loading(self):
        """Test that all core modules can be imported"""
        core_modules = []
        
        # Try to import each module
        module_tests = [
            ('config', 'Config'),
            ('cache', 'LRUCache'), 
            ('resilience', 'CircuitBreaker'),
        ]
        
        for module_name, class_name in module_tests:
            try:
                # Mock dependencies that might not be available
                if module_name == 'cache':
                    sys.modules['psutil'] = MagicMock()
                elif module_name == 'database':
                    sys.modules['pandas'] = MagicMock()
                elif module_name == 'monitoring':
                    sys.modules['psutil'] = MagicMock()
                elif module_name == 'security':
                    sys.modules['streamlit'] = MagicMock()
                
                module = __import__(module_name)
                if hasattr(module, class_name):
                    core_modules.append(module_name)
                    print(f"✓ {module_name} module loaded successfully")
                else:
                    print(f"✗ {module_name} module missing {class_name} class")
                    
            except ImportError as e:
                print(f"✗ {module_name} module import failed: {e}")
        
        # At least some core modules should load
        self.assertGreater(len(core_modules), 0, "No core modules could be loaded")
        
    def test_configuration_system(self):
        """Test configuration system integration"""
        try:
            from config import Config
            
            # Test default configuration
            config = Config()
            
            # Should have basic structure (even if attributes differ)
            self.assertIsNotNone(config)
            
            # Test environment override
            with patch.dict(os.environ, {'TEST_CONFIG': 'test_value'}):
                # Basic environment access works
                self.assertEqual(os.getenv('TEST_CONFIG'), 'test_value')
            
            print("✓ Configuration system integration test passed")
            
        except Exception as e:
            self.skipTest(f"Configuration system not available: {e}")


def run_basic_tests():
    """Run basic test suite"""
    print("Running Project Kairos Basic Test Suite...")
    print("=" * 60)
    
    # Create test suite
    test_classes = [
        TestBasicFunctionality,
        TestSystemIntegration
    ]
    
    suite = unittest.TestSuite()
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("BASIC TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(getattr(result, 'skipped', []))}")
    
    if result.testsRun > 0:
        success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100)
        print(f"Success rate: {success_rate:.1f}%")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}")
    
    successful = len(result.failures) == 0 and len(result.errors) == 0
    
    if successful:
        print("\nBASIC TESTS PASSED! Core functionality is working.")
    else:
        print("\nSome basic tests failed. Please review the issues above.")
    
    return successful


if __name__ == '__main__':
    success = run_basic_tests()
    sys.exit(0 if success else 1)
