"""
Configuration Management
Handles environment variables, API configurations, and deployment settings.
"""

import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    path: str = "kairos_production.db"
    connection_timeout: int = 30
    max_connections: int = 10
    backup_interval_hours: int = 6
    enable_wal_mode: bool = True


@dataclass
class CacheConfig:
    """Caching configuration settings"""
    weather_ttl: int = 300  # 5 minutes
    alerts_ttl: int = 600   # 10 minutes
    disasters_ttl: int = 1800  # 30 minutes
    max_size_weather: int = 500
    max_size_alerts: int = 100
    max_size_disasters: int = 200


@dataclass
class APIConfig:
    """API configuration and rate limiting"""
    timeout_seconds: int = 15
    max_retries: int = 3
    retry_delay: int = 2
    rate_limit_calls: int = 100
    rate_limit_period: int = 3600  # 1 hour
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_timeout: int = 60


@dataclass
class SecurityConfig:
    """Security configuration settings"""
    enable_auth: bool = False
    session_timeout: int = 3600
    max_login_attempts: int = 5
    enable_rate_limiting: bool = True
    allowed_origins: list = None
    
    def __post_init__(self):
        if self.allowed_origins is None:
            self.allowed_origins = ["*"]


@dataclass
class MonitoringConfig:
    """Monitoring and logging configuration"""
    log_level: str = "INFO"
    log_file: str = "kairos_production.log"
    max_log_size_mb: int = 100
    backup_count: int = 5
    enable_metrics: bool = True
    health_check_interval: int = 60
    alert_webhook_url: Optional[str] = None


class Config:
    """Main configuration class"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or "kairos_config.json"
        self.database = DatabaseConfig()
        self.cache = CacheConfig()
        self.api = APIConfig()
        self.security = SecurityConfig()
        self.monitoring = MonitoringConfig()
        
        # Load configuration from file or environment
        self._load_config()
        
    def _load_config(self):
        """Load configuration from file and environment variables"""
        # Load from JSON file if it exists
        config_path = Path(self.config_file)
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    file_config = json.load(f)
                self._update_from_dict(file_config)
            except Exception as e:
                print(f"Warning: Could not load config file {self.config_file}: {e}")
        
        # Override with environment variables
        self._load_from_environment()
    
    def _update_from_dict(self, config_dict: Dict[str, Any]):
        """Update configuration from dictionary"""
        for section, values in config_dict.items():
            if hasattr(self, section) and isinstance(values, dict):
                section_obj = getattr(self, section)
                for key, value in values.items():
                    if hasattr(section_obj, key):
                        setattr(section_obj, key, value)
    
    def _load_from_environment(self):
        """Load configuration from environment variables"""
        env_mappings = {
            # Database
            'KAIROS_DB_PATH': ('database', 'path'),
            'KAIROS_DB_TIMEOUT': ('database', 'connection_timeout', int),
            'KAIROS_DB_MAX_CONN': ('database', 'max_connections', int),
            
            # Cache
            'KAIROS_CACHE_WEATHER_TTL': ('cache', 'weather_ttl', int),
            'KAIROS_CACHE_ALERTS_TTL': ('cache', 'alerts_ttl', int),
            'KAIROS_CACHE_DISASTERS_TTL': ('cache', 'disasters_ttl', int),
            
            # API
            'KAIROS_API_TIMEOUT': ('api', 'timeout_seconds', int),
            'KAIROS_API_MAX_RETRIES': ('api', 'max_retries', int),
            'KAIROS_API_RATE_LIMIT': ('api', 'rate_limit_calls', int),
            
            # Security
            'KAIROS_ENABLE_AUTH': ('security', 'enable_auth', self._str_to_bool),
            'KAIROS_SESSION_TIMEOUT': ('security', 'session_timeout', int),
            'KAIROS_ALLOWED_ORIGINS': ('security', 'allowed_origins', self._str_to_list),
            
            # Monitoring
            'KAIROS_LOG_LEVEL': ('monitoring', 'log_level'),
            'KAIROS_LOG_FILE': ('monitoring', 'log_file'),
            'KAIROS_ALERT_WEBHOOK': ('monitoring', 'alert_webhook_url'),
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                section = config_path[0]
                key = config_path[1]
                transform = config_path[2] if len(config_path) > 2 else str
                
                try:
                    transformed_value = transform(value)
                    setattr(getattr(self, section), key, transformed_value)
                except Exception as e:
                    print(f"Warning: Invalid value for {env_var}: {e}")
    
    @staticmethod
    def _str_to_bool(value: str) -> bool:
        """Convert string to boolean"""
        return value.lower() in ('true', '1', 'yes', 'on')
    
    @staticmethod
    def _str_to_list(value: str) -> list:
        """Convert comma-separated string to list"""
        return [item.strip() for item in value.split(',') if item.strip()]
    
    def save_config(self):
        """Save current configuration to file"""
        config_dict = {
            'database': {
                'path': self.database.path,
                'connection_timeout': self.database.connection_timeout,
                'max_connections': self.database.max_connections,
                'backup_interval_hours': self.database.backup_interval_hours,
                'enable_wal_mode': self.database.enable_wal_mode,
            },
            'cache': {
                'weather_ttl': self.cache.weather_ttl,
                'alerts_ttl': self.cache.alerts_ttl,
                'disasters_ttl': self.cache.disasters_ttl,
                'max_size_weather': self.cache.max_size_weather,
                'max_size_alerts': self.cache.max_size_alerts,
                'max_size_disasters': self.cache.max_size_disasters,
            },
            'api': {
                'timeout_seconds': self.api.timeout_seconds,
                'max_retries': self.api.max_retries,
                'retry_delay': self.api.retry_delay,
                'rate_limit_calls': self.api.rate_limit_calls,
                'rate_limit_period': self.api.rate_limit_period,
            },
            'security': {
                'enable_auth': self.security.enable_auth,
                'session_timeout': self.security.session_timeout,
                'max_login_attempts': self.security.max_login_attempts,
                'enable_rate_limiting': self.security.enable_rate_limiting,
                'allowed_origins': self.security.allowed_origins,
            },
            'monitoring': {
                'log_level': self.monitoring.log_level,
                'log_file': self.monitoring.log_file,
                'max_log_size_mb': self.monitoring.max_log_size_mb,
                'backup_count': self.monitoring.backup_count,
                'enable_metrics': self.monitoring.enable_metrics,
            }
        }
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config_dict, f, indent=2)
        except Exception as e:
            print(f"Error saving config file: {e}")
    
    def get_environment(self) -> str:
        """Get current environment"""
        return os.getenv('KAIROS_ENV', 'production')
    
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.get_environment().lower() in ('dev', 'development', 'local')
    
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.get_environment().lower() in ('prod', 'production')


# Global configuration instance
config = Config()
