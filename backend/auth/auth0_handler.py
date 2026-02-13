"""
Auth0 Authentication Handler - Enterprise-Grade Multi-tenant Auth

Features:
- JWT token validation
- Role-based access control (RBAC)
- Organization/tenant isolation
- API key support for programmatic access
- Rate limiting per user/org
"""

import os
import json
import time
import hashlib
from functools import wraps
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass
import requests

# JWT handling
try:
    from jose import jwt, JWTError
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    print("Warning: python-jose not installed. Run: pip install python-jose")

from flask import request, jsonify, g


@dataclass
class Auth0Config:
    """Auth0 configuration"""
    domain: str  # e.g., "your-tenant.auth0.com"
    api_audience: str  # e.g., "https://api.knowledgevault.com"
    client_id: str
    client_secret: str
    algorithms: List[str] = None

    def __post_init__(self):
        if self.algorithms is None:
            self.algorithms = ["RS256"]


@dataclass
class User:
    """Authenticated user object"""
    id: str
    email: str
    name: str
    organization_id: Optional[str] = None
    roles: List[str] = None
    permissions: List[str] = None
    metadata: Dict = None

    def __post_init__(self):
        if self.roles is None:
            self.roles = []
        if self.permissions is None:
            self.permissions = []
        if self.metadata is None:
            self.metadata = {}

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def get_namespace(self) -> str:
        """Get Pinecone namespace for this user's data"""
        return self.organization_id or f"user_{self.id}"


class Auth0Handler:
    """
    Auth0 authentication handler for Flask applications.

    Usage:
        auth = Auth0Handler(config)

        @app.route('/api/protected')
        @auth.requires_auth
        def protected_route():
            user = g.current_user
            return jsonify({'user': user.email})

        @app.route('/api/admin')
        @auth.requires_role('admin')
        def admin_route():
            return jsonify({'message': 'Admin access granted'})
    """

    def __init__(self, config: Optional[Auth0Config] = None):
        if not JWT_AVAILABLE:
            raise ImportError("python-jose not installed")

        # Load from environment if not provided
        if config is None:
            config = Auth0Config(
                domain=os.getenv("AUTH0_DOMAIN", ""),
                api_audience=os.getenv("AUTH0_API_AUDIENCE", ""),
                client_id=os.getenv("AUTH0_CLIENT_ID", ""),
                client_secret=os.getenv("AUTH0_CLIENT_SECRET", "")
            )

        self.config = config
        self.jwks_url = f"https://{config.domain}/.well-known/jwks.json"
        self._jwks_cache = None
        self._jwks_cache_time = 0
        self._api_keys: Dict[str, User] = {}  # API key -> User mapping

    def _get_jwks(self) -> Dict:
        """Get JSON Web Key Set from Auth0 (cached)"""
        # Cache JWKS for 1 hour
        if self._jwks_cache and time.time() - self._jwks_cache_time < 3600:
            return self._jwks_cache

        response = requests.get(self.jwks_url)
        self._jwks_cache = response.json()
        self._jwks_cache_time = time.time()
        return self._jwks_cache

    def _get_token_from_header(self) -> Optional[str]:
        """Extract token from Authorization header"""
        auth_header = request.headers.get("Authorization", "")

        if not auth_header:
            return None

        parts = auth_header.split()

        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]

        return None

    def _get_api_key_from_header(self) -> Optional[str]:
        """Extract API key from X-API-Key header"""
        return request.headers.get("X-API-Key")

    def _validate_token(self, token: str) -> Optional[Dict]:
        """Validate JWT token and return payload"""
        try:
            jwks = self._get_jwks()

            # Get unverified header to find the key
            unverified_header = jwt.get_unverified_header(token)

            # Find the matching key
            rsa_key = {}
            for key in jwks.get("keys", []):
                if key["kid"] == unverified_header.get("kid"):
                    rsa_key = {
                        "kty": key["kty"],
                        "kid": key["kid"],
                        "use": key["use"],
                        "n": key["n"],
                        "e": key["e"]
                    }
                    break

            if not rsa_key:
                return None

            # Validate token
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=self.config.algorithms,
                audience=self.config.api_audience,
                issuer=f"https://{self.config.domain}/"
            )

            return payload

        except JWTError as e:
            print(f"JWT validation error: {e}")
            return None
        except Exception as e:
            print(f"Token validation error: {e}")
            return None

    def _payload_to_user(self, payload: Dict) -> User:
        """Convert JWT payload to User object"""
        # Auth0 namespaced claims
        namespace = "https://knowledgevault.com/"

        return User(
            id=payload.get("sub", ""),
            email=payload.get(f"{namespace}email", payload.get("email", "")),
            name=payload.get(f"{namespace}name", payload.get("name", "")),
            organization_id=payload.get(f"{namespace}organization_id"),
            roles=payload.get(f"{namespace}roles", []),
            permissions=payload.get("permissions", []),
            metadata=payload.get(f"{namespace}metadata", {})
        )

    def register_api_key(self, api_key: str, user: User) -> None:
        """Register an API key for a user (for programmatic access)"""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        self._api_keys[key_hash] = user

    def validate_api_key(self, api_key: str) -> Optional[User]:
        """Validate API key and return associated user"""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        return self._api_keys.get(key_hash)

    def get_current_user(self) -> Optional[User]:
        """Get current authenticated user from request"""
        # Try JWT token first
        token = self._get_token_from_header()
        if token:
            payload = self._validate_token(token)
            if payload:
                return self._payload_to_user(payload)

        # Try API key
        api_key = self._get_api_key_from_header()
        if api_key:
            return self.validate_api_key(api_key)

        return None

    def requires_auth(self, f: Callable) -> Callable:
        """Decorator: Require authentication"""
        @wraps(f)
        def decorated(*args, **kwargs):
            user = self.get_current_user()

            if not user:
                return jsonify({
                    "error": "Unauthorized",
                    "message": "Valid authentication required"
                }), 401

            # Store user in Flask's g object for access in route
            g.current_user = user
            return f(*args, **kwargs)

        return decorated

    def requires_role(self, role: str) -> Callable:
        """Decorator: Require specific role"""
        def decorator(f: Callable) -> Callable:
            @wraps(f)
            def decorated(*args, **kwargs):
                user = self.get_current_user()

                if not user:
                    return jsonify({
                        "error": "Unauthorized",
                        "message": "Valid authentication required"
                    }), 401

                if not user.has_role(role):
                    return jsonify({
                        "error": "Forbidden",
                        "message": f"Role '{role}' required"
                    }), 403

                g.current_user = user
                return f(*args, **kwargs)

            return decorated
        return decorator

    def requires_permission(self, permission: str) -> Callable:
        """Decorator: Require specific permission"""
        def decorator(f: Callable) -> Callable:
            @wraps(f)
            def decorated(*args, **kwargs):
                user = self.get_current_user()

                if not user:
                    return jsonify({
                        "error": "Unauthorized",
                        "message": "Valid authentication required"
                    }), 401

                if not user.has_permission(permission):
                    return jsonify({
                        "error": "Forbidden",
                        "message": f"Permission '{permission}' required"
                    }), 403

                g.current_user = user
                return f(*args, **kwargs)

            return decorated
        return decorator

    def optional_auth(self, f: Callable) -> Callable:
        """Decorator: Optional authentication (sets user if available)"""
        @wraps(f)
        def decorated(*args, **kwargs):
            user = self.get_current_user()
            g.current_user = user  # May be None
            return f(*args, **kwargs)

        return decorated


class RateLimiter:
    """
    Simple in-memory rate limiter for API endpoints.
    For production, use Redis-based rate limiting.
    """

    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self._requests: Dict[str, List[float]] = {}

    def _clean_old_requests(self, key: str) -> None:
        """Remove requests older than 1 minute"""
        now = time.time()
        if key in self._requests:
            self._requests[key] = [
                t for t in self._requests[key]
                if now - t < 60
            ]

    def check_rate_limit(self, key: str) -> bool:
        """Check if request is within rate limit"""
        self._clean_old_requests(key)

        if key not in self._requests:
            self._requests[key] = []

        if len(self._requests[key]) >= self.rpm:
            return False

        self._requests[key].append(time.time())
        return True

    def rate_limit(self, key_func: Callable = None) -> Callable:
        """Decorator: Apply rate limiting"""
        def decorator(f: Callable) -> Callable:
            @wraps(f)
            def decorated(*args, **kwargs):
                # Get rate limit key (default: IP address)
                if key_func:
                    key = key_func()
                else:
                    key = request.remote_addr

                if not self.check_rate_limit(key):
                    return jsonify({
                        "error": "Rate limit exceeded",
                        "message": f"Maximum {self.rpm} requests per minute"
                    }), 429

                return f(*args, **kwargs)

            return decorated
        return decorator


# Example usage in Flask app
def init_auth(app):
    """Initialize Auth0 authentication for Flask app"""
    auth = Auth0Handler()
    rate_limiter = RateLimiter(requests_per_minute=100)

    # Store in app context
    app.auth = auth
    app.rate_limiter = rate_limiter

    return auth, rate_limiter
