"""
Resilience and Error Handling Module
Implements circuit breakers, retry logic, and graceful degradation patterns.
"""

import time
import logging
import functools
import threading
from typing import Any, Callable, Dict, Optional, Type, Union, List
from enum import Enum
from datetime import datetime, timedelta
from dataclasses import dataclass
import json


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics"""
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changed_time: Optional[datetime] = None


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open"""
    pass


class CircuitBreaker:
    """Circuit breaker implementation for API calls"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.expected_exception = expected_exception
        
        self.state = CircuitBreakerState.CLOSED
        self.stats = CircuitBreakerStats()
        self.lock = threading.RLock()
        
        # Logger
        self.logger = logging.getLogger(f"{__name__}.CircuitBreaker")
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap functions with circuit breaker"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return self._call_with_circuit_breaker(func, *args, **kwargs)
        return wrapper
    
    def _call_with_circuit_breaker(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        with self.lock:
            # Check if circuit breaker should open
            if self.state == CircuitBreakerState.CLOSED:
                if self.stats.failure_count >= self.failure_threshold:
                    self._open_circuit()
            
            # Check if circuit breaker should move to half-open
            elif self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self._half_open_circuit()
            
            # Reject calls when circuit is open
            if self.state == CircuitBreakerState.OPEN:
                raise CircuitBreakerError(
                    f"Circuit breaker is open. Last failure: {self.stats.last_failure_time}"
                )
        
        # Execute the function
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except self.expected_exception as e:
            self._record_failure()
            raise
    
    def _open_circuit(self):
        """Open the circuit breaker"""
        self.state = CircuitBreakerState.OPEN
        self.stats.state_changed_time = datetime.now()
        self.logger.warning(
            f"Circuit breaker opened after {self.stats.failure_count} failures"
        )
    
    def _half_open_circuit(self):
        """Move circuit breaker to half-open state"""
        self.state = CircuitBreakerState.HALF_OPEN
        self.stats.state_changed_time = datetime.now()
        self.logger.info("Circuit breaker moved to half-open state")
    
    def _close_circuit(self):
        """Close the circuit breaker"""
        self.state = CircuitBreakerState.CLOSED
        self.stats.failure_count = 0
        self.stats.state_changed_time = datetime.now()
        self.logger.info("Circuit breaker closed - service recovered")
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset"""
        if self.stats.state_changed_time is None:
            return True
        
        time_since_open = datetime.now() - self.stats.state_changed_time
        return time_since_open.total_seconds() >= self.timeout_seconds
    
    def _record_success(self):
        """Record successful call"""
        with self.lock:
            self.stats.success_count += 1
            self.stats.last_success_time = datetime.now()
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                self._close_circuit()
    
    def _record_failure(self):
        """Record failed call"""
        with self.lock:
            self.stats.failure_count += 1
            self.stats.last_failure_time = datetime.now()


class RetryConfig:
    """Configuration for retry logic"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter


class RetryHandler:
    """Advanced retry handler with exponential backoff and jitter"""
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.RetryHandler")
    
    def __call__(
        self,
        exceptions: Union[Type[Exception], tuple] = Exception,
        on_retry: Optional[Callable] = None
    ) -> Callable:
        """Decorator for retry logic"""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return self._execute_with_retry(func, exceptions, on_retry, *args, **kwargs)
            return wrapper
        return decorator
    
    def _execute_with_retry(
        self,
        func: Callable,
        exceptions: Union[Type[Exception], tuple],
        on_retry: Optional[Callable],
        *args,
        **kwargs
    ) -> Any:
        """Execute function with retry logic"""
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                last_exception = e
                
                if attempt == self.config.max_attempts:
                    self.logger.error(
                        f"Function {func.__name__} failed after {attempt} attempts: {e}"
                    )
                    break
                
                delay = self._calculate_delay(attempt)
                self.logger.warning(
                    f"Function {func.__name__} failed (attempt {attempt}/{self.config.max_attempts}). "
                    f"Retrying in {delay:.2f} seconds: {e}"
                )
                
                if on_retry:
                    try:
                        on_retry(attempt, e, delay)
                    except Exception as retry_callback_error:
                        self.logger.error(f"Retry callback failed: {retry_callback_error}")
                
                time.sleep(delay)
        
        # Re-raise the last exception
        if last_exception:
            raise last_exception
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter"""
        delay = min(
            self.config.base_delay * (self.config.exponential_base ** (attempt - 1)),
            self.config.max_delay
        )
        
        if self.config.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)  # Add 0-50% jitter
        
        return delay


class GracefulDegradation:
    """Manages graceful degradation when services are unavailable"""
    
    def __init__(self):
        self.fallback_data = {}
        self.service_status = {}
        self.lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.GracefulDegradation")
    
    def set_fallback_data(self, service: str, data: Any, ttl_seconds: int = 3600):
        """Set fallback data for a service"""
        with self.lock:
            self.fallback_data[service] = {
                'data': data,
                'timestamp': datetime.now(),
                'ttl_seconds': ttl_seconds
            }
    
    def get_fallback_data(self, service: str) -> Optional[Any]:
        """Get fallback data for a service"""
        with self.lock:
            if service not in self.fallback_data:
                return None
            
            entry = self.fallback_data[service]
            age = datetime.now() - entry['timestamp']
            
            if age.total_seconds() > entry['ttl_seconds']:
                self.logger.warning(f"Fallback data for {service} is stale")
                return None
            
            return entry['data']
    
    def mark_service_degraded(self, service: str, reason: str):
        """Mark a service as degraded"""
        with self.lock:
            self.service_status[service] = {
                'status': 'degraded',
                'reason': reason,
                'timestamp': datetime.now()
            }
            self.logger.warning(f"Service {service} marked as degraded: {reason}")
    
    def mark_service_healthy(self, service: str):
        """Mark a service as healthy"""
        with self.lock:
            self.service_status[service] = {
                'status': 'healthy',
                'timestamp': datetime.now()
            }
    
    def is_service_degraded(self, service: str) -> bool:
        """Check if a service is degraded"""
        with self.lock:
            return (service in self.service_status and 
                    self.service_status[service]['status'] == 'degraded')
    
    def get_service_status(self, service: str) -> Dict[str, Any]:
        """Get service status information"""
        with self.lock:
            return self.service_status.get(service, {'status': 'unknown'})


class ErrorTracker:
    """Tracks and analyzes error patterns"""
    
    def __init__(self, max_entries: int = 1000):
        self.max_entries = max_entries
        self.errors = []
        self.lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.ErrorTracker")
    
    def record_error(
        self,
        service: str,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ):
        """Record an error occurrence"""
        with self.lock:
            error_entry = {
                'timestamp': datetime.now(),
                'service': service,
                'error_type': type(error).__name__,
                'error_message': str(error),
                'context': context or {}
            }
            
            self.errors.append(error_entry)
            
            # Keep only recent errors
            if len(self.errors) > self.max_entries:
                self.errors = self.errors[-self.max_entries:]
    
    def get_error_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get error statistics for the last N hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self.lock:
            recent_errors = [
                error for error in self.errors 
                if error['timestamp'] > cutoff_time
            ]
        
        if not recent_errors:
            return {'total_errors': 0, 'services': {}, 'error_types': {}}
        
        # Analyze errors by service and type
        service_errors = {}
        error_type_counts = {}
        
        for error in recent_errors:
            service = error['service']
            error_type = error['error_type']
            
            if service not in service_errors:
                service_errors[service] = 0
            service_errors[service] += 1
            
            if error_type not in error_type_counts:
                error_type_counts[error_type] = 0
            error_type_counts[error_type] += 1
        
        return {
            'total_errors': len(recent_errors),
            'services': service_errors,
            'error_types': error_type_counts,
            'time_period_hours': hours
        }
    
    def get_recent_errors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent errors"""
        with self.lock:
            return sorted(
                self.errors[-limit:],
                key=lambda x: x['timestamp'],
                reverse=True
            )


class ResilienceManager:
    """Central manager for all resilience components"""
    
    def __init__(self):
        self.circuit_breakers = {}
        self.retry_handlers = {}
        self.degradation = GracefulDegradation()
        self.error_tracker = ErrorTracker()
        self.lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.ResilienceManager")
    
    def get_circuit_breaker(
        self,
        service: str,
        failure_threshold: int = 5,
        timeout_seconds: int = 60
    ) -> CircuitBreaker:
        """Get or create a circuit breaker for a service"""
        with self.lock:
            if service not in self.circuit_breakers:
                self.circuit_breakers[service] = CircuitBreaker(
                    failure_threshold=failure_threshold,
                    timeout_seconds=timeout_seconds
                )
            return self.circuit_breakers[service]
    
    def get_retry_handler(
        self,
        service: str,
        max_attempts: int = 3,
        base_delay: float = 1.0
    ) -> RetryHandler:
        """Get or create a retry handler for a service"""
        with self.lock:
            if service not in self.retry_handlers:
                config = RetryConfig(
                    max_attempts=max_attempts,
                    base_delay=base_delay
                )
                self.retry_handlers[service] = RetryHandler(config)
            return self.retry_handlers[service]
    
    def execute_with_resilience(
        self,
        service: str,
        func: Callable,
        fallback_data: Any = None,
        *args,
        **kwargs
    ) -> Any:
        """Execute function with full resilience protection"""
        circuit_breaker = self.get_circuit_breaker(service)
        retry_handler = self.get_retry_handler(service)
        
        try:
            # Wrap with retry and circuit breaker
            @circuit_breaker
            @retry_handler(
                exceptions=(Exception,),
                on_retry=lambda attempt, error, delay: self.error_tracker.record_error(
                    service, error, {'attempt': attempt, 'delay': delay}
                )
            )
            def protected_func():
                return func(*args, **kwargs)
            
            result = protected_func()
            
            # Mark service as healthy on success
            self.degradation.mark_service_healthy(service)
            
            # Store successful result as fallback data
            if fallback_data is None:
                self.degradation.set_fallback_data(service, result)
            
            return result
            
        except Exception as e:
            # Record error
            self.error_tracker.record_error(service, e)
            
            # Mark service as degraded
            self.degradation.mark_service_degraded(service, str(e))
            
            # Try to return fallback data
            if fallback_data is not None:
                self.logger.warning(f"Using provided fallback data for {service}: {e}")
                return fallback_data
            
            fallback = self.degradation.get_fallback_data(service)
            if fallback is not None:
                self.logger.warning(f"Using cached fallback data for {service}: {e}")
                return fallback
            
            # No fallback available, re-raise
            self.logger.error(f"No fallback available for {service}, re-raising: {e}")
            raise
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health information"""
        circuit_breaker_stats = {}
        for service, cb in self.circuit_breakers.items():
            circuit_breaker_stats[service] = {
                'state': cb.state.value,
                'failure_count': cb.stats.failure_count,
                'success_count': cb.stats.success_count,
                'last_failure': cb.stats.last_failure_time,
                'last_success': cb.stats.last_success_time
            }
        
        return {
            'timestamp': datetime.now(),
            'circuit_breakers': circuit_breaker_stats,
            'service_status': dict(self.degradation.service_status),
            'error_stats': self.error_tracker.get_error_stats(),
            'total_services': len(self.circuit_breakers)
        }


# Global resilience manager instance
resilience_manager = ResilienceManager()
