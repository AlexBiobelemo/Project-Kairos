"""
Monitoring and Health Check System
Provides application monitoring, metrics collection, and alerting capabilities.
"""

import time
import json
import logging
import threading
import platform
try:
    import psutil
except ImportError:
    psutil = None

from typing import Any, Dict, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
try:
    import requests
except ImportError:
    requests = None

from collections import deque

from config import config
from database import db_manager
from cache import cache_manager, performance_monitor
from resilience import resilience_manager


class HealthStatus(Enum):
    """Health check status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Health check result"""
    name: str
    status: HealthStatus
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    response_time_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Metric:
    """System metric data point"""
    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Collects system and application metrics"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.MetricsCollector")
        self._metrics_buffer = deque(maxlen=10000)  # Keep last 10k metrics
        self._lock = threading.RLock()
        
        # Start metrics collection thread
        self._collection_thread = threading.Thread(target=self._collect_metrics_loop, daemon=True)
        self._collection_thread.start()
    
    def _collect_metrics_loop(self):
        """Background thread for metrics collection"""
        while True:
            try:
                self._collect_system_metrics()
                self._collect_application_metrics()
                time.sleep(30)  # Collect every 30 seconds
            except Exception as e:
                self.logger.error(f"Metrics collection error: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _collect_system_metrics(self):
        """Collect system-level metrics"""
        if psutil is None:
            self.logger.debug("System metrics collection skipped (psutil not available)")
            return
        
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            self.record_metric("system.cpu.usage_percent", cpu_percent, "percent")
            
            # Memory metrics
            memory = psutil.virtual_memory()
            self.record_metric("system.memory.usage_percent", memory.percent, "percent")
            self.record_metric("system.memory.used_bytes", memory.used, "bytes")
            self.record_metric("system.memory.available_bytes", memory.available, "bytes")
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            self.record_metric("system.disk.usage_percent", 
                             (disk.used / disk.total) * 100, "percent")
            self.record_metric("system.disk.free_bytes", disk.free, "bytes")
            
            # Network metrics (if available)
            try:
                net_io = psutil.net_io_counters()
                self.record_metric("system.network.bytes_sent", net_io.bytes_sent, "bytes")
                self.record_metric("system.network.bytes_recv", net_io.bytes_recv, "bytes")
            except:
                pass  # Network metrics not available on all systems
            
        except Exception as e:
            self.logger.error(f"System metrics collection failed: {e}")
    
    def _collect_application_metrics(self):
        """Collect application-specific metrics"""
        try:
            # Database metrics
            db_stats = db_manager.get_database_stats()
            for key, value in db_stats.items():
                if isinstance(value, (int, float)):
                    self.record_metric(f"app.database.{key}", float(value), "count")
            
            # Cache metrics
            cache_stats = cache_manager.get_all_stats()
            for cache_type, stats in cache_stats.items():
                if cache_type == 'timestamp':
                    continue
                
                # L1 cache metrics
                l1_stats = stats.get('l1_cache', {})
                for metric, value in l1_stats.items():
                    if isinstance(value, (int, float)):
                        self.record_metric(
                            f"app.cache.{cache_type}.l1.{metric}", 
                            float(value), 
                            "count"
                        )
                
                # L2 cache metrics
                l2_stats = stats.get('l2_cache', {})
                for metric, value in l2_stats.items():
                    if isinstance(value, (int, float)):
                        self.record_metric(
                            f"app.cache.{cache_type}.l2.{metric}", 
                            float(value), 
                            "count"
                        )
            
            # Resilience metrics
            resilience_health = resilience_manager.get_system_health()
            self.record_metric(
                "app.resilience.total_services", 
                float(resilience_health.get('total_services', 0)), 
                "count"
            )
            
            error_stats = resilience_health.get('error_stats', {})
            self.record_metric(
                "app.resilience.total_errors", 
                float(error_stats.get('total_errors', 0)), 
                "count"
            )
            
        except Exception as e:
            self.logger.error(f"Application metrics collection failed: {e}")
    
    def record_metric(self, name: str, value: float, unit: str, tags: Optional[Dict[str, str]] = None):
        """Record a custom metric"""
        metric = Metric(
            name=name,
            value=value,
            unit=unit,
            tags=tags or {}
        )
        
        with self._lock:
            self._metrics_buffer.append(metric)
        
        # Store in database if enabled
        if config.monitoring.enable_metrics:
            try:
                # Use proper connection context manager with retry logic
                max_retries = 3
                retry_delay = 0.1
                
                for attempt in range(max_retries):
                    try:
                        with db_manager.pool.get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO system_metrics (timestamp, metric_name, metric_value, metric_unit, tags) VALUES (?, ?, ?, ?, ?)",
                                (metric.timestamp.isoformat(), name, value, unit, json.dumps(tags or {}))
                            )
                            conn.commit()
                            break  # Success, exit retry loop
                    except Exception as e:
                        if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                            time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                            continue
                        else:
                            raise e
            except Exception as e:
                self.logger.warning(f"Failed to store metric in database: {e}")
    
    def get_recent_metrics(self, minutes: int = 10) -> List[Metric]:
        """Get metrics from the last N minutes"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        with self._lock:
            return [m for m in self._metrics_buffer if m.timestamp > cutoff_time]
    
    def get_metric_summary(self, metric_name: str, minutes: int = 60) -> Dict[str, float]:
        """Get summary statistics for a metric"""
        recent_metrics = [
            m for m in self.get_recent_metrics(minutes)
            if m.name == metric_name
        ]
        
        if not recent_metrics:
            return {}
        
        values = [m.value for m in recent_metrics]
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'latest': values[-1] if values else 0
        }


class HealthChecker:
    """Performs health checks on system components"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.HealthChecker")
        self._checks = {}
        self._last_results = {}
        
        # Register default health checks
        self._register_default_checks()
    
    def _register_default_checks(self):
        """Register default health checks"""
        self.register_check("database", self._check_database, critical=True)
        self.register_check("cache", self._check_cache, critical=False)
        self.register_check("disk_space", self._check_disk_space, critical=True)
        self.register_check("memory", self._check_memory, critical=False)
        self.register_check("resilience", self._check_resilience, critical=False)
    
    def register_check(self, name: str, check_func: Callable, critical: bool = False):
        """Register a new health check"""
        self._checks[name] = {
            'func': check_func,
            'critical': critical
        }
    
    def _check_database(self) -> HealthCheck:
        """Check database health"""
        start_time = time.time()
        
        try:
            # Test database connection and basic query
            with db_manager.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            # Get database stats
            stats = db_manager.get_database_stats()
            
            response_time = (time.time() - start_time) * 1000
            
            # Check connection pool health
            pool_stats = stats.get('connection_pool', {})
            active_connections = pool_stats.get('active_connections', 0)
            max_connections = pool_stats.get('max_connections', 10)
            
            if active_connections > max_connections * 0.8:
                return HealthCheck(
                    name="database",
                    status=HealthStatus.WARNING,
                    message=f"High connection usage: {active_connections}/{max_connections}",
                    response_time_ms=response_time,
                    details=stats
                )
            
            return HealthCheck(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Database is healthy",
                response_time_ms=response_time,
                details=stats
            )
            
        except Exception as e:
            return HealthCheck(
                name="database",
                status=HealthStatus.CRITICAL,
                message=f"Database error: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000
            )
    
    def _check_cache(self) -> HealthCheck:
        """Check cache health"""
        start_time = time.time()
        
        try:
            # Test cache operations
            test_key = "health_check_test"
            test_value = {"timestamp": datetime.now().isoformat()}
            
            # Test set and get
            cache_manager.general_cache.set(test_key, test_value, l1_ttl=60)
            retrieved = cache_manager.general_cache.get(test_key)
            
            if retrieved != test_value:
                raise Exception("Cache set/get test failed")
            
            # Clean up test data
            cache_manager.general_cache.delete(test_key)
            
            # Get cache performance analysis
            performance = performance_monitor.analyze_performance()
            
            response_time = (time.time() - start_time) * 1000
            
            if performance['overall_health'] != 'good':
                return HealthCheck(
                    name="cache",
                    status=HealthStatus.WARNING,
                    message=f"Cache performance issues detected",
                    response_time_ms=response_time,
                    details=performance
                )
            
            return HealthCheck(
                name="cache",
                status=HealthStatus.HEALTHY,
                message="Cache is healthy",
                response_time_ms=response_time,
                details=performance
            )
            
        except Exception as e:
            return HealthCheck(
                name="cache",
                status=HealthStatus.CRITICAL,
                message=f"Cache error: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000
            )
    
    def _check_disk_space(self) -> HealthCheck:
        """Check disk space"""
        if psutil is None:
            return HealthCheck(
                name="disk_space",
                status=HealthStatus.UNKNOWN,
                message="Disk space check unavailable (psutil not installed)"
            )
        
        try:
            disk = psutil.disk_usage('/')
            usage_percent = (disk.used / disk.total) * 100
            
            details = {
                'total_bytes': disk.total,
                'used_bytes': disk.used,
                'free_bytes': disk.free,
                'usage_percent': usage_percent
            }
            
            if usage_percent > 90:
                return HealthCheck(
                    name="disk_space",
                    status=HealthStatus.CRITICAL,
                    message=f"Disk space critically low: {usage_percent:.1f}% used",
                    details=details
                )
            elif usage_percent > 80:
                return HealthCheck(
                    name="disk_space",
                    status=HealthStatus.WARNING,
                    message=f"Disk space getting low: {usage_percent:.1f}% used",
                    details=details
                )
            
            return HealthCheck(
                name="disk_space",
                status=HealthStatus.HEALTHY,
                message=f"Disk space OK: {usage_percent:.1f}% used",
                details=details
            )
            
        except Exception as e:
            return HealthCheck(
                name="disk_space",
                status=HealthStatus.UNKNOWN,
                message=f"Could not check disk space: {str(e)}"
            )
    
    def _check_memory(self) -> HealthCheck:
        """Check memory usage"""
        if psutil is None:
            return HealthCheck(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message="Memory check unavailable (psutil not installed)"
            )
        
        try:
            memory = psutil.virtual_memory()
            
            details = {
                'total_bytes': memory.total,
                'available_bytes': memory.available,
                'used_bytes': memory.used,
                'usage_percent': memory.percent
            }
            
            if memory.percent > 90:
                return HealthCheck(
                    name="memory",
                    status=HealthStatus.CRITICAL,
                    message=f"Memory usage critically high: {memory.percent:.1f}%",
                    details=details
                )
            elif memory.percent > 80:
                return HealthCheck(
                    name="memory",
                    status=HealthStatus.WARNING,
                    message=f"Memory usage high: {memory.percent:.1f}%",
                    details=details
                )
            
            return HealthCheck(
                name="memory",
                status=HealthStatus.HEALTHY,
                message=f"Memory usage OK: {memory.percent:.1f}%",
                details=details
            )
            
        except Exception as e:
            return HealthCheck(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message=f"Could not check memory: {str(e)}"
            )
    
    def _check_resilience(self) -> HealthCheck:
        """Check resilience system health"""
        try:
            health = resilience_manager.get_system_health()
            
            # Count services in different states
            circuit_breakers = health.get('circuit_breakers', {})
            open_breakers = sum(1 for cb in circuit_breakers.values() if cb['state'] == 'open')
            total_breakers = len(circuit_breakers)
            
            # Check error rates
            error_stats = health.get('error_stats', {})
            total_errors = error_stats.get('total_errors', 0)
            
            details = {
                'total_services': health.get('total_services', 0),
                'open_circuit_breakers': open_breakers,
                'total_circuit_breakers': total_breakers,
                'errors_24h': total_errors
            }
            
            if open_breakers > 0:
                return HealthCheck(
                    name="resilience",
                    status=HealthStatus.WARNING,
                    message=f"{open_breakers} circuit breakers are open",
                    details=details
                )
            
            if total_errors > 100:  # More than 100 errors in 24h
                return HealthCheck(
                    name="resilience",
                    status=HealthStatus.WARNING,
                    message=f"High error count: {total_errors} errors in 24h",
                    details=details
                )
            
            return HealthCheck(
                name="resilience",
                status=HealthStatus.HEALTHY,
                message="Resilience system healthy",
                details=details
            )
            
        except Exception as e:
            return HealthCheck(
                name="resilience",
                status=HealthStatus.UNKNOWN,
                message=f"Could not check resilience: {str(e)}"
            )
    
    def run_all_checks(self) -> Dict[str, HealthCheck]:
        """Run all registered health checks"""
        results = {}
        
        for name, check_config in self._checks.items():
            try:
                result = check_config['func']()
                results[name] = result
            except Exception as e:
                self.logger.error(f"Health check {name} failed: {e}")
                results[name] = HealthCheck(
                    name=name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Check failed: {str(e)}"
                )
        
        self._last_results = results
        return results
    
    def get_overall_status(self) -> HealthStatus:
        """Get overall system health status"""
        if not self._last_results:
            self.run_all_checks()
        
        # Check for any critical failures
        critical_checks = [
            name for name, config in self._checks.items()
            if config['critical']
        ]
        
        for check_name in critical_checks:
            if check_name in self._last_results:
                result = self._last_results[check_name]
                if result.status == HealthStatus.CRITICAL:
                    return HealthStatus.CRITICAL
        
        # Check for warnings
        for result in self._last_results.values():
            if result.status == HealthStatus.WARNING:
                return HealthStatus.WARNING
        
        # Check if all checks passed
        if all(r.status == HealthStatus.HEALTHY for r in self._last_results.values()):
            return HealthStatus.HEALTHY
        
        return HealthStatus.UNKNOWN


class AlertManager:
    """Manages alerting for system issues"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.AlertManager")
        self._alert_history = deque(maxlen=1000)
        self._suppression_cache = {}  # Prevent spam
        
    def send_alert(
        self,
        title: str,
        message: str,
        severity: str = "warning",
        tags: Optional[Dict[str, str]] = None
    ):
        """Send an alert"""
        alert_key = f"{title}:{severity}"
        now = datetime.now()
        
        # Check if alert is suppressed (prevent spam)
        if alert_key in self._suppression_cache:
            last_sent = self._suppression_cache[alert_key]
            if now - last_sent < timedelta(minutes=30):  # 30 min suppression
                return
        
        alert = {
            'timestamp': now.isoformat(),
            'title': title,
            'message': message,
            'severity': severity,
            'tags': tags or {}
        }
        
        self._alert_history.append(alert)
        
        # Log the alert
        log_level = logging.ERROR if severity == 'critical' else logging.WARNING
        self.logger.log(log_level, f"ALERT [{severity.upper()}]: {title} - {message}")
        
        # Send webhook alert if configured
        if config.monitoring.alert_webhook_url:
            try:
                self._send_webhook_alert(alert)
            except Exception as e:
                self.logger.error(f"Failed to send webhook alert: {e}")
        
        # Update suppression cache
        self._suppression_cache[alert_key] = now
    
    def _send_webhook_alert(self, alert: Dict[str, Any]):
        """Send alert via webhook"""
        if requests is None:
            self.logger.warning("Cannot send webhook alert: requests library not available")
            return
        
        payload = {
            'text': f" **{alert['title']}**\n{alert['message']}",
            'severity': alert['severity'],
            'timestamp': alert['timestamp'],
            'tags': alert['tags']
        }
        
        response = requests.post(
            config.monitoring.alert_webhook_url,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
    
    def get_recent_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent alerts"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        return [
            alert for alert in self._alert_history
            if datetime.fromisoformat(alert['timestamp']) > cutoff_time
        ]


class MonitoringManager:
    """Central monitoring manager"""
    
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.health_checker = HealthChecker()
        self.alert_manager = AlertManager()
        self.logger = logging.getLogger(f"{__name__}.MonitoringManager")
        
        # Start monitoring loop
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while True:
            try:
                # Run health checks
                health_results = self.health_checker.run_all_checks()
                
                # Check for issues and send alerts
                for name, result in health_results.items():
                    if result.status == HealthStatus.CRITICAL:
                        self.alert_manager.send_alert(
                            title=f"Critical Issue: {name}",
                            message=result.message,
                            severity="critical",
                            tags={'component': name}
                        )
                    elif result.status == HealthStatus.WARNING:
                        self.alert_manager.send_alert(
                            title=f"Warning: {name}",
                            message=result.message,
                            severity="warning",
                            tags={'component': name}
                        )
                
                # Check system metrics for anomalies
                self._check_metric_anomalies()
                
                # Sleep until next check
                time.sleep(config.monitoring.health_check_interval)
                
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _check_metric_anomalies(self):
        """Check for metric anomalies and alert"""
        try:
            # Check CPU usage
            cpu_summary = self.metrics_collector.get_metric_summary("system.cpu.usage_percent", 10)
            if cpu_summary.get('avg', 0) > 90:
                self.alert_manager.send_alert(
                    title="High CPU Usage",
                    message=f"CPU usage is {cpu_summary['avg']:.1f}% (10-minute average)",
                    severity="warning"
                )
            
            # Check memory usage
            mem_summary = self.metrics_collector.get_metric_summary("system.memory.usage_percent", 10)
            if mem_summary.get('avg', 0) > 90:
                self.alert_manager.send_alert(
                    title="High Memory Usage",
                    message=f"Memory usage is {mem_summary['avg']:.1f}% (10-minute average)",
                    severity="warning"
                )
            
            # Check error rates
            error_summary = self.metrics_collector.get_metric_summary("app.resilience.total_errors", 60)
            if error_summary.get('latest', 0) > 50:  # More than 50 errors in last hour
                self.alert_manager.send_alert(
                    title="High Error Rate",
                    message=f"Error rate is high: {error_summary['latest']} errors in last hour",
                    severity="warning"
                )
                
        except Exception as e:
            self.logger.error(f"Anomaly detection error: {e}")
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data"""
        health_results = self.health_checker._last_results or self.health_checker.run_all_checks()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'overall_status': self.health_checker.get_overall_status().value,
            'health_checks': {
                name: {
                    'status': result.status.value,
                    'message': result.message,
                    'response_time_ms': result.response_time_ms,
                    'timestamp': result.timestamp.isoformat()
                }
                for name, result in health_results.items()
            },
            'system_metrics': {
                'cpu_usage': self.metrics_collector.get_metric_summary("system.cpu.usage_percent", 10),
                'memory_usage': self.metrics_collector.get_metric_summary("system.memory.usage_percent", 10),
                'disk_usage': self.metrics_collector.get_metric_summary("system.disk.usage_percent", 10)
            },
            'recent_alerts': self.alert_manager.get_recent_alerts(24),
            'cache_performance': cache_manager.get_all_stats(),
            'database_stats': db_manager.get_database_stats(),
            'system_info': {
                'platform': platform.platform(),
                'python_version': platform.python_version(),
                'uptime_seconds': time.time() - (psutil.boot_time() if psutil else 0)
            }
        }


# Global monitoring manager instance
monitoring_manager = MonitoringManager()
