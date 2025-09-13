#!/usr/bin/env python3
"""
Test Runner
Provides convenient way to run different types of tests
"""

import os
import sys
import time
import argparse
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def run_command(cmd, description=""):
    """Run command and return result"""
    print(f"\n{'='*60}")
    if description:
        print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)
    
    start_time = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
        elapsed = time.time() - start_time
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        print(f"\nCompleted in {elapsed:.2f} seconds")
        print(f"Exit code: {result.returncode}")
        
        return result.returncode == 0
    except Exception as e:
        print(f"Error running command: {e}")
        return False


def run_unit_tests():
    """Run unit tests using unittest"""
    print("Running Unit Tests...")
    
    cmd = [
        sys.executable, 
        os.path.join("tests", "test_comprehensive.py"),
        "--unit"
    ]
    
    return run_command(cmd, "Unit Tests")


def run_integration_tests():
    """Run integration tests"""
    print("Running Integration Tests...")
    
    cmd = [
        sys.executable, 
        os.path.join("tests", "test_comprehensive.py"),
        "--integration"
    ]
    
    return run_command(cmd, "Integration Tests")


def run_performance_tests():
    """Run performance benchmarks"""
    print("Running Performance Tests...")
    
    cmd = [
        sys.executable, 
        os.path.join("tests", "test_comprehensive.py"),
        "--performance"
    ]
    
    return run_command(cmd, "Performance Benchmarks")


def run_all_tests():
    """Run all tests"""
    print("Running All Tests...")
    
    cmd = [
        sys.executable, 
        os.path.join("tests", "test_comprehensive.py")
    ]
    
    return run_command(cmd, "Complete Test Suite")


def run_pytest_tests():
    """Run tests with pytest (if available)"""
    print("Running Tests with pytest...")
    
    try:
        import pytest
        cmd = [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"]
        return run_command(cmd, "Pytest Test Suite")
    except ImportError:
        print("pytest not available. Install with: pip install pytest")
        return False


def run_security_checks():
    """Run security-related checks"""
    print("Running Security Checks...")
    
    success = True
    
    # Test security module directly
    try:
        from security import InputValidator, RateLimiter
        
        print("Testing Input Validation...")
        validator = InputValidator()
        
        # Test cases
        test_cases = [
            ("test@example.com", True, "Valid email"),
            ("invalid-email", False, "Invalid email"),
            ("validuser123", True, "Valid username"),
            ("user@invalid", False, "Invalid username"),
            ("<script>alert('xss')</script>", False, "XSS attempt should be detected"),
            ("'; DROP TABLE users; --", False, "SQL injection should be detected")
        ]
        
        for test_input, expected_valid, description in test_cases:
            if "@" in test_input:
                result = validator.validate_email(test_input)
            elif any(char in test_input for char in ['<', '>', ';', "'"]):
                threats = validator.check_malicious_patterns(test_input)
                result = len(threats) == 0
            else:
                result = validator.validate_username(test_input)
            
            status = "✓" if result == expected_valid else "✗"
            print(f"  {status} {description}: {test_input[:30]}...")
            
            if result != expected_valid:
                success = False
        
        print("Testing Rate Limiting...")
        rate_limiter = RateLimiter(requests_per_window=3, window_seconds=60)
        client_id = "test_client"
        
        # Should allow first 3 requests
        for i in range(3):
            if not rate_limiter.is_allowed(client_id):
                print(f"  ✗ Request {i+1} should be allowed")
                success = False
            else:
                print(f"  ✓ Request {i+1} allowed")
        
        # Should deny 4th request
        if rate_limiter.is_allowed(client_id):
            print("  ✗ Request 4 should be denied")
            success = False
        else:
            print("  ✓ Request 4 denied (rate limited)")
        
    except Exception as e:
        print(f"Error running security checks: {e}")
        success = False
    
    return success


def check_code_style():
    """Check code style with available tools"""
    print("Checking Code Style...")
    
    success = True
    
    # Try to run flake8 if available
    try:
        cmd = [sys.executable, "-m", "flake8", ".", "--max-line-length=120", "--ignore=E501,W503"]
        result = run_command(cmd, "Flake8 Code Style Check")
        if not result:
            print("Note: Some style issues found. Install flake8 for detailed checks: pip install flake8")
        success = success and result
    except FileNotFoundError:
        print("flake8 not found. Skipping style checks.")
        print("Install with: pip install flake8")
    
    return success


def run_smoke_tests():
    """Run basic smoke tests to verify system works"""
    print("Running Smoke Tests...")
    
    success = True
    
    try:
        # Test imports
        print("Testing module imports...")
        modules = ['config', 'database', 'cache', 'resilience', 'monitoring', 'security']
        
        for module in modules:
            try:
                __import__(module)
                print(f"  ✓ {module} imported successfully")
            except Exception as e:
                print(f"  ✗ {module} import failed: {e}")
                success = False
        
        # Test basic functionality
        print("\nTesting basic functionality...")
        
        from config import Config
        config = Config()
        print(f"  ✓ Config loaded: {config.app.name}")
        
        # Test database creation
        import tempfile
        from database import DatabaseManager
        
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        config.database.path = temp_db.name
        
        db_manager = DatabaseManager(config)
        db_manager.initialize_schema()
        print("  ✓ Database schema created")
        
        # Clean up
        db_manager.close()
        os.unlink(temp_db.name)
        
        print("  ✓ Database cleanup completed")
        
    except Exception as e:
        print(f"Smoke test failed: {e}")
        success = False
    
    return success


def generate_test_report():
    """Generate comprehensive test report"""
    print("\n" + "="*80)
    print("GENERATING COMPREHENSIVE TEST REPORT")
    print("="*80)
    
    results = {}
    
    # Run all test categories
    test_categories = [
        ("Smoke Tests", run_smoke_tests),
        ("Unit Tests", run_unit_tests),
        ("Integration Tests", run_integration_tests),
        ("Performance Tests", run_performance_tests),
        ("Security Checks", run_security_checks),
        ("Code Style", check_code_style),
    ]
    
    for category, test_func in test_categories:
        print(f"\n{'-'*60}")
        print(f"RUNNING {category.upper()}")
        print(f"{'-'*60}")
        
        start_time = time.time()
        try:
            success = test_func()
            elapsed = time.time() - start_time
            results[category] = {
                'success': success,
                'time': elapsed
            }
        except Exception as e:
            elapsed = time.time() - start_time
            results[category] = {
                'success': False,
                'time': elapsed,
                'error': str(e)
            }
            print(f"Error in {category}: {e}")
    
    # Generate summary report
    print("\n" + "="*80)
    print("TEST REPORT SUMMARY")
    print("="*80)
    
    total_time = sum(r['time'] for r in results.values())
    passed_tests = sum(1 for r in results.values() if r['success'])
    total_tests = len(results)
    
    for category, result in results.items():
        status = "✓ PASS" if result['success'] else "✗ FAIL"
        time_str = f"{result['time']:.2f}s"
        print(f"{category:<20} {status:<8} ({time_str})")
        
        if 'error' in result:
            print(f"                     Error: {result['error']}")
    
    print("-" * 80)
    print(f"Total Tests:     {total_tests}")
    print(f"Passed:          {passed_tests}")
    print(f"Failed:          {total_tests - passed_tests}")
    print(f"Success Rate:    {(passed_tests/total_tests*100):.1f}%")
    print(f"Total Time:      {total_time:.2f}s")
    
    if passed_tests == total_tests:
        print("\nALL TESTS PASSED! System is ready for production.")
    else:
        print(f"\n{total_tests - passed_tests} test categories failed. Please review and fix issues.")
    
    return passed_tests == total_tests


def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(
        description="Project Kairos Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py --all          # Run all tests
  python run_tests.py --unit         # Run unit tests only
  python run_tests.py --integration  # Run integration tests only
  python run_tests.py --performance  # Run performance benchmarks
  python run_tests.py --security     # Run security checks
  python run_tests.py --smoke        # Run smoke tests
  python run_tests.py --style        # Check code style
  python run_tests.py --report       # Generate comprehensive report
        """
    )
    
    parser.add_argument('--all', action='store_true', help='Run all tests')
    parser.add_argument('--unit', action='store_true', help='Run unit tests')
    parser.add_argument('--integration', action='store_true', help='Run integration tests')
    parser.add_argument('--performance', action='store_true', help='Run performance tests')
    parser.add_argument('--security', action='store_true', help='Run security checks')
    parser.add_argument('--smoke', action='store_true', help='Run smoke tests')
    parser.add_argument('--style', action='store_true', help='Check code style')
    parser.add_argument('--report', action='store_true', help='Generate comprehensive test report')
    parser.add_argument('--pytest', action='store_true', help='Run tests with pytest')
    
    args = parser.parse_args()
    
    # If no specific test type is specified, run smoke tests
    if not any(vars(args).values()):
        args.smoke = True
    
    success = True
    
    if args.report:
        success = generate_test_report()
    else:
        if args.smoke:
            success = success and run_smoke_tests()
        if args.unit:
            success = success and run_unit_tests()
        if args.integration:
            success = success and run_integration_tests()
        if args.performance:
            success = success and run_performance_tests()
        if args.security:
            success = success and run_security_checks()
        if args.style:
            success = success and check_code_style()
        if args.all:
            success = success and run_all_tests()
        if args.pytest:
            success = success and run_pytest_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
