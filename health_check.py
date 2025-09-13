#!/usr/bin/env python3
"""
System Health Check and Optimization Script for Project Kairos
Addresses memory usage, system alerts, and performance issues
"""

import os
import sys
import gc
import psutil
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def check_memory_usage():
    """Check current memory usage and recommend optimizations"""
    print("Checking memory usage...")
    
    try:
        # Get system memory info
        memory = psutil.virtual_memory()
        
        print(f"Total Memory: {memory.total / (1024**3):.2f} GB")
        print(f"Available Memory: {memory.available / (1024**3):.2f} GB")
        print(f"Used Memory: {memory.used / (1024**3):.2f} GB")
        print(f"Memory Usage: {memory.percent:.1f}%")
        
        # Check if memory usage is critical
        if memory.percent > 90:
            print("🚨 CRITICAL: Memory usage is very high (>90%)")
            return False, "critical"
        elif memory.percent > 80:
            print("⚠️ WARNING: Memory usage is high (>80%)")
            return False, "warning"
        else:
            print("✅ Memory usage is normal")
            return True, "normal"
            
    except Exception as e:
        print(f"❌ Error checking memory: {e}")
        return False, "error"


def optimize_python_memory():
    """Optimize Python memory usage"""
    print("Optimizing Python memory usage...")
    
    try:
        # Force garbage collection
        collected = gc.collect()
        print(f"  Collected {collected} objects")
        
        # Get memory usage before and after
        process = psutil.Process()
        memory_before = process.memory_info().rss / (1024**2)  # MB
        
        # Clear any module-level caches
        if 'cache' in sys.modules:
            try:
                from cache import cache_manager
                cache_manager.optimize_memory()
                print("  Optimized cache memory")
            except:
                pass
        
        # Force another garbage collection
        gc.collect()
        
        memory_after = process.memory_info().rss / (1024**2)  # MB
        memory_saved = memory_before - memory_after
        
        print(f"  Memory before: {memory_before:.1f} MB")
        print(f"  Memory after: {memory_after:.1f} MB")
        print(f"  Memory saved: {memory_saved:.1f} MB")
        
        return True
        
    except Exception as e:
        print(f"❌ Memory optimization failed: {e}")
        return False


def check_database_size():
    """Check database file sizes"""
    print("Checking database sizes...")
    
    try:
        db_files = [
            "kairos.db",
            "kairos.db-wal", 
            "kairos.db-shm"
        ]
        
        total_size = 0
        for db_file in db_files:
            if os.path.exists(db_file):
                size = os.path.getsize(db_file) / (1024**2)  # MB
                print(f"  {db_file}: {size:.2f} MB")
                total_size += size
        
        print(f"  Total database size: {total_size:.2f} MB")
        
        if total_size > 500:  # More than 500MB
            print("⚠️ Database is large, consider cleanup")
            return False
        else:
            print("✅ Database size is reasonable")
            return True
            
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        return False


def optimize_database():
    """Optimize database if possible"""
    print("Optimizing database...")
    
    try:
        # Try to import and use database manager
        from database import db_manager
        
        # Get connection and run optimization
        with db_manager.pool.get_connection() as conn:
            cursor = conn.cursor()
            
            # Run VACUUM to reclaim space
            cursor.execute("VACUUM")
            print("  Ran VACUUM operation")
            
            # Update statistics
            cursor.execute("ANALYZE")
            print("  Updated table statistics")
            
            conn.commit()
        
        print("✅ Database optimization completed")
        return True
        
    except Exception as e:
        print(f"⚠️ Database optimization failed: {e}")
        return False


def check_disk_space():
    """Check available disk space"""
    print("Checking disk space...")
    
    try:
        # Get current directory disk usage
        current_path = Path.cwd()
        disk_usage = psutil.disk_usage(current_path)
        
        total_gb = disk_usage.total / (1024**3)
        free_gb = disk_usage.free / (1024**3)
        used_gb = disk_usage.used / (1024**3)
        usage_percent = (disk_usage.used / disk_usage.total) * 100
        
        print(f"  Total Disk: {total_gb:.1f} GB")
        print(f"  Free Disk: {free_gb:.1f} GB") 
        print(f"  Used Disk: {used_gb:.1f} GB")
        print(f"  Usage: {usage_percent:.1f}%")
        
        if usage_percent > 90:
            print("🚨 CRITICAL: Disk space is very low")
            return False
        elif usage_percent > 80:
            print("⚠️ WARNING: Disk space is getting low")
            return False
        else:
            print("✅ Disk space is adequate")
            return True
            
    except Exception as e:
        print(f"❌ Error checking disk space: {e}")
        return False


def cleanup_temp_files():
    """Clean up temporary files"""
    print("Cleaning up temporary files...")
    
    try:
        cleaned_count = 0
        cleaned_size = 0
        
        # Clean up Python cache files
        for root, dirs, files in os.walk("."):
            for file in files:
                if file.endswith('.pyc') or file.endswith('.pyo'):
                    file_path = Path(root) / file
                    try:
                        size = file_path.stat().st_size
                        file_path.unlink()
                        cleaned_count += 1
                        cleaned_size += size
                    except:
                        pass
            
            # Remove __pycache__ directories
            if '__pycache__' in dirs:
                pycache_path = Path(root) / '__pycache__'
                try:
                    import shutil
                    shutil.rmtree(pycache_path)
                    cleaned_count += 1
                except:
                    pass
        
        print(f"  Cleaned {cleaned_count} files ({cleaned_size / 1024:.1f} KB)")
        return True
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        return False


def check_running_processes():
    """Check for other Python/Streamlit processes"""
    print("Checking running processes...")
    
    try:
        streamlit_processes = []
        python_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_percent']):
            try:
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'streamlit' in cmdline.lower():
                        streamlit_processes.append(proc)
                    elif proc.pid != os.getpid():  # Exclude current process
                        python_processes.append(proc)
            except:
                continue
        
        print(f"  Found {len(streamlit_processes)} Streamlit processes")
        print(f"  Found {len(python_processes)} other Python processes")
        
        # Show top memory consumers
        all_processes = streamlit_processes + python_processes
        if all_processes:
            print("  Top memory consumers:")
            for proc in sorted(all_processes, key=lambda p: p.info['memory_percent'], reverse=True)[:3]:
                print(f"    PID {proc.info['pid']}: {proc.info['memory_percent']:.1f}% memory")
        
        return len(all_processes) < 10  # Warning if too many processes
        
    except Exception as e:
        print(f"❌ Process check failed: {e}")
        return True


def generate_health_report():
    """Generate comprehensive health report"""
    print("SYSTEM HEALTH CHECK")
    print("=" * 50)
    
    checks = [
        ("Memory Usage", check_memory_usage),
        ("Database Size", check_database_size), 
        ("Disk Space", check_disk_space),
        ("Running Processes", check_running_processes),
    ]
    
    optimizations = [
        ("Python Memory", optimize_python_memory),
        ("Database", optimize_database),
        ("Temp Files", cleanup_temp_files),
    ]
    
    # Run health checks
    health_results = {}
    print("\nHEALTH CHECKS:")
    print("-" * 30)
    
    for check_name, check_func in checks:
        try:
            result = check_func()
            if isinstance(result, tuple):
                success, level = result
                health_results[check_name] = {'success': success, 'level': level}
            else:
                health_results[check_name] = {'success': result, 'level': 'normal' if result else 'warning'}
        except Exception as e:
            health_results[check_name] = {'success': False, 'level': 'error', 'error': str(e)}
        print()
    
    # Run optimizations if needed
    print("OPTIMIZATIONS:")
    print("-" * 30)
    
    optimization_results = {}
    for opt_name, opt_func in optimizations:
        try:
            result = opt_func()
            optimization_results[opt_name] = {'success': result}
        except Exception as e:
            optimization_results[opt_name] = {'success': False, 'error': str(e)}
        print()
    
    # Generate summary
    print("HEALTH SUMMARY:")
    print("-" * 30)
    
    critical_issues = sum(1 for r in health_results.values() if r.get('level') == 'critical')
    warnings = sum(1 for r in health_results.values() if r.get('level') == 'warning')
    healthy = sum(1 for r in health_results.values() if r.get('level') == 'normal')
    
    print(f"🔴 Critical Issues: {critical_issues}")
    print(f"🟡 Warnings: {warnings}")
    print(f"🟢 Healthy: {healthy}")
    
    successful_opts = sum(1 for r in optimization_results.values() if r['success'])
    print(f"Successful Optimizations: {successful_opts}/{len(optimizations)}")
    
    # Recommendations
    print("\nRECOMMENDATIONS:")
    print("-" * 30)
    
    if critical_issues > 0:
        print("• Critical issues detected - immediate action required")
        print("• Consider restarting the system")
        print("• Check system resources and close unnecessary applications")
    
    if warnings > 0:
        print("• Monitor system resources closely")
        print("• Consider reducing cache sizes or data retention")
        print("• Set auto-refresh intervals to 60+ seconds")
    
    if critical_issues == 0 and warnings == 0:
        print("• System is healthy and ready for operation")
        print("• Continue with normal monitoring")
    
    print(f"• Run 'python health_check.py' periodically to monitor health")
    
    return critical_issues == 0


def main():
    """Main health check execution"""
    print("Project Kairos Health Check & Optimization")
    print("=" * 60)
    
    # Run comprehensive health check
    healthy = generate_health_report()
    
    if healthy:
        print(f"\nSYSTEM IS HEALTHY!")
        print("Ready to run Project Kairos.")
        return 0
    else:
        print(f"\nISSUES DETECTED!")
        print("Please address the issues above before running the application.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
