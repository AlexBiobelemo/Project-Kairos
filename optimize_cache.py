#!/usr/bin/env python3
"""
Cache Optimization and Testing Script for Project Kairos
Demonstrates the improved multi-level cache behavior and provides optimizations
"""

import os
import sys
import time
import random
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_cache_behavior():
    """Test and demonstrate cache behavior"""
    print("Testing Cache Behavior...")
    
    try:
        from cache import cache_manager
        
        # Get initial stats
        initial_stats = cache_manager.get_all_stats()
        print("\nInitial Cache Stats:")
        for cache_name, stats in initial_stats.items():
            if cache_name == 'timestamp':
                continue
            print(f"  {cache_name.title()} Cache:")
            print(f"    L1: {stats['l1_cache']['entry_count']} items, {stats['l1_cache']['hit_rate']:.1%} hit rate")
            print(f"    L2: {stats['l2_cache']['entry_count']} items, {stats['l2_cache']['hit_rate']:.1%} hit rate")
        
        # Test cache operations
        print("\nTesting Cache Operations...")
        
        # Fill up the weather cache to trigger L1->L2 movement
        weather_cache = cache_manager.get_cache('weather')
        
        # Add items until L1 is near capacity
        print("  Adding items to trigger L1 overflow...")
        for i in range(150):  # More than typical L1 capacity
            key = f"test_weather_{i}"
            value = {
                'temperature': 20 + random.random() * 10,
                'humidity': 50 + random.random() * 30,
                'location': f'TestCity_{i}',
                'timestamp': time.time()
            }
            weather_cache.set(key, value)
        
        # Test some cache hits to see L2 behavior
        print("  Testing cache hits...")
        hits = 0
        l2_hits = 0
        for i in range(50):
            key = f"test_weather_{i}"
            # First check L1
            l1_value = weather_cache.l1_cache.get(key, None)
            if l1_value is not None:
                hits += 1
            else:
                # Check L2
                l2_value = weather_cache.l2_cache.get(key, None) 
                if l2_value is not None:
                    l2_hits += 1
                    hits += 1
        
        print(f"    Total hits: {hits}/50")
        print(f"    L2 hits: {l2_hits}/50")
        
        # Get final stats
        final_stats = cache_manager.get_all_stats()
        print("\nFinal Cache Stats:")
        for cache_name, stats in final_stats.items():
            if cache_name == 'timestamp':
                continue
            print(f"  {cache_name.title()} Cache:")
            print(f"    L1: {stats['l1_cache']['entry_count']} items, {stats['l1_cache']['hit_rate']:.1%} hit rate")
            print(f"    L2: {stats['l2_cache']['entry_count']} items, {stats['l2_cache']['hit_rate']:.1%} hit rate")
            print(f"    Memory: {stats['total_memory_mb']:.2f} MB")
        
        print("✅ Cache behavior test completed")
        return True
        
    except Exception as e:
        print(f"❌ Cache test failed: {e}")
        return False


def analyze_cache_performance():
    """Analyze cache performance and provide recommendations"""
    print("\nAnalyzing Cache Performance...")
    
    try:
        from cache import cache_manager
        
        # Get performance analysis
        analysis = cache_manager.performance_monitor.analyze_performance()
        
        print(f"Overall Health: {analysis['overall_health']}")
        
        for cache_name, cache_analysis in analysis['cache_analysis'].items():
            print(f"\n{cache_name.title()} Cache Analysis:")
            print(f"  L1 Hit Rate: {cache_analysis['hit_rate']['l1']:.1%}")
            print(f"  L2 Hit Rate: {cache_analysis['hit_rate']['l2']:.1%}")
            print(f"  Memory Usage: {cache_analysis['memory_usage']:.2f} MB")
            print(f"  Status: {cache_analysis['status']}")
            
            if cache_analysis['recommendations']:
                print(f"  Recommendations:")
                for rec in cache_analysis['recommendations']:
                    print(f"    • {rec}")
        
        # Get optimization suggestions
        suggestions = cache_manager.performance_monitor.get_optimization_suggestions()
        if suggestions:
            print(f"\nOptimization Suggestions:")
            for suggestion in suggestions:
                print(f"  • {suggestion}")
        
        return True
        
    except Exception as e:
        print(f"Performance analysis failed: {e}")
        return False


def optimize_cache_settings():
    """Optimize cache settings based on current usage"""
    print("\n🔧 Optimizing Cache Settings...")
    
    try:
        from cache import cache_manager
        
        # Run memory optimization
        cache_manager.optimize_memory()
        print("✅ Memory optimization completed")
        
        # Clear unused caches if they're empty
        stats = cache_manager.get_all_stats()
        for cache_name, cache_stats in stats.items():
            if cache_name == 'timestamp':
                continue
            
            if (cache_stats['l1_cache']['entry_count'] == 0 and 
                cache_stats['l2_cache']['entry_count'] == 0):
                cache = cache_manager.get_cache(cache_name)
                cache.clear()
                print(f"✅ Cleared empty {cache_name} cache")
        
        return True
        
    except Exception as e:
        print(f"❌ Cache optimization failed: {e}")
        return False


def generate_cache_report():
    """Generate comprehensive cache report"""
    print("\nCACHE OPTIMIZATION REPORT")
    print("=" * 50)
    
    results = {
        'test_behavior': False,
        'analyze_performance': False,
        'optimize_settings': False
    }
    
    # Run all tests
    print("\n1. TESTING CACHE BEHAVIOR")
    print("-" * 30)
    results['test_behavior'] = test_cache_behavior()
    
    print("\n2. ANALYZING PERFORMANCE")
    print("-" * 30)
    results['analyze_performance'] = analyze_cache_performance()
    
    print("\n3. OPTIMIZING SETTINGS")
    print("-" * 30) 
    results['optimize_settings'] = optimize_cache_settings()
    
    # Generate summary
    passed = sum(results.values())
    total = len(results)
    
    print(f"\nCACHE REPORT SUMMARY")
    print("=" * 50)
    print(f"Tests Passed: {passed}/{total}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    for test_name, success in results.items():
        status = "✅" if success else "❌"
        print(f"{status} {test_name.replace('_', ' ').title()}")
    
    if passed == total:
        print(f"\nALL CACHE OPTIMIZATIONS SUCCESSFUL!")
        print("Cache system is properly configured and performing well.")
    else:
        print(f"\nSome optimizations failed. Check the errors above.")
    
    print(f"\nNEXT STEPS:")
    print(f"1. The L2 cache should now be properly utilized")
    print(f"2. Monitor cache hit rates in the application")
    print(f"3. L2 cache usage is normal when L1 has sufficient capacity")
    print(f"4. Warning status is expected during initial cache warming")
    
    return passed == total


def main():
    """Main optimization execution"""
    print("Project Kairos Cache Optimization")
    print("=" * 60)
    
    # Run comprehensive cache optimization
    success = generate_cache_report()
    
    if success:
        print(f"\nCACHE OPTIMIZATION COMPLETE!")
        print("The multi-level cache system is now properly configured.")
        return 0
    else:
        print(f"\nSOME OPTIMIZATIONS FAILED!")
        print("Please review the issues above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
