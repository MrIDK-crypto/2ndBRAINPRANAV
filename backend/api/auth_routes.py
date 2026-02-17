"""
Authentication API Routes
REST endpoints for user authentication, registration, and session management.
"""

from flask import Blueprint, request, jsonify, g, make_response
from sqlalchemy.orm import Session

from database.models import SessionLocal, User, Tenant
from services.auth_service import (
    AuthService, SignupData,
    get_token_from_header, require_auth, JWTUtils
)
from services.validators import (
    validate_signup_data, validate_login_data,
    EmailValidator, PasswordValidator
)
from middleware.csrf import (
    get_csrf_token_endpoint,
    add_csrf_to_response,
    generate_csrf_token,
    CSRF_COOKIE_NAME
)


# Create blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


# Cookie configuration
ACCESS_TOKEN_COOKIE = "accessToken"
REFRESH_TOKEN_COOKIE = "refreshToken"
COOKIE_MAX_AGE_ACCESS = 15 * 60  # 15 minutes
COOKIE_MAX_AGE_REFRESH = 7 * 24 * 60 * 60  # 7 days


def is_secure_request():
    """Check if request is over HTTPS"""
    return request.is_secure or request.headers.get('X-Forwarded-Proto') == 'https'


def set_auth_cookies(response, access_token: str, refresh_token: str):
    """
    Set httpOnly cookies for authentication tokens.
    Also sets CSRF token cookie.
    """
    secure = is_secure_request()

    # Access token cookie (shorter lived)
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        access_token,
        httponly=True,
        secure=secure,
        samesite='Lax',
        max_age=COOKIE_MAX_AGE_ACCESS,
        path='/'
    )

    # Refresh token cookie (longer lived)
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        refresh_token,
        httponly=True,
        secure=secure,
        samesite='Lax',
        max_age=COOKIE_MAX_AGE_REFRESH,
        path='/'
    )

    # Set CSRF token
    csrf_token = generate_csrf_token()
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        httponly=False,  # Must be readable by JavaScript
        secure=secure,
        samesite='Lax',
        max_age=COOKIE_MAX_AGE_ACCESS,
        path='/'
    )

    return response


def clear_auth_cookies(response):
    """Clear all auth-related cookies"""
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path='/')
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path='/')
    response.delete_cookie(CSRF_COOKIE_NAME, path='/')
    return response


def get_refresh_token_from_request():
    """
    Get refresh token from multiple sources:
    1. Cookie (preferred)
    2. Authorization header
    3. Request body
    """
    # Check cookie first
    token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if token:
        return token

    # Check request body
    data = request.get_json(silent=True)
    if data and data.get('refresh_token'):
        return data['refresh_token']

    return None


def get_db():
    """Get database session"""
    return SessionLocal()


def get_client_info():
    """Get client IP and user agent from request"""
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    user_agent = request.headers.get('User-Agent', '')[:500]
    return ip, user_agent


# ============================================================================
# SIGNUP
# ============================================================================

@auth_bp.route('/signup', methods=['POST'])
def signup():
    """
    Register a new user and organization.

    Request body:
    {
        "email": "user@example.com",
        "password": "SecurePassword123",
        "full_name": "John Doe",
        "organization_name": "Acme Corp" (optional)
    }

    Response:
    {
        "success": true,
        "user": { ... },
        "tokens": {
            "access_token": "...",
            "refresh_token": "...",
            "token_type": "Bearer",
            "expires_in": 604800
        }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400

        # Validate required fields
        required_fields = ['email', 'password', 'full_name']
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return jsonify({
                "success": False,
                "error": f"Missing required fields: {', '.join(missing)}"
            }), 400

        # Validate signup data (email format, password strength, name)
        is_valid, error_msg = validate_signup_data(
            email=data['email'],
            password=data['password'],
            full_name=data['full_name']
        )

        if not is_valid:
            return jsonify({
                "success": False,
                "error": error_msg,
                "error_code": "VALIDATION_ERROR"
            }), 400

        # Normalize email
        normalized_email = EmailValidator.normalize(data['email'])

        ip, user_agent = get_client_info()

        db = get_db()
        try:
            auth_service = AuthService(db)

            signup_data = SignupData(
                email=normalized_email,
                password=data['password'],
                full_name=data['full_name'].strip(),
                organization_name=data.get('organization_name', '').strip() if data.get('organization_name') else None,
                invite_code=data.get('invite_code')
            )

            result = auth_service.signup(signup_data, ip, user_agent)

            if not result.success:
                return jsonify({
                    "success": False,
                    "error": result.error,
                    "error_code": result.error_code
                }), 400

            # Create response with tokens in body
            response_data = {
                "success": True,
                "user": result.user.to_dict(),
                "tenant": result.user.tenant.to_dict(),
                "tokens": {
                    "access_token": result.tokens.access_token,
                    "refresh_token": result.tokens.refresh_token,
                    "token_type": result.tokens.token_type,
                    "expires_in": 604800  # 7 days in seconds
                }
            }

            response = make_response(jsonify(response_data), 201)

            # Set httpOnly cookies
            response = set_auth_cookies(
                response,
                result.tokens.access_token,
                result.tokens.refresh_token
            )

            return response

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Signup failed: {str(e)}"
        }), 500


# ============================================================================
# LOGIN
# ============================================================================

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Authenticate user with email and password.

    Request body:
    {
        "email": "user@example.com",
        "password": "SecurePassword123"
    }

    Response:
    {
        "success": true,
        "user": { ... },
        "tokens": { ... }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400

        email = data.get('email', '').strip()
        password = data.get('password', '')

        # Validate login data
        is_valid, error_msg = validate_login_data(email, password)
        if not is_valid:
            return jsonify({
                "success": False,
                "error": error_msg
            }), 400

        # Normalize email
        normalized_email = EmailValidator.normalize(email)

        ip, user_agent = get_client_info()

        db = get_db()
        try:
            auth_service = AuthService(db)
            result = auth_service.login(normalized_email, password, ip, user_agent)

            if not result.success:
                status_code = 401
                if result.error_code == "ACCOUNT_LOCKED":
                    status_code = 423
                elif result.error_code == "TENANT_INACTIVE":
                    status_code = 403

                return jsonify({
                    "success": False,
                    "error": result.error,
                    "error_code": result.error_code
                }), status_code

            # Create response with tokens in body
            response_data = {
                "success": True,
                "user": result.user.to_dict(),
                "tenant": result.user.tenant.to_dict(),
                "tokens": {
                    "access_token": result.tokens.access_token,
                    "refresh_token": result.tokens.refresh_token,
                    "token_type": result.tokens.token_type,
                    "expires_in": 604800
                }
            }

            response = make_response(jsonify(response_data))

            # Set httpOnly cookies
            response = set_auth_cookies(
                response,
                result.tokens.access_token,
                result.tokens.refresh_token
            )

            return response

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Login failed: {str(e)}"
        }), 500


# ============================================================================
# REFRESH TOKEN
# ============================================================================

@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """
    Refresh access token using refresh token.

    Accepts refresh token from:
    1. Cookie (preferred)
    2. Request body: { "refresh_token": "..." }

    Response:
    {
        "success": true,
        "tokens": { ... }
    }
    """
    try:
        # Get refresh token from multiple sources
        token = get_refresh_token_from_request()

        if not token:
            return jsonify({
                "success": False,
                "error": "Refresh token is required"
            }), 400

        ip, user_agent = get_client_info()

        db = get_db()
        try:
            auth_service = AuthService(db)
            result = auth_service.refresh_tokens(
                token,
                ip,
                user_agent
            )

            if not result.success:
                # Clear cookies on refresh failure
                response = make_response(jsonify({
                    "success": False,
                    "error": result.error,
                    "error_code": result.error_code
                }), 401)
                response = clear_auth_cookies(response)
                return response

            # Create response with new tokens
            response_data = {
                "success": True,
                "tokens": {
                    "access_token": result.tokens.access_token,
                    "refresh_token": result.tokens.refresh_token,
                    "token_type": result.tokens.token_type,
                    "expires_in": 604800
                }
            }

            response = make_response(jsonify(response_data))

            # Set new httpOnly cookies
            response = set_auth_cookies(
                response,
                result.tokens.access_token,
                result.tokens.refresh_token
            )

            return response

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Token refresh failed: {str(e)}"
        }), 500


# ============================================================================
# LOGOUT
# ============================================================================

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    Logout current session.

    Accepts token from:
    1. Cookie (preferred)
    2. Authorization header

    Response:
    {
        "success": true
    }
    """
    try:
        # Try to get token from cookie first, then header
        token = request.cookies.get(ACCESS_TOKEN_COOKIE)
        if not token:
            token = get_token_from_header(request.headers.get("Authorization", ""))

        ip, _ = get_client_info()

        if token:
            db = get_db()
            try:
                auth_service = AuthService(db)
                auth_service.logout(token, ip)
            finally:
                db.close()

        # Always clear cookies on logout
        response = make_response(jsonify({"success": True}))
        response = clear_auth_cookies(response)
        return response

    except Exception:
        # Always clear cookies even on error
        response = make_response(jsonify({"success": True}))
        response = clear_auth_cookies(response)
        return response


@auth_bp.route('/logout-all', methods=['POST'])
@require_auth
def logout_all():
    """
    Logout all sessions except current one.

    Headers:
        Authorization: Bearer <access_token>

    Response:
    {
        "success": true,
        "sessions_revoked": 3
    }
    """
    try:
        token = get_token_from_header(request.headers.get("Authorization", ""))
        payload, _ = JWTUtils.decode_access_token(token)
        current_jti = payload.get("jti") if payload else None

        ip, _ = get_client_info()

        db = get_db()
        try:
            auth_service = AuthService(db)
            count = auth_service.logout_all_sessions(
                g.user_id,
                except_current_jti=current_jti,
                ip_address=ip
            )
            return jsonify({
                "success": True,
                "sessions_revoked": count
            })
        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# CURRENT USER
# ============================================================================

@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_current_user():
    """
    Get current authenticated user info.

    Headers:
        Authorization: Bearer <access_token>

    Response:
    {
        "success": true,
        "user": { ... },
        "tenant": { ... }
    }
    """
    try:
        db = get_db()
        try:
            user = db.query(User).filter(User.id == g.user_id).first()

            if not user:
                return jsonify({
                    "success": False,
                    "error": "User not found"
                }), 404

            return jsonify({
                "success": True,
                "user": user.to_dict(),
                "tenant": user.tenant.to_dict()
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# CHANGE PASSWORD
# ============================================================================

@auth_bp.route('/password', methods=['PUT'])
@require_auth
def change_password():
    """
    Change current user's password.

    Headers:
        Authorization: Bearer <access_token>

    Request body:
    {
        "current_password": "OldPassword123",
        "new_password": "NewPassword456",
        "logout_other_sessions": true (optional, default true)
    }

    Response:
    {
        "success": true
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400

        current_password = data.get('current_password')
        new_password = data.get('new_password')
        logout_others = data.get('logout_other_sessions', True)

        if not current_password or not new_password:
            return jsonify({
                "success": False,
                "error": "Current password and new password are required"
            }), 400

        ip, _ = get_client_info()

        db = get_db()
        try:
            auth_service = AuthService(db)
            success, error = auth_service.change_password(
                g.user_id,
                current_password,
                new_password,
                logout_others,
                ip
            )

            if not success:
                return jsonify({
                    "success": False,
                    "error": error
                }), 400

            return jsonify({"success": True})

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# UPDATE PROFILE
# ============================================================================

@auth_bp.route('/profile', methods=['PUT'])
@require_auth
def update_profile():
    """
    Update current user's profile.

    Headers:
        Authorization: Bearer <access_token>

    Request body:
    {
        "full_name": "John Doe",
        "timezone": "America/Los_Angeles",
        "preferences": { ... }
    }

    Response:
    {
        "success": true,
        "user": { ... }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400

        db = get_db()
        try:
            user = db.query(User).filter(User.id == g.user_id).first()

            if not user:
                return jsonify({
                    "success": False,
                    "error": "User not found"
                }), 404

            # Update allowed fields
            if 'full_name' in data:
                user.full_name = data['full_name']
            if 'timezone' in data:
                user.timezone = data['timezone']
            if 'preferences' in data and isinstance(data['preferences'], dict):
                user.preferences = {**user.preferences, **data['preferences']}

            db.commit()

            return jsonify({
                "success": True,
                "user": user.to_dict()
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# SESSIONS LIST
# ============================================================================

@auth_bp.route('/sessions', methods=['GET'])
@require_auth
def list_sessions():
    """
    List all active sessions for current user.

    Headers:
        Authorization: Bearer <access_token>

    Response:
    {
        "success": true,
        "sessions": [
            {
                "id": "...",
                "device_info": "...",
                "ip_address": "...",
                "created_at": "...",
                "last_used_at": "...",
                "is_current": true
            }
        ]
    }
    """
    try:
        from database.models import UserSession

        # Get current token JTI
        token = get_token_from_header(request.headers.get("Authorization", ""))
        payload, _ = JWTUtils.decode_access_token(token)
        current_jti = payload.get("jti") if payload else None

        db = get_db()
        try:
            sessions = db.query(UserSession).filter(
                UserSession.user_id == g.user_id,
                UserSession.is_revoked == False,
                UserSession.expires_at > db.func.now()
            ).order_by(UserSession.last_used_at.desc()).all()

            session_list = []
            for s in sessions:
                session_list.append({
                    "id": s.id,
                    "device_info": s.device_info,
                    "ip_address": s.ip_address,
                    "location": s.location,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "last_used_at": s.last_used_at.isoformat() if s.last_used_at else None,
                    "is_current": s.access_token_jti == current_jti
                })

            return jsonify({
                "success": True,
                "sessions": session_list
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@auth_bp.route('/sessions/<session_id>', methods=['DELETE'])
@require_auth
def revoke_session(session_id):
    """
    Revoke a specific session.

    Headers:
        Authorization: Bearer <access_token>

    Response:
    {
        "success": true
    }
    """
    try:
        from database.models import UserSession

        db = get_db()
        try:
            session = db.query(UserSession).filter(
                UserSession.id == session_id,
                UserSession.user_id == g.user_id
            ).first()

            if not session:
                return jsonify({
                    "success": False,
                    "error": "Session not found"
                }), 404

            session.is_revoked = True
            session.revoked_at = db.func.now()
            session.revoked_reason = "user_revoked"

            db.commit()

            return jsonify({"success": True})

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# CSRF TOKEN
# ============================================================================

@auth_bp.route('/csrf-token', methods=['GET'])
def csrf_token():
    """
    Get a new CSRF token.

    Response:
    {
        "success": true,
        "csrf_token": "..."
    }

    Also sets csrf_token cookie.
    """
    return get_csrf_token_endpoint()


# ============================================================================
# PASSWORD RESET
# ============================================================================

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """
    Request password reset email.

    Request body:
    {
        "email": "user@example.com"
    }

    Response:
    {
        "success": true,
        "message": "If an account exists, a reset link has been sent"
    }

    Note: Always returns success to prevent email enumeration.
    Reset token is logged to console for testing.
    """
    try:
        data = request.get_json()

        if not data or not data.get('email'):
            return jsonify({
                "success": False,
                "error": "Email is required"
            }), 400

        email = EmailValidator.normalize(data['email'])

        db = get_db()
        try:
            auth_service = AuthService(db)
            result = auth_service.request_password_reset(email)

            # Always return success to prevent email enumeration
            return jsonify({
                "success": True,
                "message": "If an account exists with this email, a password reset link has been sent."
            })

        finally:
            db.close()

    except Exception as e:
        # Still return success to prevent enumeration
        print(f"[Auth] Password reset error: {e}", flush=True)
        return jsonify({
            "success": True,
            "message": "If an account exists with this email, a password reset link has been sent."
        })


@auth_bp.route('/verify-reset-token', methods=['GET'])
def verify_reset_token():
    """
    Verify if a password reset token is valid.

    Query params:
        token: The reset token

    Response:
    {
        "success": true,
        "valid": true
    }
    """
    try:
        token = request.args.get('token')

        if not token:
            return jsonify({
                "success": False,
                "error": "Token is required"
            }), 400

        db = get_db()
        try:
            auth_service = AuthService(db)
            is_valid = auth_service.verify_reset_token(token)

            return jsonify({
                "success": True,
                "valid": is_valid
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """
    Reset password using reset token.

    Request body:
    {
        "token": "reset-token-here",
        "new_password": "NewSecurePassword123"
    }

    Response:
    {
        "success": true
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400

        token = data.get('token')
        new_password = data.get('new_password')

        if not token or not new_password:
            return jsonify({
                "success": False,
                "error": "Token and new password are required"
            }), 400

        # Validate new password
        is_valid, error = PasswordValidator.validate(new_password)
        if not is_valid:
            return jsonify({
                "success": False,
                "error": error,
                "error_code": "WEAK_PASSWORD"
            }), 400

        ip, _ = get_client_info()

        db = get_db()
        try:
            auth_service = AuthService(db)
            success, error = auth_service.reset_password(token, new_password, ip)

            if not success:
                return jsonify({
                    "success": False,
                    "error": error
                }), 400

            return jsonify({
                "success": True,
                "message": "Password has been reset successfully. Please log in with your new password."
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# EMAIL VERIFICATION
# ============================================================================

@auth_bp.route('/verify-email', methods=['GET'])
def verify_email():
    """
    Verify email using verification token.

    Query params:
        token: The verification token

    Response:
    {
        "success": true,
        "message": "Email verified successfully"
    }
    """
    try:
        token = request.args.get('token')

        if not token:
            return jsonify({
                "success": False,
                "error": "Verification token is required"
            }), 400

        ip, _ = get_client_info()

        db = get_db()
        try:
            auth_service = AuthService(db)
            success, error, user = auth_service.verify_email(token, ip)

            if not success:
                return jsonify({
                    "success": False,
                    "error": error
                }), 400

            return jsonify({
                "success": True,
                "message": "Email verified successfully. You can now access all features.",
                "user": user.to_dict() if user else None
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    """
    Resend verification email.

    Request body:
    {
        "email": "user@example.com"
    }

    Response:
    {
        "success": true,
        "message": "If an account exists, a verification email has been sent"
    }
    """
    try:
        data = request.get_json()

        if not data or not data.get('email'):
            return jsonify({
                "success": False,
                "error": "Email is required"
            }), 400

        email = EmailValidator.normalize(data['email'])
        ip, _ = get_client_info()

        db = get_db()
        try:
            auth_service = AuthService(db)
            success, error = auth_service.resend_verification_email(email, ip)

            if not success and error:
                return jsonify({
                    "success": False,
                    "error": error
                }), 400

            # Always return success to prevent email enumeration
            return jsonify({
                "success": True,
                "message": "If an account exists with this email, a verification link has been sent."
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@auth_bp.route('/verification-status', methods=['GET'])
@require_auth
def verification_status():
    """
    Check if current user's email is verified.

    Headers:
        Authorization: Bearer <access_token>

    Response:
    {
        "success": true,
        "email_verified": true
    }
    """
    try:
        db = get_db()
        try:
            auth_service = AuthService(db)
            is_verified = auth_service.check_email_verified(g.user_id)

            return jsonify({
                "success": True,
                "email_verified": is_verified
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# INVITE / SHARE (Team Invitations)
# ============================================================================

@auth_bp.route('/invite', methods=['POST'])
@require_auth
def send_invitation():
    """
    Send invitation email(s) to invite people to join your organization.
    Supports batch invites (multiple emails at once).

    Request body:
    {
        "emails": ["a@example.com", "b@example.com"],
        "email": "single@example.com",       // legacy single-email support
        "message": "Optional personal message"
    }

    Response:
    {
        "success": true,
        "sent": ["a@example.com", "b@example.com"],
        "failed": [{"email": "c@example.com", "reason": "Already a member"}]
    }
    """
    import os
    import secrets
    import hashlib
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from database.models import Invitation, InvitationStatus, utc_now

    # Only admins can invite
    if g.role and g.role != 'admin':
        return jsonify({"success": False, "error": "Only admins can send invitations"}), 403

    try:
        data = request.json or {}
        personal_message = data.get('message', '').strip()

        # Support both "emails" (array) and "email" (single string)
        raw_emails = data.get('emails', [])
        if not raw_emails and data.get('email'):
            raw_emails = [data['email']]
        if isinstance(raw_emails, str):
            # Handle comma-separated string
            raw_emails = [e.strip() for e in raw_emails.split(',') if e.strip()]

        # Deduplicate and normalize
        emails = list(dict.fromkeys([e.strip().lower() for e in raw_emails if e.strip()]))

        if not emails:
            return jsonify({"success": False, "error": "At least one email address is required"}), 400

        if len(emails) > 20:
            return jsonify({"success": False, "error": "Maximum 20 invitations at once"}), 400

        db = get_db()
        try:
            inviter = db.query(User).filter(User.id == g.user_id).first()
            if not inviter:
                return jsonify({"success": False, "error": "User not found"}), 404

            tenant = db.query(Tenant).filter(Tenant.id == g.tenant_id).first()
            if not tenant:
                return jsonify({"success": False, "error": "Organization not found"}), 404

            sender_name = inviter.full_name or inviter.email.split('@')[0]
            sender_email = inviter.email
            org_name = tenant.name

            # Email configuration
            SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
            SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
            SMTP_USER = os.getenv('SMTP_USER') or os.getenv('FORWARD_EMAIL_ADDRESS', '')
            SMTP_PASSWORD = os.getenv('SMTP_PASSWORD') or os.getenv('FORWARD_EMAIL_PASSWORD', '')
            _configured_from = os.getenv('SMTP_FROM_EMAIL') or SMTP_USER
            if 'gmail' in SMTP_HOST.lower() and SMTP_USER and _configured_from != SMTP_USER:
                SMTP_FROM_EMAIL = SMTP_USER
            else:
                SMTP_FROM_EMAIL = _configured_from
            FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3006')

            if not SMTP_USER or not SMTP_PASSWORD:
                return jsonify({"success": False, "error": "Email service not configured"}), 500

            sent = []
            failed = []

            for recipient_email in emails:
                # Validate email format
                is_valid, email_error = EmailValidator.validate(recipient_email)
                if not is_valid:
                    failed.append({"email": recipient_email, "reason": email_error or "Invalid email format"})
                    continue

                # Check if already a member
                existing_user = db.query(User).filter(
                    User.tenant_id == g.tenant_id,
                    User.email == recipient_email
                ).first()
                if existing_user:
                    failed.append({"email": recipient_email, "reason": "Already a member"})
                    continue

                # Check for existing pending invitation
                existing_invitation = db.query(Invitation).filter(
                    Invitation.tenant_id == g.tenant_id,
                    Invitation.recipient_email == recipient_email,
                    Invitation.status == InvitationStatus.PENDING
                ).first()
                if existing_invitation and existing_invitation.is_valid:
                    failed.append({"email": recipient_email, "reason": "Invitation already sent"})
                    continue

                # Check if email already has an account in another org
                existing_account = db.query(User).filter(
                    User.email == recipient_email,
                    User.is_active == True
                ).first()
                if existing_account:
                    failed.append({"email": recipient_email, "reason": "This email already has an account in another organization"})
                    continue

                # Generate token and create invitation (30 day expiry)
                from datetime import timedelta
                token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(token.encode()).hexdigest()

                # Set expiration to 30 days from now
                invitation_expires_at = utc_now() + timedelta(days=30)

                invitation = Invitation(
                    tenant_id=g.tenant_id,
                    inviter_id=g.user_id,
                    recipient_email=recipient_email,
                    token_hash=token_hash,
                    message=personal_message or None,
                    expires_at=invitation_expires_at
                )
                db.add(invitation)
                db.flush()

                # Build signup URL
                signup_url = f"{FRONTEND_URL}/signup?invite={token}"

                # Send email
                try:
                    msg = MIMEMultipart('alternative')
                    msg['Subject'] = f"{sender_name} invited you to join {org_name} on 2nd Brain"
                    msg['From'] = f"2nd Brain <{SMTP_FROM_EMAIL}>"
                    msg['To'] = recipient_email

                    personal_section = ""
                    if personal_message:
                        personal_section = f"""
                <div style="background-color: #F3F4F6; padding: 16px; border-radius: 8px; margin-bottom: 24px;">
                    <p style="font-style: italic; color: #374151; margin: 0;">&ldquo;{personal_message}&rdquo;</p>
                    <p style="color: #6B7280; margin: 8px 0 0 0; font-size: 14px;">&mdash; {sender_name}</p>
                </div>
                """

                    html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #F8FAFC;">
    <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
        <div style="background-color: #FFFFFF; border-radius: 16px; padding: 40px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
            <div style="text-align: center; margin-bottom: 32px;">
                <h1 style="font-size: 28px; font-weight: 700; color: #111827; margin: 0;">2nd Brain</h1>
                <p style="color: #6B7280; margin-top: 8px; font-size: 16px;">AI-Powered Knowledge Management</p>
            </div>
            <div style="text-align: center; margin-bottom: 32px;">
                <p style="font-size: 18px; color: #111827; margin: 0 0 16px 0;"><strong>{sender_name}</strong> has invited you to join</p>
                <p style="font-size: 24px; font-weight: 700; color: #2563EB; margin: 0;">{org_name}</p>
                <p style="color: #6B7280; margin-top: 8px; font-size: 14px;">on 2nd Brain</p>
            </div>
            {personal_section}
            <div style="margin-bottom: 32px;">
                <h2 style="font-size: 16px; color: #111827; margin-bottom: 16px;">By joining, you'll have access to:</h2>
                <ul style="color: #374151; padding-left: 20px; line-height: 1.8;">
                    <li><strong>Shared Knowledge Base</strong> - All documents, emails, and research</li>
                    <li><strong>AI-Powered Search</strong> - Find answers across your organization's knowledge</li>
                    <li><strong>Knowledge Gap Analysis</strong> - Discover what information is missing</li>
                    <li><strong>Integrations</strong> - Connect Gmail, Slack, Google Drive, and more</li>
                </ul>
            </div>
            <div style="text-align: center; margin-bottom: 32px;">
                <a href="{signup_url}" style="display: inline-block; background-color: #2563EB; color: #FFFFFF; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: 600; font-size: 16px;">Accept Invitation</a>
            </div>
            <div style="text-align: center; padding-top: 24px; border-top: 1px solid #E5E7EB;">
                <p style="color: #9CA3AF; font-size: 14px; margin: 0;">Questions? Reply to this email or contact {sender_email}</p>
            </div>
        </div>
    </div>
</body>
</html>"""

                    text_content = f"""{sender_name} has invited you to join {org_name} on 2nd Brain!

{f'"{personal_message}"' if personal_message else ''}

By joining, you'll have access to:
- Shared Knowledge Base - All documents, emails, and research
- AI-Powered Search - Find answers across your organization's knowledge
- Knowledge Gap Analysis - Discover what information is missing
- Integrations - Connect Gmail, Slack, Google Drive, and more

Accept your invitation: {signup_url}

Questions? Contact {sender_email}
"""

                    msg.attach(MIMEText(text_content, 'plain'))
                    msg.attach(MIMEText(html_content, 'html'))

                    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                        server.starttls()
                        server.login(SMTP_USER, SMTP_PASSWORD)
                        server.sendmail(SMTP_FROM_EMAIL, recipient_email, msg.as_string())

                    sent.append(recipient_email)
                    print(f"[Invite] Sent to {recipient_email} for tenant {org_name}")

                except smtplib.SMTPException as smtp_err:
                    print(f"[Invite] SMTP error for {recipient_email}: {smtp_err}")
                    failed.append({"email": recipient_email, "reason": "Failed to send email"})
                    continue

            db.commit()

            return jsonify({
                "success": len(sent) > 0,
                "sent": sent,
                "failed": failed,
                "message": f"Sent {len(sent)} invitation(s)" + (f", {len(failed)} failed" if failed else "")
            })

        finally:
            db.close()

    except Exception as e:
        print(f"[Invite] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@auth_bp.route('/invitations', methods=['GET'])
@require_auth
def list_invitations():
    """List all invitations for the current tenant (admin only)."""
    if g.role and g.role != 'admin':
        return jsonify({"success": False, "error": "Only admins can view invitations"}), 403

    from database.models import Invitation

    db = get_db()
    try:
        invitations = db.query(Invitation).filter(
            Invitation.tenant_id == g.tenant_id
        ).order_by(Invitation.created_at.desc()).all()

        return jsonify({
            "success": True,
            "invitations": [inv.to_dict() for inv in invitations]
        })
    finally:
        db.close()


@auth_bp.route('/invitations/<invitation_id>', methods=['DELETE'])
@require_auth
def revoke_invitation(invitation_id):
    """Revoke a pending invitation (admin only)."""
    if g.role and g.role != 'admin':
        return jsonify({"success": False, "error": "Only admins can revoke invitations"}), 403

    from database.models import Invitation, InvitationStatus, utc_now

    db = get_db()
    try:
        invitation = db.query(Invitation).filter(
            Invitation.id == invitation_id,
            Invitation.tenant_id == g.tenant_id
        ).first()

        if not invitation:
            return jsonify({"success": False, "error": "Invitation not found"}), 404

        if invitation.status != InvitationStatus.PENDING:
            return jsonify({"success": False, "error": f"Cannot revoke invitation with status: {invitation.status.value}"}), 400

        invitation.status = InvitationStatus.REVOKED
        db.commit()

        return jsonify({"success": True, "message": f"Invitation to {invitation.recipient_email} revoked"})
    finally:
        db.close()


@auth_bp.route('/invitation/<token>', methods=['GET'])
def get_invitation_info(token):
    """
    Get information about an invitation by token.
    Used by the frontend to show invitation details on signup page.

    Response:
    {
        "success": true,
        "invitation": {
            "recipient_email": "...",
            "inviter_name": "...",
            "organization_name": "...",
            "expires_at": "...",
            "is_valid": true
        }
    }
    """
    import hashlib
    from database.models import Invitation, InvitationStatus

    try:
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        db = get_db()
        try:
            invitation = db.query(Invitation).filter(
                Invitation.token_hash == token_hash
            ).first()

            if not invitation:
                return jsonify({
                    "success": False,
                    "error": "Invalid invitation link"
                }), 404

            # Get inviter and tenant info
            inviter = db.query(User).filter(User.id == invitation.inviter_id).first()
            tenant = db.query(Tenant).filter(Tenant.id == invitation.tenant_id).first()

            return jsonify({
                "success": True,
                "invitation": {
                    "recipient_email": invitation.recipient_email,
                    "recipient_name": invitation.recipient_name,
                    "inviter_name": inviter.full_name if inviter else "A team member",
                    "inviter_email": inviter.email if inviter else None,
                    "organization_name": tenant.name if tenant else "Unknown Organization",
                    "message": invitation.message,
                    "expires_at": invitation.expires_at.isoformat() if invitation.expires_at else None,
                    "is_valid": invitation.is_valid,
                    "status": invitation.status.value
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
