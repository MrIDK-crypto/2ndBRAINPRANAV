"""
Authentication Service
Enterprise-grade authentication with JWT, bcrypt, MFA support, and security features.
"""

import os
import re
import secrets
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass

import jwt
import bcrypt
from sqlalchemy.orm import Session

# Email configuration - uses same Gmail account as email forwarding
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
# Use FORWARD_EMAIL credentials for sending (same Gmail account)
SMTP_USER = os.getenv('SMTP_USER') or os.getenv('FORWARD_EMAIL_ADDRESS', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD') or os.getenv('FORWARD_EMAIL_PASSWORD', '')
SMTP_FROM_EMAIL = os.getenv('SMTP_FROM_EMAIL') or SMTP_USER or 'noreply@2ndbrain.ai'
SMTP_FROM_NAME = os.getenv('SMTP_FROM_NAME', '2nd Brain')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3006')

from database.models import (
    User, UserSession, Tenant, AuditLog, PasswordResetToken,
    EmailVerificationToken, Invitation, InvitationStatus,
    UserRole, TenantPlan,
    generate_uuid, utc_now
)
from database.config import (
    JWT_SECRET_KEY, JWT_ALGORITHM,
    JWT_ACCESS_TOKEN_EXPIRES, JWT_REFRESH_TOKEN_EXPIRES,
    BCRYPT_ROUNDS
)


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class TokenPair:
    """Access and refresh token pair"""
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime
    token_type: str = "Bearer"


@dataclass
class AuthResult:
    """Authentication result"""
    success: bool
    user: Optional[User] = None
    tokens: Optional[TokenPair] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


@dataclass
class SignupData:
    """User signup data"""
    email: str
    password: str
    full_name: str
    organization_name: Optional[str] = None
    invite_code: Optional[str] = None


# ============================================================================
# PASSWORD UTILITIES
# ============================================================================

class PasswordUtils:
    """Password hashing and validation utilities"""

    # Password requirements
    MIN_LENGTH = 8
    MAX_LENGTH = 128
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = False

    @classmethod
    def hash_password(cls, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    @classmethod
    def verify_password(cls, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                password_hash.encode('utf-8')
            )
        except Exception:
            return False

    @classmethod
    def validate_password_strength(cls, password: str) -> Tuple[bool, List[str]]:
        """
        Validate password strength.
        Returns (is_valid, list of errors)
        """
        errors = []

        if len(password) < cls.MIN_LENGTH:
            errors.append(f"Password must be at least {cls.MIN_LENGTH} characters")

        if len(password) > cls.MAX_LENGTH:
            errors.append(f"Password must be at most {cls.MAX_LENGTH} characters")

        if cls.REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")

        if cls.REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")

        if cls.REQUIRE_DIGIT and not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")

        if cls.REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")

        # Check for common passwords (basic check)
        common_passwords = {'password', 'password123', '123456', 'qwerty', 'admin'}
        if password.lower() in common_passwords:
            errors.append("Password is too common")

        return len(errors) == 0, errors

    @classmethod
    def generate_random_password(cls, length: int = 16) -> str:
        """Generate a secure random password"""
        import string
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(chars) for _ in range(length))


# ============================================================================
# JWT UTILITIES
# ============================================================================

class JWTUtils:
    """JWT token utilities"""

    @classmethod
    def create_access_token(
        cls,
        user_id: str,
        tenant_id: str,
        email: str,
        role: str,
        expires_delta: Optional[timedelta] = None
    ) -> Tuple[str, datetime, str]:
        """
        Create JWT access token.
        Returns (token, expires_at, jti)
        """
        jti = generate_uuid()  # Unique token identifier
        now = utc_now()

        if expires_delta:
            expires_at = now + expires_delta
        else:
            expires_at = now + timedelta(seconds=JWT_ACCESS_TOKEN_EXPIRES)

        payload = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "email": email,
            "role": role,
            "jti": jti,
            "iat": now,
            "exp": expires_at,
            "type": "access"
        }

        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return token, expires_at, jti

    @classmethod
    def create_refresh_token(
        cls,
        user_id: str,
        expires_delta: Optional[timedelta] = None
    ) -> Tuple[str, datetime]:
        """
        Create refresh token.
        Returns (token, expires_at)
        """
        now = utc_now()

        if expires_delta:
            expires_at = now + expires_delta
        else:
            expires_at = now + timedelta(seconds=JWT_REFRESH_TOKEN_EXPIRES)

        # Refresh token is a random string, not a JWT
        token = secrets.token_urlsafe(64)

        return token, expires_at

    @classmethod
    def decode_access_token(cls, token: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Decode and validate access token.
        Returns (payload, error)
        """
        try:
            payload = jwt.decode(
                token,
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM]
            )

            # Verify it's an access token
            if payload.get("type") != "access":
                return None, "Invalid token type"

            return payload, None

        except jwt.ExpiredSignatureError:
            return None, "Token has expired"
        except jwt.InvalidTokenError as e:
            return None, f"Invalid token: {str(e)}"

    @classmethod
    def hash_refresh_token(cls, token: str) -> str:
        """Hash refresh token for storage"""
        return hashlib.sha256(token.encode()).hexdigest()


# ============================================================================
# AUTHENTICATION SERVICE
# ============================================================================

class AuthService:
    """Main authentication service"""

    def __init__(self, db: Session):
        self.db = db

    # ========================================================================
    # USER REGISTRATION
    # ========================================================================

    def signup(
        self,
        data: SignupData,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuthResult:
        """
        Register a new user and organization.
        Creates a new tenant if organization_name is provided.
        """
        try:
            # Validate email format
            email = data.email.lower().strip()
            if not self._validate_email(email):
                return AuthResult(
                    success=False,
                    error="Invalid email format",
                    error_code="INVALID_EMAIL"
                )

            # Validate password strength
            is_valid, password_errors = PasswordUtils.validate_password_strength(data.password)
            if not is_valid:
                return AuthResult(
                    success=False,
                    error="; ".join(password_errors),
                    error_code="WEAK_PASSWORD"
                )

            # Check if email already exists (across all tenants for now)
            existing_user = self.db.query(User).filter(
                User.email == email,
                User.is_active == True
            ).first()

            if existing_user:
                return AuthResult(
                    success=False,
                    error="An account with this email already exists",
                    error_code="EMAIL_EXISTS"
                )

            # Check if this is an invitation-based signup
            invitation = None
            tenant = None
            user_role = UserRole.ADMIN  # Default for new org creators

            if data.invite_code:
                # Validate invitation token
                import hashlib
                from database.models import Invitation, InvitationStatus

                token_hash = hashlib.sha256(data.invite_code.encode()).hexdigest()
                invitation = self.db.query(Invitation).filter(
                    Invitation.token_hash == token_hash
                ).first()

                if not invitation:
                    return AuthResult(
                        success=False,
                        error="Invalid invitation link",
                        error_code="INVALID_INVITATION"
                    )

                if not invitation.is_valid:
                    if invitation.status == InvitationStatus.ACCEPTED:
                        return AuthResult(
                            success=False,
                            error="This invitation has already been used",
                            error_code="INVITATION_USED"
                        )
                    elif invitation.status == InvitationStatus.REVOKED:
                        return AuthResult(
                            success=False,
                            error="This invitation has been revoked",
                            error_code="INVITATION_REVOKED"
                        )
                    else:
                        return AuthResult(
                            success=False,
                            error="This invitation has expired",
                            error_code="INVITATION_EXPIRED"
                        )

                # Get the existing tenant from the invitation
                tenant = self.db.query(Tenant).filter(
                    Tenant.id == invitation.tenant_id
                ).first()

                if not tenant:
                    return AuthResult(
                        success=False,
                        error="The organization no longer exists",
                        error_code="TENANT_NOT_FOUND"
                    )

                # Check if email matches invitation (optional - could allow any email)
                # For now, we'll be flexible and allow any email to use the invitation
                user_role = invitation.role  # Use the role specified in the invitation
                print(f"[Auth] Signup via invitation for tenant: {tenant.name}")

            if not tenant:
                # No invitation - create new tenant (organization)
                org_name = data.organization_name or f"{data.full_name}'s Organization"
                tenant_slug = self._generate_tenant_slug(org_name)

                # Create tenant data directory path
                from pathlib import Path
                base_path = Path(__file__).parent.parent / "tenant_data" / tenant_slug

                tenant = Tenant(
                    name=org_name,
                    slug=tenant_slug,
                    plan=TenantPlan.FREE,
                    plan_started_at=utc_now(),
                    data_directory=str(base_path)
                )
                self.db.add(tenant)
                self.db.flush()  # Get tenant ID

                # Create tenant data directory
                self._create_tenant_directory(tenant)

            # Create user
            user = User(
                tenant_id=tenant.id,
                email=email,
                password_hash=PasswordUtils.hash_password(data.password),
                full_name=data.full_name,
                role=user_role,
                email_verified=False
            )
            self.db.add(user)
            self.db.flush()  # Get user ID

            # If this was an invitation signup, mark it as accepted
            if invitation:
                invitation.status = InvitationStatus.ACCEPTED
                invitation.accepted_at = utc_now()
                invitation.accepted_by_user_id = user.id

            # Generate tokens
            tokens = self._create_token_pair(user, tenant, ip_address, user_agent)

            # Log the signup
            self._log_action(
                tenant_id=tenant.id,
                user_id=user.id,
                action="user.signup",
                resource_type="user",
                resource_id=user.id,
                details={"email": email, "organization": org_name},
                ip_address=ip_address,
                user_agent=user_agent
            )

            self.db.commit()

            # Send verification email (after commit so user exists)
            # Wrap in try/except so signup succeeds even if email fails
            try:
                self.send_verification_email(user, ip_address)
            except Exception as email_error:
                print(f"[Auth] Warning: Failed to send verification email: {email_error}")
                import traceback
                traceback.print_exc()
                # Don't fail signup if email fails - user can resend

            return AuthResult(
                success=True,
                user=user,
                tokens=tokens
            )

        except Exception as e:
            self.db.rollback()
            import traceback
            print(f"[Auth] Signup error: {e}")
            traceback.print_exc()
            return AuthResult(
                success=False,
                error=f"Signup failed: {str(e)}",
                error_code="SIGNUP_ERROR"
            )

    # ========================================================================
    # USER LOGIN
    # ========================================================================

    def login(
        self,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuthResult:
        """
        Authenticate user with email and password.
        Returns tokens on success.
        """
        try:
            email = email.lower().strip()

            # Find user
            user = self.db.query(User).filter(
                User.email == email,
                User.is_active == True
            ).first()

            if not user:
                # Don't reveal if user exists
                return AuthResult(
                    success=False,
                    error="Invalid email or password",
                    error_code="INVALID_CREDENTIALS"
                )

            # Check if account is locked
            if user.locked_until and user.locked_until > utc_now():
                remaining = (user.locked_until - utc_now()).seconds // 60
                return AuthResult(
                    success=False,
                    error=f"Account is locked. Try again in {remaining} minutes",
                    error_code="ACCOUNT_LOCKED"
                )

            # Verify password
            if not PasswordUtils.verify_password(password, user.password_hash):
                # Increment failed attempts
                user.failed_login_attempts += 1

                # Lock account after 5 failed attempts
                if user.failed_login_attempts >= 5:
                    user.locked_until = utc_now() + timedelta(minutes=15)
                    self._log_action(
                        tenant_id=user.tenant_id,
                        user_id=user.id,
                        action="user.locked",
                        resource_type="user",
                        resource_id=user.id,
                        details={"reason": "Too many failed login attempts"},
                        ip_address=ip_address
                    )

                self.db.commit()

                return AuthResult(
                    success=False,
                    error="Invalid email or password",
                    error_code="INVALID_CREDENTIALS"
                )

            # Check if tenant is active
            tenant = user.tenant
            if not tenant.is_active:
                return AuthResult(
                    success=False,
                    error="Organization has been deactivated",
                    error_code="TENANT_INACTIVE"
                )

            # Successful login - reset failed attempts
            user.failed_login_attempts = 0
            user.locked_until = None
            user.last_login_at = utc_now()
            user.last_login_ip = ip_address

            # Generate tokens
            tokens = self._create_token_pair(user, tenant, ip_address, user_agent)

            # Log successful login
            self._log_action(
                tenant_id=user.tenant_id,
                user_id=user.id,
                action="user.login",
                resource_type="user",
                resource_id=user.id,
                details={"method": "password"},
                ip_address=ip_address,
                user_agent=user_agent
            )

            self.db.commit()

            return AuthResult(
                success=True,
                user=user,
                tokens=tokens
            )

        except Exception as e:
            self.db.rollback()
            return AuthResult(
                success=False,
                error=f"Login failed: {str(e)}",
                error_code="LOGIN_ERROR"
            )

    # ========================================================================
    # TOKEN REFRESH
    # ========================================================================

    def refresh_tokens(
        self,
        refresh_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuthResult:
        """
        Refresh access token using refresh token.
        Implements token rotation for security.
        """
        try:
            # Hash the token to find in database
            token_hash = JWTUtils.hash_refresh_token(refresh_token)

            # Find session
            session = self.db.query(UserSession).filter(
                UserSession.refresh_token_hash == token_hash,
                UserSession.is_revoked == False
            ).first()

            if not session:
                return AuthResult(
                    success=False,
                    error="Invalid refresh token",
                    error_code="INVALID_REFRESH_TOKEN"
                )

            # Check if expired
            if session.expires_at < utc_now():
                session.is_revoked = True
                session.revoked_reason = "expired"
                self.db.commit()
                return AuthResult(
                    success=False,
                    error="Refresh token has expired",
                    error_code="REFRESH_TOKEN_EXPIRED"
                )

            # Get user
            user = session.user
            if not user or not user.is_active:
                return AuthResult(
                    success=False,
                    error="User not found or inactive",
                    error_code="USER_INACTIVE"
                )

            tenant = user.tenant
            if not tenant or not tenant.is_active:
                return AuthResult(
                    success=False,
                    error="Organization is inactive",
                    error_code="TENANT_INACTIVE"
                )

            # Revoke old session (token rotation)
            session.is_revoked = True
            session.revoked_at = utc_now()
            session.revoked_reason = "rotated"

            # Create new tokens
            tokens = self._create_token_pair(user, tenant, ip_address, user_agent)

            # Update last used
            session.last_used_at = utc_now()

            self.db.commit()

            return AuthResult(
                success=True,
                user=user,
                tokens=tokens
            )

        except Exception as e:
            self.db.rollback()
            return AuthResult(
                success=False,
                error=f"Token refresh failed: {str(e)}",
                error_code="REFRESH_ERROR"
            )

    # ========================================================================
    # LOGOUT
    # ========================================================================

    def logout(
        self,
        access_token: str,
        ip_address: Optional[str] = None
    ) -> bool:
        """Logout user by revoking the current session"""
        try:
            # Decode token to get JTI
            payload, error = JWTUtils.decode_access_token(access_token)
            if error or not payload:
                return False

            jti = payload.get("jti")
            user_id = payload.get("sub")

            # Find and revoke session
            session = self.db.query(UserSession).filter(
                UserSession.user_id == user_id,
                UserSession.access_token_jti == jti,
                UserSession.is_revoked == False
            ).first()

            if session:
                session.is_revoked = True
                session.revoked_at = utc_now()
                session.revoked_reason = "logout"

                self._log_action(
                    tenant_id=payload.get("tenant_id"),
                    user_id=user_id,
                    action="user.logout",
                    resource_type="user",
                    resource_id=user_id,
                    ip_address=ip_address
                )

                self.db.commit()

            return True

        except Exception:
            self.db.rollback()
            return False

    def logout_all_sessions(
        self,
        user_id: str,
        except_current_jti: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> int:
        """Logout all user sessions (except optionally current one)"""
        try:
            query = self.db.query(UserSession).filter(
                UserSession.user_id == user_id,
                UserSession.is_revoked == False
            )

            if except_current_jti:
                query = query.filter(UserSession.access_token_jti != except_current_jti)

            sessions = query.all()
            count = len(sessions)

            for session in sessions:
                session.is_revoked = True
                session.revoked_at = utc_now()
                session.revoked_reason = "logout_all"

            self.db.commit()
            return count

        except Exception:
            self.db.rollback()
            return 0

    # ========================================================================
    # TOKEN VALIDATION
    # ========================================================================

    def validate_access_token(self, token: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Validate access token and return payload.
        Also checks if session is revoked.
        """
        payload, error = JWTUtils.decode_access_token(token)
        if error:
            return None, error

        # Check if session is revoked
        jti = payload.get("jti")
        user_id = payload.get("sub")

        session = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.access_token_jti == jti
        ).first()

        if session and session.is_revoked:
            return None, "Token has been revoked"

        return payload, None

    def get_current_user(self, token: str) -> Optional[User]:
        """Get user from access token"""
        payload, error = self.validate_access_token(token)
        if error or not payload:
            return None

        user_id = payload.get("sub")
        return self.db.query(User).filter(
            User.id == user_id,
            User.is_active == True
        ).first()

    # ========================================================================
    # PASSWORD MANAGEMENT
    # ========================================================================

    def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
        logout_other_sessions: bool = True,
        ip_address: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Change user password"""
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return False, "User not found"

            # Verify current password
            if not PasswordUtils.verify_password(current_password, user.password_hash):
                return False, "Current password is incorrect"

            # Validate new password
            is_valid, errors = PasswordUtils.validate_password_strength(new_password)
            if not is_valid:
                return False, "; ".join(errors)

            # Update password
            user.password_hash = PasswordUtils.hash_password(new_password)
            user.updated_at = utc_now()

            # Logout other sessions if requested
            if logout_other_sessions:
                self.logout_all_sessions(user_id)

            self._log_action(
                tenant_id=user.tenant_id,
                user_id=user_id,
                action="user.password_changed",
                resource_type="user",
                resource_id=user_id,
                ip_address=ip_address
            )

            self.db.commit()
            return True, None

        except Exception as e:
            self.db.rollback()
            return False, str(e)

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _create_token_pair(
        self,
        user: User,
        tenant: Tenant,
        ip_address: Optional[str],
        user_agent: Optional[str]
    ) -> TokenPair:
        """Create access and refresh tokens, save session"""

        # Create access token
        access_token, access_expires, jti = JWTUtils.create_access_token(
            user_id=user.id,
            tenant_id=tenant.id,
            email=user.email,
            role=user.role.value
        )

        # Create refresh token
        refresh_token, refresh_expires = JWTUtils.create_refresh_token(user.id)

        # Save session
        session = UserSession(
            user_id=user.id,
            refresh_token_hash=JWTUtils.hash_refresh_token(refresh_token),
            access_token_jti=jti,
            device_info=user_agent,
            ip_address=ip_address,
            expires_at=refresh_expires
        )
        self.db.add(session)

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=access_expires,
            refresh_expires_at=refresh_expires
        )

    def _validate_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def _generate_tenant_slug(self, name: str) -> str:
        """Generate unique tenant slug from name"""
        import re

        # Convert to lowercase and replace spaces with hyphens
        slug = name.lower().strip()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = slug.strip('-')

        # Ensure uniqueness
        base_slug = slug
        counter = 1

        while self.db.query(Tenant).filter(Tenant.slug == slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    def _create_tenant_directory(self, tenant: Tenant):
        """Create data directory for tenant"""
        from pathlib import Path

        if tenant.data_directory:
            path = Path(tenant.data_directory)
            path.mkdir(parents=True, exist_ok=True)

            # Create subdirectories
            (path / "documents").mkdir(exist_ok=True)
            (path / "embeddings").mkdir(exist_ok=True)
            (path / "videos").mkdir(exist_ok=True)
            (path / "audio").mkdir(exist_ok=True)

    # ========================================================================
    # PASSWORD RESET
    # ========================================================================

    def request_password_reset(
        self,
        email: str,
        ip_address: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Request a password reset.

        Returns (success, reset_token or error).
        Token is logged to console for testing.
        """
        try:
            # Find user by email (case insensitive)
            user = self.db.query(User).filter(
                User.email.ilike(email),
                User.is_active == True
            ).first()

            if not user:
                # Don't reveal if user exists - just log and return success
                print(f"[Auth] Password reset requested for non-existent email: {email}", flush=True)
                return True, None

            # Check if tenant is active
            if not user.tenant.is_active:
                print(f"[Auth] Password reset blocked - tenant inactive: {user.tenant_id}", flush=True)
                return True, None

            # Invalidate any existing reset tokens for this user
            self.db.query(PasswordResetToken).filter(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used == False
            ).update({"used": True, "used_at": utc_now()})

            # Generate new token
            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

            # Create reset token (expires in 1 hour)
            expires_at = utc_now() + timedelta(hours=1)
            reset_token = PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
                ip_address=ip_address
            )
            self.db.add(reset_token)

            self._log_action(
                tenant_id=user.tenant_id,
                user_id=user.id,
                action="user.password_reset_requested",
                resource_type="user",
                resource_id=user.id,
                ip_address=ip_address
            )

            self.db.commit()

            # Build reset URL
            reset_url = f"{FRONTEND_URL}/reset-password?token={raw_token}"

            # Build email content - Clean white/blue design like Catalyst
            html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f5f5f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f5f5f0;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                    <!-- Logo -->
                    <tr>
                        <td align="center" style="padding: 40px 40px 20px 40px;">
                            <span style="font-size: 28px; font-weight: 700; color: #1a1a1a; background-color: #fef3c7; padding: 4px 12px; border-radius: 4px;">2nd Brain</span>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 20px 40px 40px 40px;">
                            <h1 style="margin: 0 0 24px 0; font-size: 24px; font-weight: 700; color: #1a1a1a;">Reset Your Password</h1>

                            <p style="margin: 0 0 16px 0; font-size: 16px; color: #4b5563; line-height: 1.6;">Hi {user.full_name},</p>

                            <p style="margin: 0 0 32px 0; font-size: 16px; color: #4b5563; line-height: 1.6;">We received a request to reset your password for your <span style="background-color: #fef3c7; padding: 2px 6px; border-radius: 3px; font-weight: 500;">2nd Brain</span> account. Click the button below to create a new password:</p>

                            <!-- Button -->
                            <table role="presentation" cellspacing="0" cellpadding="0" style="margin: 0 auto 32px auto;">
                                <tr>
                                    <td align="center" style="background-color: #2563eb; border-radius: 8px;">
                                        <a href="{reset_url}" target="_blank" style="display: inline-block; padding: 16px 32px; font-size: 16px; font-weight: 600; color: #ffffff; text-decoration: none;">Reset Password</a>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0 0 16px 0; font-size: 14px; color: #6b7280; line-height: 1.6;">This link will expire in 1 hour for security reasons.</p>

                            <p style="margin: 0 0 32px 0; font-size: 14px; color: #6b7280; line-height: 1.6;">If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.</p>

                            <!-- Divider -->
                            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 32px 0;">

                            <!-- Footer -->
                            <p style="margin: 0 0 8px 0; font-size: 13px; color: #9ca3af; text-align: center;">
                                <span style="background-color: #fef3c7; padding: 2px 6px; border-radius: 3px; font-weight: 500; color: #1a1a1a;">2nd Brain</span> - Enterprise Knowledge Transfer Platform
                            </p>
                            <p style="margin: 0; font-size: 12px; color: #9ca3af; text-align: center; line-height: 1.6;">
                                If you're having trouble clicking the button, copy and paste this URL into your browser:<br>
                                <a href="{reset_url}" style="color: #2563eb; word-break: break-all;">{reset_url}</a>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

            text_body = f"""
2nd Brain Password Reset

Hi {user.full_name},

We received a request to reset your password. Click the link below to choose a new password:

{reset_url}

This link will expire in 1 hour.

If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.

- The 2nd Brain Team
"""

            # Try to send actual email
            email_sent = self._send_email(
                to_email=user.email,
                subject="Reset your 2nd Brain password",
                html_body=html_body,
                text_body=text_body
            )

            # Always log to console for debugging/testing
            print(f"\n{'='*60}", flush=True)
            print(f"PASSWORD RESET TOKEN FOR: {email}", flush=True)
            print(f"Token: {raw_token}", flush=True)
            print(f"Expires: {expires_at.isoformat()}", flush=True)
            print(f"Reset URL: {reset_url}", flush=True)
            if email_sent:
                print(f"Status: EMAIL SENT SUCCESSFULLY", flush=True)
            else:
                print(f"Status: Email not sent (SMTP not configured - check console above)", flush=True)
            print(f"{'='*60}\n", flush=True)

            return True, raw_token

        except Exception as e:
            self.db.rollback()
            print(f"[Auth] Password reset error: {e}", flush=True)
            return False, str(e)

    def verify_reset_token(self, token: str) -> bool:
        """Verify if a password reset token is valid."""
        try:
            token_hash = hashlib.sha256(token.encode()).hexdigest()

            reset_token = self.db.query(PasswordResetToken).filter(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used == False,
                PasswordResetToken.expires_at > utc_now()
            ).first()

            return reset_token is not None

        except Exception:
            return False

    def reset_password(
        self,
        token: str,
        new_password: str,
        ip_address: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Reset password using reset token.

        Returns (success, error_message).
        """
        try:
            # Validate new password
            is_valid, errors = PasswordUtils.validate_password_strength(new_password)
            if not is_valid:
                return False, f"Password does not meet requirements: {', '.join(errors)}"

            # Find token
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            reset_token = self.db.query(PasswordResetToken).filter(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used == False
            ).first()

            if not reset_token:
                return False, "Invalid or expired reset token"

            if reset_token.expires_at < utc_now():
                return False, "Reset token has expired"

            # Get user
            user = self.db.query(User).filter(User.id == reset_token.user_id).first()
            if not user or not user.is_active:
                return False, "User not found or inactive"

            # Update password
            user.password_hash = PasswordUtils.hash_password(new_password)
            user.failed_login_attempts = 0
            user.locked_until = None

            # Mark token as used
            reset_token.used = True
            reset_token.used_at = utc_now()

            # Revoke all existing sessions (logout everywhere)
            self.db.query(UserSession).filter(
                UserSession.user_id == user.id,
                UserSession.is_revoked == False
            ).update({
                "is_revoked": True,
                "revoked_at": utc_now(),
                "revoked_reason": "password_reset"
            })

            self._log_action(
                tenant_id=user.tenant_id,
                user_id=user.id,
                action="user.password_reset_completed",
                resource_type="user",
                resource_id=user.id,
                ip_address=ip_address
            )

            self.db.commit()

            print(f"[Auth] Password reset successful for user: {user.email}", flush=True)
            return True, None

        except Exception as e:
            self.db.rollback()
            return False, str(e)

    # ========================================================================
    # EMAIL VERIFICATION
    # ========================================================================

    def _send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str
    ) -> bool:
        """
        Send email via SMTP using configured Gmail account.
        Returns True if sent successfully, False otherwise.
        """
        if not SMTP_USER or not SMTP_PASSWORD:
            print(f"[Auth] Email not configured (missing SMTP_USER/PASSWORD or FORWARD_EMAIL credentials)")
            print(f"[Auth] Set SMTP_USER and SMTP_PASSWORD, or FORWARD_EMAIL_ADDRESS and FORWARD_EMAIL_PASSWORD")
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
            msg['To'] = to_email

            # Attach parts
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)

            # Connect and send
            print(f"[Auth] Connecting to SMTP {SMTP_HOST}:{SMTP_PORT}...")
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()

            print(f"[Auth] Email sent successfully to {to_email}: {subject}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            print(f"[Auth] SMTP authentication failed: {e}")
            print(f"[Auth] Check your Gmail app password at https://myaccount.google.com/apppasswords")
            return False
        except Exception as e:
            print(f"[Auth] Failed to send email to {to_email}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def send_verification_email(
        self,
        user: User,
        ip_address: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Send email verification link.

        Returns (success, token or error).
        Sends actual email if SMTP is configured, otherwise logs to console.
        """
        try:
            # Invalidate any existing verification tokens for this user
            self.db.query(EmailVerificationToken).filter(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.used == False
            ).update({"used": True, "used_at": utc_now()})

            # Generate new token
            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

            # Create verification token (expires in 24 hours)
            expires_at = utc_now() + timedelta(hours=24)
            verification_token = EmailVerificationToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
                ip_address=ip_address
            )
            self.db.add(verification_token)

            self._log_action(
                tenant_id=user.tenant_id,
                user_id=user.id,
                action="user.verification_email_sent",
                resource_type="user",
                resource_id=user.id,
                ip_address=ip_address
            )

            self.db.commit()

            # Build verification URL
            verification_url = f"{FRONTEND_URL}/verify-email?token={raw_token}"

            # Build email content - Clean white/blue design like Catalyst
            html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f5f5f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f5f5f0;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                    <!-- Logo -->
                    <tr>
                        <td align="center" style="padding: 40px 40px 20px 40px;">
                            <span style="font-size: 28px; font-weight: 700; color: #1a1a1a; background-color: #fef3c7; padding: 4px 12px; border-radius: 4px;">2nd Brain</span>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 20px 40px 40px 40px;">
                            <h1 style="margin: 0 0 24px 0; font-size: 24px; font-weight: 700; color: #1a1a1a;">Verify Your Email</h1>

                            <p style="margin: 0 0 16px 0; font-size: 16px; color: #4b5563; line-height: 1.6;">Hi {user.full_name},</p>

                            <p style="margin: 0 0 32px 0; font-size: 16px; color: #4b5563; line-height: 1.6;">Thanks for signing up for <span style="background-color: #fef3c7; padding: 2px 6px; border-radius: 3px; font-weight: 500;">2nd Brain</span>. Click the button below to verify your email address:</p>

                            <!-- Button -->
                            <table role="presentation" cellspacing="0" cellpadding="0" style="margin: 0 auto 32px auto;">
                                <tr>
                                    <td align="center" style="background-color: #2563eb; border-radius: 8px;">
                                        <a href="{verification_url}" target="_blank" style="display: inline-block; padding: 16px 32px; font-size: 16px; font-weight: 600; color: #ffffff; text-decoration: none;">Verify Email</a>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0 0 16px 0; font-size: 14px; color: #6b7280; line-height: 1.6;">This link will expire in 24 hours for security reasons.</p>

                            <p style="margin: 0 0 32px 0; font-size: 14px; color: #6b7280; line-height: 1.6;">If you didn't create an account, you can safely ignore this email.</p>

                            <!-- Divider -->
                            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 32px 0;">

                            <!-- Footer -->
                            <p style="margin: 0 0 8px 0; font-size: 13px; color: #9ca3af; text-align: center;">
                                <span style="background-color: #fef3c7; padding: 2px 6px; border-radius: 3px; font-weight: 500; color: #1a1a1a;">2nd Brain</span> - Enterprise Knowledge Transfer Platform
                            </p>
                            <p style="margin: 0; font-size: 12px; color: #9ca3af; text-align: center; line-height: 1.6;">
                                If you're having trouble clicking the button, copy and paste this URL into your browser:<br>
                                <a href="{verification_url}" style="color: #2563eb; word-break: break-all;">{verification_url}</a>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

            text_body = f"""
Welcome to 2nd Brain!

Hi {user.full_name},

Thanks for signing up for 2nd Brain! Please verify your email address to get started.

Click this link to verify your email:
{verification_url}

This link will expire in 24 hours.

If you didn't create an account, you can safely ignore this email.

- The 2nd Brain Team
"""

            # Try to send actual email
            email_sent = self._send_email(
                to_email=user.email,
                subject="Verify your 2nd Brain email address",
                html_body=html_body,
                text_body=text_body
            )

            # Always log to console for debugging/testing
            print(f"\n{'='*60}", flush=True)
            print(f"EMAIL VERIFICATION TOKEN FOR: {user.email}", flush=True)
            print(f"Token: {raw_token}", flush=True)
            print(f"Expires: {expires_at.isoformat()}", flush=True)
            print(f"Verification URL: {verification_url}", flush=True)
            if email_sent:
                print(f"Status: EMAIL SENT SUCCESSFULLY", flush=True)
            else:
                print(f"Status: Email not sent (SMTP not configured - check console above)", flush=True)
            print(f"{'='*60}\n", flush=True)

            return True, raw_token

        except Exception as e:
            self.db.rollback()
            print(f"[Auth] Send verification email error: {e}", flush=True)
            return False, str(e)

    def verify_email(
        self,
        token: str,
        ip_address: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[User]]:
        """
        Verify email using verification token.

        Returns (success, error_message, user).
        """
        try:
            # Find token
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            verification_token = self.db.query(EmailVerificationToken).filter(
                EmailVerificationToken.token_hash == token_hash,
                EmailVerificationToken.used == False
            ).first()

            if not verification_token:
                return False, "Invalid or expired verification token", None

            # Handle timezone-naive datetime from SQLite
            expires_at = verification_token.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < utc_now():
                return False, "Verification token has expired. Please request a new one.", None

            # Get user
            user = self.db.query(User).filter(User.id == verification_token.user_id).first()
            if not user:
                return False, "User not found", None

            if user.email_verified:
                return False, "Email is already verified", user

            # Mark email as verified
            user.email_verified = True
            user.updated_at = utc_now()

            # Mark token as used
            verification_token.used = True
            verification_token.used_at = utc_now()

            self._log_action(
                tenant_id=user.tenant_id,
                user_id=user.id,
                action="user.email_verified",
                resource_type="user",
                resource_id=user.id,
                ip_address=ip_address
            )

            self.db.commit()

            print(f"[Auth] Email verified for user: {user.email}", flush=True)
            return True, None, user

        except Exception as e:
            self.db.rollback()
            return False, str(e), None

    def resend_verification_email(
        self,
        email: str,
        ip_address: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Resend verification email.

        Returns (success, error_message).
        """
        try:
            # Find user by email
            user = self.db.query(User).filter(
                User.email.ilike(email),
                User.is_active == True
            ).first()

            if not user:
                # Don't reveal if user exists
                print(f"[Auth] Resend verification requested for non-existent email: {email}", flush=True)
                return True, None

            if user.email_verified:
                return False, "Email is already verified"

            # Send new verification email
            success, result = self.send_verification_email(user, ip_address)
            return success, None if success else result

        except Exception as e:
            self.db.rollback()
            return False, str(e)

    def check_email_verified(self, user_id: str) -> bool:
        """Check if user's email is verified."""
        user = self.db.query(User).filter(User.id == user_id).first()
        return user.email_verified if user else False

    def _log_action(
        self,
        action: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log an audit action"""
        log = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
        self.db.add(log)


# ============================================================================
# HELPER FUNCTIONS (for Flask integration)
# ============================================================================

def get_token_from_header(authorization_header: str) -> Optional[str]:
    """Extract token from Authorization header"""
    if not authorization_header:
        return None

    parts = authorization_header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]

    return None


def require_auth(f):
    """Decorator for requiring authentication (JWT or share token)"""
    from functools import wraps
    from flask import request, jsonify, g

    @wraps(f)
    def decorated(*args, **kwargs):
        # Try JWT first
        token = get_token_from_header(request.headers.get("Authorization", ""))

        if token:
            payload, error = JWTUtils.decode_access_token(token)
            if error:
                return jsonify({"error": error}), 401

            # Store user info in Flask g object
            g.user_id = payload.get("sub")
            g.tenant_id = payload.get("tenant_id")
            g.email = payload.get("email")
            g.role = payload.get("role")
            g.is_shared_access = False

            return f(*args, **kwargs)

        # Fallback: try share token
        share_token = request.headers.get('X-Share-Token')
        if share_token:
            import hashlib
            from database.models import SessionLocal, TenantShareLink, Tenant, utc_now as _utc_now

            token_hash = hashlib.sha256(share_token.encode()).hexdigest()
            db = SessionLocal()
            try:
                link = db.query(TenantShareLink).filter(
                    TenantShareLink.token_hash == token_hash,
                    TenantShareLink.is_active == True
                ).first()

                if not link or not link.is_valid:
                    return jsonify({"error": "Invalid or expired share link"}), 401

                tenant = db.query(Tenant).filter(Tenant.id == link.tenant_id).first()
                if not tenant or not tenant.is_active:
                    return jsonify({"error": "Organization is inactive"}), 403

                g.user_id = f"shared-{link.id[:8]}"
                g.tenant_id = link.tenant_id
                g.email = "shared@portal"
                g.role = "viewer"
                g.is_shared_access = True
                g.share_permissions = link.permissions or {}

                # Track access
                link.access_count = (link.access_count or 0) + 1
                link.last_accessed_at = _utc_now()
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

            return f(*args, **kwargs)

        return jsonify({"error": "Missing authorization token"}), 401

    return decorated


def require_role(*allowed_roles):
    """Decorator for requiring specific roles"""
    from functools import wraps
    from flask import g, jsonify

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, 'role') or g.role not in allowed_roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def require_verified_email(f):
    """
    Decorator for requiring email verification.
    Must be used after @require_auth decorator.
    """
    from functools import wraps
    from flask import g, jsonify

    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(g, 'user_id'):
            return jsonify({"error": "Authentication required"}), 401

        # Check if email is verified
        from database.models import SessionLocal, User
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == g.user_id).first()
            if not user:
                return jsonify({"error": "User not found"}), 404

            if not user.email_verified:
                return jsonify({
                    "error": "Email verification required",
                    "error_code": "EMAIL_NOT_VERIFIED",
                    "message": "Please verify your email address to access this feature."
                }), 403
        finally:
            db.close()

        return f(*args, **kwargs)

    return decorated
