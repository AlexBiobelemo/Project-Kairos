"""
Security Module
Provides authentication, input validation, rate limiting, and security headers
"""

import os
import re
import time
import json
import hashlib
import secrets
import logging
from typing import Optional, Dict, Any, List, Callable
from functools import wraps
from datetime import datetime, timedelta
try:
    import streamlit as st
except ImportError:
    st = None

from collections import defaultdict, deque


logger = logging.getLogger(__name__)


class SecurityConfig:
    """Security configuration settings"""
    
    def __init__(self):
        self.session_timeout = int(os.getenv('SESSION_TIMEOUT', '3600'))  # 1 hour
        self.max_login_attempts = int(os.getenv('MAX_LOGIN_ATTEMPTS', '5'))
        self.lockout_duration = int(os.getenv('LOCKOUT_DURATION', '900'))  # 15 minutes
        self.rate_limit_requests = int(os.getenv('RATE_LIMIT_REQUESTS', '100'))
        self.rate_limit_window = int(os.getenv('RATE_LIMIT_WINDOW', '60'))  # 1 minute
        self.password_min_length = int(os.getenv('PASSWORD_MIN_LENGTH', '8'))
        self.enable_2fa = os.getenv('ENABLE_2FA', 'false').lower() == 'true'
        self.secret_key = os.getenv('SECRET_KEY', secrets.token_urlsafe(32))
        self.admin_users = os.getenv('ADMIN_USERS', '').split(',') if os.getenv('ADMIN_USERS') else []
        self.allowed_domains = os.getenv('ALLOWED_DOMAINS', '').split(',') if os.getenv('ALLOWED_DOMAINS') else []


class InputValidator:
    """Input validation and sanitization"""
    
    # Regex patterns for common inputs
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{3,20}$')
    API_KEY_PATTERN = re.compile(r'^[a-zA-Z0-9]{20,64}$')
    
    # Dangerous characters and patterns
    SQL_INJECTION_PATTERNS = [
        r"('|(\\')|(;)|(\\;)|(\|)|(\*)|(%)|(<)|(>)|(\{)|(\})|(\[)|(\]))",
        r"(union|select|insert|delete|update|drop|create|alter|exec|execute)",
        r"(script|javascript|vbscript|onload|onerror|onclick)"
    ]
    
    XSS_PATTERNS = [
        r"<script.*?>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe.*?>",
        r"<object.*?>",
        r"<embed.*?>"
    ]
    
    @classmethod
    def validate_email(cls, email: str) -> bool:
        """Validate email format"""
        if not isinstance(email, str) or len(email) > 254:
            return False
        return bool(cls.EMAIL_PATTERN.match(email.lower()))
    
    @classmethod
    def validate_username(cls, username: str) -> bool:
        """Validate username format"""
        if not isinstance(username, str):
            return False
        return bool(cls.USERNAME_PATTERN.match(username))
    
    @classmethod
    def validate_password(cls, password: str, min_length: int = 8) -> Dict[str, Any]:
        """Validate password strength"""
        result = {
            'valid': False,
            'errors': []
        }
        
        if not isinstance(password, str):
            result['errors'].append('Password must be a string')
            return result
        
        if len(password) < min_length:
            result['errors'].append(f'Password must be at least {min_length} characters')
        
        if not re.search(r'[A-Z]', password):
            result['errors'].append('Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', password):
            result['errors'].append('Password must contain at least one lowercase letter')
        
        if not re.search(r'\d', password):
            result['errors'].append('Password must contain at least one number')
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            result['errors'].append('Password must contain at least one special character')
        
        result['valid'] = len(result['errors']) == 0
        return result
    
    @classmethod
    def sanitize_input(cls, input_text: str, max_length: int = 1000) -> str:
        """Sanitize user input to prevent injection attacks"""
        if not isinstance(input_text, str):
            return ""
        
        # Truncate to max length
        sanitized = input_text[:max_length]
        
        # Remove null bytes
        sanitized = sanitized.replace('\x00', '')
        
        # Basic HTML encoding for XSS prevention
        sanitized = (sanitized
                    .replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;')
                    .replace('"', '&quot;')
                    .replace("'", '&#x27;'))
        
        return sanitized.strip()
    
    @classmethod
    def check_malicious_patterns(cls, input_text: str) -> List[str]:
        """Check for potentially malicious patterns"""
        threats = []
        input_lower = input_text.lower()
        
        # Check for SQL injection patterns
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, input_lower, re.IGNORECASE):
                threats.append(f'Potential SQL injection: {pattern}')
        
        # Check for XSS patterns
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, input_lower, re.IGNORECASE):
                threats.append(f'Potential XSS: {pattern}')
        
        return threats


class RateLimiter:
    """Rate limiting implementation"""
    
    def __init__(self, requests_per_window: int = 100, window_seconds: int = 60):
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.clients = defaultdict(deque)
        self.last_cleanup = time.time()
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if client is within rate limit"""
        current_time = time.time()
        client_queue = self.clients[client_id]
        
        # Remove expired entries
        while client_queue and client_queue[0] <= current_time - self.window_seconds:
            client_queue.popleft()
        
        # Check if within limit
        if len(client_queue) >= self.requests_per_window:
            logger.warning(f"Rate limit exceeded for client: {client_id}")
            return False
        
        # Add current request
        client_queue.append(current_time)
        
        # Periodic cleanup to prevent memory leaks
        if current_time - self.last_cleanup > self.window_seconds:
            self._cleanup_expired_clients()
            self.last_cleanup = current_time
        
        return True
    
    def _cleanup_expired_clients(self):
        """Remove expired client records"""
        current_time = time.time()
        expired_clients = []
        
        for client_id, queue in self.clients.items():
            if not queue or queue[-1] <= current_time - self.window_seconds:
                expired_clients.append(client_id)
        
        for client_id in expired_clients:
            del self.clients[client_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics"""
        return {
            'active_clients': len(self.clients),
            'requests_per_window': self.requests_per_window,
            'window_seconds': self.window_seconds,
            'total_requests': sum(len(queue) for queue in self.clients.values())
        }


class AuthenticationManager:
    """Authentication and session management"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.failed_attempts = defaultdict(list)
        self.locked_accounts = {}
        self.sessions = {}
        
        # Load user credentials (in production, use proper user store)
        self.users = self._load_users()
    
    def _load_users(self) -> Dict[str, Dict[str, Any]]:
        """Load user credentials from environment or file"""
        users = {}
        
        # Try to load from environment variable
        users_json = os.getenv('USERS_JSON')
        if users_json:
            try:
                users = json.loads(users_json)
            except json.JSONDecodeError:
                logger.error("Invalid USERS_JSON format")
        
        # Try to load from file
        users_file = os.getenv('USERS_FILE', 'users.json')
        if os.path.exists(users_file):
            try:
                with open(users_file, 'r') as f:
                    file_users = json.load(f)
                    users.update(file_users)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading users file: {e}")
        
        # Default admin user if no users configured
        if not users:
            admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
            users = {
                'admin': {
                    'password_hash': self._hash_password(admin_password),
                    'role': 'admin',
                    'email': 'admin@kairos.local'
                }
            }
            logger.warning("Using default admin credentials. Please change in production!")
        
        return users
    
    def _hash_password(self, password: str) -> str:
        """Hash password with salt"""
        salt = secrets.token_hex(32)
        password_hash = hashlib.pbkdf2_hmac('sha256', 
                                          password.encode('utf-8'), 
                                          salt.encode('utf-8'), 
                                          100000)
        return f"{salt}:{password_hash.hex()}"
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        try:
            salt, hash_hex = password_hash.split(':', 1)
            password_bytes = hashlib.pbkdf2_hmac('sha256',
                                               password.encode('utf-8'),
                                               salt.encode('utf-8'),
                                               100000)
            return secrets.compare_digest(password_bytes.hex(), hash_hex)
        except ValueError:
            return False
    
    def is_account_locked(self, username: str) -> bool:
        """Check if account is locked due to failed attempts"""
        if username in self.locked_accounts:
            lock_time = self.locked_accounts[username]
            if time.time() - lock_time > self.config.lockout_duration:
                del self.locked_accounts[username]
                self.failed_attempts[username].clear()
                return False
            return True
        return False
    
    def record_failed_attempt(self, username: str):
        """Record failed login attempt"""
        current_time = time.time()
        self.failed_attempts[username].append(current_time)
        
        # Remove old attempts
        cutoff_time = current_time - self.config.lockout_duration
        self.failed_attempts[username] = [
            attempt_time for attempt_time in self.failed_attempts[username]
            if attempt_time > cutoff_time
        ]
        
        # Lock account if too many attempts
        if len(self.failed_attempts[username]) >= self.config.max_login_attempts:
            self.locked_accounts[username] = current_time
            logger.warning(f"Account locked due to failed attempts: {username}")
    
    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user credentials"""
        if self.is_account_locked(username):
            return None
        
        if username not in self.users:
            self.record_failed_attempt(username)
            return None
        
        user = self.users[username]
        if not self._verify_password(password, user['password_hash']):
            self.record_failed_attempt(username)
            return None
        
        # Clear failed attempts on successful login
        if username in self.failed_attempts:
            self.failed_attempts[username].clear()
        if username in self.locked_accounts:
            del self.locked_accounts[username]
        
        # Create session
        session_id = secrets.token_urlsafe(32)
        session_data = {
            'username': username,
            'role': user.get('role', 'user'),
            'email': user.get('email', ''),
            'created_at': time.time(),
            'last_activity': time.time()
        }
        self.sessions[session_id] = session_data
        
        logger.info(f"User authenticated successfully: {username}")
        return {
            'session_id': session_id,
            'user': session_data
        }
    
    def validate_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Validate session and check timeout"""
        if not session_id or session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        current_time = time.time()
        
        # Check session timeout
        if current_time - session['last_activity'] > self.config.session_timeout:
            del self.sessions[session_id]
            return None
        
        # Update last activity
        session['last_activity'] = current_time
        return session
    
    def logout(self, session_id: str):
        """Logout user and remove session"""
        if session_id in self.sessions:
            username = self.sessions[session_id]['username']
            del self.sessions[session_id]
            logger.info(f"User logged out: {username}")
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        current_time = time.time()
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            if current_time - session['last_activity'] > self.config.session_timeout:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.sessions[session_id]


class SecurityHeaders:
    """HTTP security headers for Streamlit"""
    
    @staticmethod
    def set_security_headers():
        """Set security headers in Streamlit"""
        try:

            st.markdown("""
            <script>
            // Set security headers via meta tags where possible
            if (!document.querySelector('meta[http-equiv="X-Content-Type-Options"]')) {
                var meta = document.createElement('meta');
                meta.httpEquiv = 'X-Content-Type-Options';
                meta.content = 'nosniff';
                document.head.appendChild(meta);
            }
            
            if (!document.querySelector('meta[http-equiv="X-Frame-Options"]')) {
                var meta = document.createElement('meta');
                meta.httpEquiv = 'X-Frame-Options';
                meta.content = 'DENY';
                document.head.appendChild(meta);
            }
            
            if (!document.querySelector('meta[http-equiv="Referrer-Policy"]')) {
                var meta = document.createElement('meta');
                meta.httpEquiv = 'Referrer-Policy';
                meta.content = 'strict-origin-when-cross-origin';
                document.head.appendChild(meta);
            }
            </script>
            """, unsafe_allow_html=True)
        except Exception as e:
            logger.error(f"Error setting security headers: {e}")


def require_authentication(func: Callable) -> Callable:
    """Decorator to require authentication for Streamlit functions"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'security_manager' not in st.session_state:
            st.session_state.security_manager = SecurityManager()
        
        security_manager = st.session_state.security_manager
        
        if not security_manager.is_authenticated():
            security_manager.show_login_form()
            return None
        
        return func(*args, **kwargs)
    
    return wrapper


def require_role(required_role: str):
    """Decorator to require specific role"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if 'security_manager' not in st.session_state:
                st.session_state.security_manager = SecurityManager()
            
            security_manager = st.session_state.security_manager
            
            if not security_manager.is_authenticated():
                security_manager.show_login_form()
                return None
            
            user_role = security_manager.get_current_user().get('role', 'user')
            if user_role != required_role and user_role != 'admin':
                st.error(f"Access denied. Required role: {required_role}")
                return None
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


class SecurityManager:
    """Main security manager class"""
    
    def __init__(self):
        self.config = SecurityConfig()
        self.auth_manager = AuthenticationManager(self.config)
        self.rate_limiter = RateLimiter(
            self.config.rate_limit_requests,
            self.config.rate_limit_window
        )
        self.validator = InputValidator()
        
        # Set security headers
        SecurityHeaders.set_security_headers()
        
        # Initialize session state
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        if 'session_id' not in st.session_state:
            st.session_state.session_id = None
        if 'user' not in st.session_state:
            st.session_state.user = None
    
    def get_client_id(self) -> str:
        """Get client identifier for rate limiting"""

        if hasattr(st, 'session_state') and hasattr(st.session_state, 'session_id'):
            return st.session_state.session_id or 'anonymous'
        return 'anonymous'
    
    def check_rate_limit(self) -> bool:
        """Check if current client is within rate limit"""
        client_id = self.get_client_id()
        return self.rate_limiter.is_allowed(client_id)
    
    def show_login_form(self):
        """Display login form"""
        st.title("Login Required")
        
        if not self.check_rate_limit():
            st.error("Too many requests. Please try again later.")
            return
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                if not username or not password:
                    st.error("Please enter both username and password")
                    return
                
                # Validate inputs
                if not self.validator.validate_username(username):
                    st.error("Invalid username format")
                    return
                
                # Check for malicious patterns
                threats = self.validator.check_malicious_patterns(username + password)
                if threats:
                    st.error("Invalid input detected")
                    logger.warning(f"Malicious input attempt: {threats}")
                    return
                
                # Authenticate
                auth_result = self.auth_manager.authenticate(username, password)
                if auth_result:
                    st.session_state.authenticated = True
                    st.session_state.session_id = auth_result['session_id']
                    st.session_state.user = auth_result['user']
                    st.success("Login successful!")
                    st.rerun()
                else:
                    if self.auth_manager.is_account_locked(username):
                        st.error("Account temporarily locked due to failed attempts")
                    else:
                        st.error("Invalid credentials")
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        if not st.session_state.authenticated or not st.session_state.session_id:
            return False
        
        # Validate session
        session = self.auth_manager.validate_session(st.session_state.session_id)
        if not session:
            st.session_state.authenticated = False
            st.session_state.session_id = None
            st.session_state.user = None
            return False
        
        # Update user data
        st.session_state.user = session
        return True
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Get current authenticated user"""
        if self.is_authenticated():
            return st.session_state.user
        return None
    
    def logout(self):
        """Logout current user"""
        if st.session_state.session_id:
            self.auth_manager.logout(st.session_state.session_id)
        
        st.session_state.authenticated = False
        st.session_state.session_id = None
        st.session_state.user = None
        st.rerun()
    
    def show_user_info(self):
        """Show current user info in sidebar"""
        if self.is_authenticated():
            user = self.get_current_user()
            with st.sidebar:
                st.write(f" **{user['username']}**")
                st.write(f" {user.get('email', 'N/A')}")
                st.write(f" Role: {user.get('role', 'user')}")
                if st.button("Logout"):
                    self.logout()
    
    def cleanup(self):
        """Cleanup expired sessions and data"""
        self.auth_manager.cleanup_expired_sessions()
        
        # Cleanup rate limiter
        self.rate_limiter._cleanup_expired_clients()


# Example usage and testing functions
def create_test_users():
    """Create test users file"""
    users = {
        "admin": {
            "password_hash": SecurityManager().auth_manager._hash_password("SecureAdmin123!"),
            "role": "admin",
            "email": "admin@kairos.local"
        },
        "analyst": {
            "password_hash": SecurityManager().auth_manager._hash_password("Analyst456!"),
            "role": "analyst",
            "email": "analyst@kairos.local"
        },
        "viewer": {
            "password_hash": SecurityManager().auth_manager._hash_password("Viewer789!"),
            "role": "viewer",
            "email": "viewer@kairos.local"
        }
    }
    
    with open('users.json', 'w') as f:
        json.dump(users, f, indent=2)
    
    print("Test users created in users.json")
    print("Admin: admin / SecureAdmin123!")
    print("Analyst: analyst / Analyst456!")
    print("Viewer: viewer / Viewer789!")


if __name__ == "__main__":
    # Create test users if running directly
    create_test_users()
