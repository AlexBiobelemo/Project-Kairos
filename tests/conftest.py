"""
Test configuration for pytest
"""

import os
import sys
import tempfile
import pytest
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from database import DatabaseManager
from cache import CacheManager


@pytest.fixture
def temp_config():
    """Create temporary configuration for testing"""
    config = Config()
    
    # Use temporary database
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    config.database.path = temp_db.name
    
    yield config
    
    # Cleanup
    if os.path.exists(temp_db.name):
        os.unlink(temp_db.name)


@pytest.fixture
def temp_database(temp_config):
    """Create temporary database for testing"""
    db_manager = DatabaseManager(temp_config)
    db_manager.initialize_schema()
    
    yield db_manager
    
    db_manager.close()


@pytest.fixture
def cache_manager(temp_config):
    """Create cache manager for testing"""
    return CacheManager(temp_config)


@pytest.fixture
def mock_environment():
    """Mock environment variables for testing"""
    env_vars = {
        'KAIROS_APP_DEBUG': 'true',
        'KAIROS_APP_NAME': 'Test Kairos',
        'KAIROS_DATABASE_POOL_SIZE': '10',
        'KAIROS_CACHE_MAX_SIZE': '1000'
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture(scope="session")
def test_data_dir():
    """Create test data directory"""
    test_dir = tempfile.mkdtemp(prefix='kairos_test_')
    yield test_dir
    
    # Cleanup is handled by OS for temp directories
    import shutil
    try:
        shutil.rmtree(test_dir)
    except OSError:
        pass  # Directory might have been cleaned up already
