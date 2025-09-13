#!/usr/bin/env python3
"""
Quick Fix Script for Critical Project Kairos Issues
Applies code fixes without requiring full dependency stack
"""

import os
import sys
import json
from pathlib import Path

def fix_experimental_rerun():
    """Fix experimental_rerun calls in app_production.py"""
    print("Fixing experimental_rerun calls...")
    
    app_file = Path("app_production.py")
    if not app_file.exists():
        print("app_production.py not found")
        return False
    
    try:
        content = app_file.read_text()
        
        # Replace experimental_rerun with st.rerun for newer Streamlit versions
        fixed_content = content.replace("st.experimental_rerun()", "st.rerun()")
        
        if fixed_content != content:
            app_file.write_text(fixed_content)
            print("Fixed experimental_rerun calls")
            return True
        else:
            print("No experimental_rerun calls to fix")
            return True
            
    except Exception as e:
        print(f"Failed to fix experimental_rerun: {e}")
        return False


def create_requirements_txt():
    """Create comprehensive requirements.txt"""
    print("Creating comprehensive requirements.txt...")
    
    requirements = [
        "streamlit>=1.28.0",
        "pandas>=1.5.0",
        "numpy>=1.21.0",
        "plotly>=5.0.0",
        "folium>=0.14.0",
        "streamlit-folium>=0.13.0",
        "requests>=2.28.0",
        "psutil>=5.9.0",
        "pydeck>=0.8.0",
        "python-dotenv>=1.0.0",
        "cryptography>=40.0.0",
        "bcrypt>=4.0.0",
        "pytest>=7.0.0",
        "flake8>=6.0.0",
        "black>=23.0.0",
    ]
    
    try:
        with open("requirements.txt", "w") as f:
            f.write("\n".join(requirements))
        
        print("Created requirements.txt")
        print("Run: pip install -r requirements.txt")
        return True
        
    except Exception as e:
        print(f"Failed to create requirements.txt: {e}")
        return False


def create_app_config():
    """Create app configuration for better stability"""
    print("Creating app configuration...")
    
    streamlit_config = """[global]
developmentMode = false
logLevel = "info"

[server]
port = 8501
address = "localhost"
baseUrlPath = ""
enableCORS = false
enableXsrfProtection = true
maxUploadSize = 200

[browser]
gatherUsageStats = false
showErrorDetails = false

[theme]
primaryColor = "#1f4e79"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"
"""
    
    try:
        # Create .streamlit directory
        streamlit_dir = Path(".streamlit")
        streamlit_dir.mkdir(exist_ok=True)
        
        # Create config.toml
        config_file = streamlit_dir / "config.toml"
        config_file.write_text(streamlit_config)
        
        print("✅ Created Streamlit configuration")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create app config: {e}")
        return False


def create_env_template():
    """Create environment template"""
    print("Creating environment template...")
    
    env_template = """# Project Kairos Environment Configuration

# Database Configuration
KAIROS_DATABASE_PATH=kairos.db
KAIROS_DATABASE_POOL_SIZE=10
KAIROS_DATABASE_TIMEOUT=30

# Cache Configuration
KAIROS_CACHE_MAX_SIZE=1000
KAIROS_CACHE_TTL=300
KAIROS_CACHE_ENABLE_COMPRESSION=true

# API Configuration
KAIROS_API_TIMEOUT_SECONDS=10
KAIROS_API_MAX_RETRIES=3

# Monitoring Configuration
KAIROS_MONITORING_ENABLE_METRICS=true
KAIROS_MONITORING_LOG_LEVEL=INFO
KAIROS_MONITORING_HEALTH_CHECK_INTERVAL=60

# Security Configuration  
SESSION_TIMEOUT=3600
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION=900
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
PASSWORD_MIN_LENGTH=8
SECRET_KEY=your-secret-key-here

# Alert Configuration
ALERT_WEBHOOK_URL=
ADMIN_USERS=admin
"""
    
    try:
        env_file = Path(".env.example")
        env_file.write_text(env_template)
        
        print("Created .env.example template")
        print("Copy to .env and update values as needed")
        return True
        
    except Exception as e:
        print(f"Failed to create env template: {e}")
        return False


def create_startup_script():
    """Create startup script for easier launching"""
    print("Creating startup script...")
    
    startup_script = """#!/usr/bin/env python3
\"\"\"
Project Kairos Startup Script
Handles initialization and launches the application
\"\"\"

import os
import sys
import subprocess
import time
from pathlib import Path

def check_requirements():
    \"\"\"Check if requirements are installed\"\"\"
    try:
        import streamlit
        import pandas  
        import plotly
        import folium
        import requests
        import psutil
        print("All requirements are installed")
        return True
    except ImportError as e:
        print(f"Missing requirement: {e}")
        print("Run: pip install -r requirements.txt")
        return False

def setup_environment():
    \"\"\"Setup environment variables\"\"\"
    env_file = Path(".env")
    if env_file.exists():
        print("Loading environment from .env")
        from dotenv import load_dotenv
        load_dotenv()
    else:
        print("No .env file found, using defaults")
    
    # Set default values if not provided
    os.environ.setdefault("KAIROS_APP_DEBUG", "false")
    os.environ.setdefault("KAIROS_DATABASE_PATH", "kairos.db")
    os.environ.setdefault("KAIROS_CACHE_MAX_SIZE", "1000")

def run_health_check():
    \"\"\"Run quick health check\"\"\"
    print("Running health check...")
    
    try:
        # Check if we can import our modules
        sys.path.insert(0, str(Path(__file__).parent))
        
        import config
        print("Config module OK")
        
        import cache
        print("Cache module OK")
        
        return True
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def main():
    \"\"\"Main startup function\"\"\"
    print("Starting Project Kairos...")
    print("="*50)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Setup environment
    setup_environment()
    
    # Run health check
    if not run_health_check():
        print("Health check failed, but continuing...")
    
    # Launch Streamlit app
    print("Launching application...")
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "app_production.py",
            "--server.address", "localhost",
            "--server.port", "8501",
            "--browser.gatherUsageStats", "false"
        ])
    except KeyboardInterrupt:
        print("\\nShutting down Project Kairos...")
    except Exception as e:
        print(f"Failed to start application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
"""
    
    try:
        startup_file = Path("start_kairos.py")
        startup_file.write_text(startup_script)
        
        print("Created startup script: start_kairos.py")
        print("Run: python start_kairos.py")
        return True
        
    except Exception as e:
        print(f"Failed to create startup script: {e}")
        return False


def create_troubleshooting_guide():
    """Create troubleshooting guide"""
    print("Creating troubleshooting guide...")
    
    guide = """# Project Kairos Troubleshooting Guide

## Common Issues and Solutions

### 1. Database Lock Errors
**Error:** `database is locked`
**Solution:**
- Stop the application
- Delete `kairos.db-wal` and `kairos.db-shm` files if they exist
- Restart the application
- Enable WAL mode: the app now automatically optimizes database settings

### 2. Disaster Processing Errors  
**Error:** `'<=' not supported between instances of 'int' and 'list'`
**Solution:**
- Fixed in the latest version with robust coordinate parsing
- Handles different GeoJSON coordinate formats
- Validates data types before comparison

### 3. Cache Performance Issues
**Error:** `'CacheManager' object has no attribute 'performance_monitor'`
**Solution:**
- Fixed: performance_monitor is now properly initialized in CacheManager
- Access via: cache_manager.performance_monitor.analyze_performance()

### 4. App Stability Issues
**Problem:** App crashes or becomes unresponsive with auto-refresh
**Solution:**
- Use the new refresh controls in the sidebar
- Set refresh interval to 60+ seconds  
- Disable auto-refresh if experiencing issues
- The app now uses more stable refresh mechanisms

### 5. Missing Dependencies
**Error:** `No module named 'pandas'` or similar
**Solution:**
```bash
pip install -r requirements.txt
```

### 6. Port Already in Use
**Error:** `Port 8501 is already in use`
**Solution:**
```bash
# Kill existing Streamlit processes
pkill -f streamlit

# Or use a different port
streamlit run app_production.py --server.port 8502
```

### 7. Memory Issues
**Problem:** High memory usage or out of memory errors
**Solution:**
- Run: python fix_issues.py (for cache optimization)
- Reduce cache sizes in config.py
- Increase refresh intervals to reduce API calls

## Performance Optimization Tips

1. **Database Performance:**
   - WAL mode is automatically enabled
   - Regular VACUUM operations are performed
   - Connection pooling optimizes concurrent access

2. **Cache Performance:**
   - Multi-level caching (L1/L2) is implemented
   - LRU eviction prevents memory bloat
   - Compression is available for large data

3. **Network Performance:**
   - Circuit breakers prevent cascade failures
   - Retry logic with exponential backoff
   - Graceful degradation with fallback data

## Monitoring and Health

Check system health:
```bash
python run_tests.py --smoke
python fix_issues.py
```

View logs in real-time:
```bash
tail -f kairos.log
```

## Getting Help

1. Check the logs for detailed error messages
2. Run the smoke tests to identify specific issues  
3. Use the troubleshooting commands above
4. Check the GitHub issues for known problems

## Emergency Recovery

If the system becomes completely unstable:

1. Stop the application
2. Delete the database: `rm kairos.db*`
3. Clear cache: `rm -rf __pycache__`
4. Restart: `python start_kairos.py`

This will reset to a clean state with fallback data.
"""
    
    try:
        guide_file = Path("TROUBLESHOOTING.md")
        guide_file.write_text(guide)
        
        print("Created troubleshooting guide: TROUBLESHOOTING.md")
        return True
        
    except Exception as e:
        print(f"Failed to create troubleshooting guide: {e}")
        return False


def main():
    """Main fix execution"""
    print("Project Kairos Quick Fix Script")
    print("="*50)
    
    fixes = [
        ("Fix experimental_rerun calls", fix_experimental_rerun),
        ("Create requirements.txt", create_requirements_txt),
        ("Create app configuration", create_app_config),
        ("Create environment template", create_env_template),
        ("Create startup script", create_startup_script),
        ("Create troubleshooting guide", create_troubleshooting_guide),
    ]
    
    results = []
    for fix_name, fix_func in fixes:
        print(f"\n{'-'*30}")
        result = fix_func()
        results.append((fix_name, result))
    
    # Summary
    print(f"\n{'='*50}")
    print("QUICK FIX SUMMARY")
    print(f"{'='*50}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"Fixes Applied: {passed}/{total}")
    
    for fix_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {fix_name}")
    
    if passed == total:
        print(f"\n🎉 ALL FIXES APPLIED SUCCESSFULLY!")
        print(f"\nNext steps:")
        print(f"1. Install dependencies: pip install -r requirements.txt")
        print(f"2. Start the app: python start_kairos.py")
        print(f"3. Check TROUBLESHOOTING.md for any issues")
    else:
        print(f"\nSome fixes failed. Check the errors above.")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
