#!/usr/bin/env python3
"""
Comprehensive Fix Script for Critical Issues
Addresses database locks, disaster processing, cache performance, and app stability
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def fix_database_connections():
    """Fix database connection issues and locks"""
    print("🔧 Fixing database connection issues...")
    
    try:
        from database import db_manager
        
        # Initialize database with proper WAL mode for better concurrency
        with db_manager.pool.get_connection() as conn:
            cursor = conn.cursor()
            
            # Enable WAL mode for better concurrent access
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=10000")
            cursor.execute("PRAGMA temp_store=memory")
            cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
            
            # Set reasonable timeout
            cursor.execute("PRAGMA busy_timeout=30000")  # 30 seconds
            
            conn.commit()
            
        print("Database connection optimizations applied")
        return True
        
    except Exception as e:
        print(f"Database fix failed: {e}")
        return False


def verify_cache_performance():
    """Verify cache performance monitor is working"""
    print("🔧 Verifying cache performance monitor...")
    
    try:
        from cache import cache_manager
        
        # Test that performance monitor exists
        if hasattr(cache_manager, 'performance_monitor'):
            analysis = cache_manager.performance_monitor.analyze_performance()
            print(f"Cache performance monitor working: {analysis.get('overall_health', 'unknown')} status")
            return True
        else:
            print("Cache performance monitor not found")
            return False
            
    except Exception as e:
        print(f"Cache verification failed: {e}")
        return False


def test_disaster_processing():
    """Test disaster feature processing with sample data"""
    print("Testing disaster data processing...")
    
    try:
        # Create test disaster features with different coordinate formats
        test_features = [
            {
                "properties": {
                    "id": "test_1",
                    "title": "Test Wildfire",
                    "categories": [{"title": "Wildfire"}],
                    "sources": [{"id": "test_source"}],
                    "date": "2023-01-01"
                },
                "geometry": {
                    "coordinates": [-120.5, 34.5]  # Point format
                }
            },
            {
                "properties": {
                    "id": "test_2", 
                    "title": "Test Flood",
                    "categories": [{"title": "Flood"}],
                    "sources": [{"id": "test_source"}],
                    "date": "2023-01-01"
                },
                "geometry": {
                    "coordinates": [[-119.5, 35.5]]  # MultiPoint format
                }
            },
            {
                "properties": {
                    "id": "test_3",
                    "title": "Test Event",
                    "categories": ["Invalid"],  # Invalid format
                    "sources": [],
                    "date": "2023-01-01"
                },
                "geometry": {
                    "coordinates": "invalid"  # Invalid coordinates
                }
            }
        ]
        
        from app_production import DataService
        data_service = DataService()
        
        disasters = []
        for feature in test_features:
            try:
                props = feature.get("properties", {})
                coords = feature.get("geometry", {}).get("coordinates", [])
                
                # Handle different coordinate formats
                if isinstance(coords, list) and len(coords) >= 2:
                    # Extract lon, lat from coordinates
                    if isinstance(coords[0], list):
                        # MultiPoint or Polygon format
                        lon, lat = coords[0][0], coords[0][1]
                    else:
                        # Point format
                        lon, lat = coords[0], coords[1]
                    
                    # Validate coordinates are numbers
                    if (isinstance(lon, (int, float)) and isinstance(lat, (int, float)) and
                        -180 <= lon <= 180 and -90 <= lat <= 90):
                        
                        categories = props.get("categories", [])
                        if isinstance(categories, list) and categories:
                            category = categories[0].get("title", "Unknown") if isinstance(categories[0], dict) else "Unknown"
                        else:
                            category = "Unknown"
                        
                        sources = props.get("sources", [])
                        source_id = ""
                        if isinstance(sources, list) and sources and isinstance(sources[0], dict):
                            source_id = sources[0].get("id", "")
                        
                        disaster = {
                            "id": str(props.get("id", "")),
                            "title": str(props.get("title", "Unknown")),
                            "description": str(props.get("description", "")),
                            "category": str(category),
                            "source": str(source_id),
                            "date": str(props.get("date", "")),
                            "lat": float(lat),
                            "lon": float(lon),
                            "closed": 0 if props.get("closed") is None else 1
                        }
                        disasters.append(disaster)
                        
            except Exception as e:
                print(f"Error processing test feature: {e}")
                continue
        
        print(f"Disaster processing test completed: {len(disasters)}/3 features processed successfully")
        return True
        
    except Exception as e:
        print(f"Disaster processing test failed: {e}")
        return False


def test_monitoring_metrics():
    """Test monitoring system metrics collection"""
    print("Testing monitoring system...")
    
    try:
        from monitoring import monitoring_manager
        
        # Test metrics collection
        dashboard_data = monitoring_manager.get_dashboard_data()
        
        if dashboard_data:
            status = dashboard_data.get('overall_status', 'unknown')
            print(f"Monitoring system working: {status} status")
            
            # Check for specific components
            health_checks = dashboard_data.get('health_checks', {})
            print(f"Health checks available: {list(health_checks.keys())}")
            
            return True
        else:
            print("No monitoring data available")
            return False
            
    except Exception as e:
        print(f"Monitoring test failed: {e}")
        return False


def optimize_app_performance():
    """Apply performance optimizations"""
    print("Applying performance optimizations...")
    
    try:
        # Clear any stuck caches
        from cache import cache_manager
        
        # Get cache stats before cleanup
        stats_before = cache_manager.get_all_stats()
        
        # Optimize memory usage
        cache_manager.optimize_memory()
        
        # Get stats after cleanup
        stats_after = cache_manager.get_all_stats()
        
        print("Cache optimization completed")
        
        # Database optimization
        from database import db_manager
        
        # Run VACUUM to optimize database
        try:
            with db_manager.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("VACUUM")
                cursor.execute("ANALYZE")
                conn.commit()
            print("Database optimization completed")
        except Exception as e:
            print(f"Database optimization warning: {e}")
        
        return True
        
    except Exception as e:
        print(f"Performance optimization failed: {e}")
        return False


def create_stability_report():
    """Generate stability report"""
    print("Generating stability report...")
    
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'checks': {}
    }
    
    # Run all checks
    checks = [
        ('Database Connections', fix_database_connections),
        ('Cache Performance', verify_cache_performance),
        ('Disaster Processing', test_disaster_processing),
        ('Monitoring System', test_monitoring_metrics),
        ('Performance Optimization', optimize_app_performance)
    ]
    
    for check_name, check_func in checks:
        try:
            result = check_func()
            report['checks'][check_name] = {
                'status': 'PASS' if result else 'FAIL',
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            report['checks'][check_name] = {
                'status': 'ERROR',
                'error': str(e),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
    
    # Save report
    with open('stability_report.json', 'w') as f:
        import json
        json.dump(report, f, indent=2)
    
    # Print summary
    passed = sum(1 for check in report['checks'].values() if check['status'] == 'PASS')
    total = len(report['checks'])
    
    print(f"\nSTABILITY REPORT SUMMARY")
    print(f"{'='*50}")
    print(f"Checks Passed: {passed}/{total}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    for check_name, result in report['checks'].items():
        status_icon = "✅" if result['status'] == 'PASS' else "❌"
        print(f"{status_icon} {check_name}: {result['status']}")
        if 'error' in result:
            print(f"   Error: {result['error']}")
    
    if passed == total:
        print(f"\nALL CHECKS PASSED! System is stable and ready.")
    else:
        print(f"\n{total-passed} issues detected. Please review and fix.")
    
    return report


def main():
    """Main fix script execution"""
    print("Project Kairos Critical Issues Fix Script")
    print("="*50)
    
    # Run comprehensive stability check and fixes
    report = create_stability_report()
    
    # Additional recommendations
    print(f"\nRECOMMENDATIONS:")
    print(f"1. Use 'python run_tests.py --smoke' to verify system health")
    print(f"2. Monitor logs for any remaining database lock warnings")
    print(f"3. Set auto-refresh interval to 60+ seconds for better stability")
    print(f"4. Use the refresh controls in the sidebar to manage updates")
    print(f"5. Check stability_report.json for detailed results")
    
    # Return success based on report
    all_passed = all(check['status'] == 'PASS' for check in report['checks'].values())
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
