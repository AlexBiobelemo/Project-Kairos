#!/bin/bash

# Project Kairos Docker Entrypoint Script
# Handles initialization, database setup, and graceful startup

set -e

echo "Starting Project Kairos"
echo "================================================"

# Environment information
echo "Environment: ${KAIROS_ENV:-production}"
echo "Python version: $(python --version)"
echo "Working directory: $(pwd)"
echo "User: $(whoami)"

# Create necessary directories
echo "Creating required directories..."
mkdir -p /app/data /app/logs /app/backups

# Initialize database if it doesn't exist
if [ ! -f "/app/data/kairos_production.db" ]; then
    echo "Initializing database..."
    python -c "
from database import db_manager
print('Database initialized successfully')
"
fi

# Run database health check
echo "Running database health check..."
python -c "
from database import db_manager
stats = db_manager.get_database_stats()
print(f'Database size: {stats.get(\"database_size_mb\", 0)} MB')
print('Database health check passed')
"

# Clear any stale cache on startup
echo "Clearing stale cache..."
python -c "
from cache import cache_manager
cache_manager.optimize_memory()
print('Cache optimization completed')
"

# Set up signal handlers for graceful shutdown
cleanup() {
    echo "Received shutdown signal, cleaning up..."
    python -c "
from database import db_manager
from cache import cache_manager
try:
    db_manager.close()
    cache_manager.clear_all()
    print('Cleanup completed')
except Exception as e:
    print(f'Cleanup warning: {e}')
"
    exit 0
}

trap cleanup SIGTERM SIGINT

echo "Starting application..."
echo "Access the application at: http://localhost:8501"
echo "================================================"

# Execute the main command
exec "$@"
