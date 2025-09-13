# Troubleshooting Guide

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
