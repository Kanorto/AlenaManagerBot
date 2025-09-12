"""
Security helpers for password hashing and JWT authentication.

This module implements a lightweight JSON Web Token (JWT) mechanism
using HMAC‑SHA256 signatures and base64url encoding.  Tokens embed
arbitrary claims and an expiration timestamp (``exp``).  A secret
key from the application settings is used to sign and verify the
token.  Additionally, helper functions are provided for hashing
passwords using PBKDF2‑HMAC with SHA‑256, along with salt generation
and verification.  These primitives avoid third‑party dependencies
while delivering sufficient security for an MVP.  For production
systems you may replace them with an industry‑standard library such
as `python‑jose` for JWT and `passlib` or `bcrypt` for password
hashing.
"""

import base64
import json
import time
import hmac
import hashlib
import os
from typing import Optional, Dict

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import Iterable, Callable

from .config import settings


def _b64_url_encode(data: bytes) -> str:
    """Base64‑url encode bytes without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64_url_decode(data: str) -> bytes:
    """Decode base64‑url encoded string, adding padding if necessary."""
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(message: bytes, secret: str) -> bytes:
    """Compute HMAC‑SHA256 signature of a message using the given secret."""
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()


def create_access_token(data: Dict[str, str], expires_delta: Optional[int] = None) -> str:
    """Create a signed JWT token with the given payload.

    The payload is extended with an ``exp`` field representing the
    expiration time as a UNIX timestamp.  A standard header with
    algorithm HS256 is used.  The token is a string of the form
    ``header.payload.signature``, where each part is base64url
    encoded.  Clients must include this token in the ``Authorization``
    header as ``Bearer <token>``.

    Parameters
    ----------
    data : dict
        Claims to embed in the token (e.g. {"sub": "user@example.com"}).
    expires_delta : Optional[int]
        Lifetime of the token in seconds.  Defaults to
        ``settings.access_token_expire_minutes * 60``.

    Returns
    -------
    str
        A signed JWT token.
    """
    to_encode = data.copy()
    exp_seconds = expires_delta or settings.access_token_expire_minutes * 60
    to_encode["exp"] = int(time.time()) + exp_seconds
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64_url_encode(json.dumps(header, separators=(',', ':')).encode("utf-8"))
    payload_b64 = _b64_url_encode(json.dumps(to_encode, separators=(',', ':')).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = _sign(signing_input, settings.secret_key)
    signature_b64 = _b64_url_encode(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_access_token(token: str) -> Optional[Dict[str, str]]:
    """Verify and decode a JWT token.

    Splits the token into header, payload and signature, verifies the
    HMAC signature and checks the ``exp`` field.  If validation
    succeeds, returns the payload dictionary; otherwise returns
    ``None``.

    Parameters
    ----------
    token : str
        JWT token string (``header.payload.signature``).

    Returns
    -------
    Optional[dict]
        The decoded payload if valid, else ``None``.
    """
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        header_b64, payload_b64, signature_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = _sign(signing_input, settings.secret_key)
        actual_sig = _b64_url_decode(signature_b64)
        # Constant‑time comparison to prevent timing attacks
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload_json = _b64_url_decode(payload_b64)
        data = json.loads(payload_json.decode("utf-8"))
        if data.get("exp") is None or int(data["exp"]) < int(time.time()):
            return None
        return data
    except Exception:
        return None


security = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, str]:
    """Dependency that retrieves the current authenticated user.

    If the request does not contain an ``Authorization`` header or the
    token is invalid/expired, an HTTP 401 error is raised.  On
    success, returns the decoded token payload.  In a real
    application you would map the token subject (``sub``) to a
    database record and return a user model.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials

    # Check if token matches any of the trusted bot tokens.  The BOT_TOKENS
    # environment variable may contain multiple comma‑separated tokens.  When
    # presented, these tokens authenticate the request as coming from a bot
    # or external service.  The role assigned is taken from
    # settings.bot_role_id, and user_id is left unspecified.  This allows
    # bots to interact with the API without a user account while still
    # respecting RBAC.
    if settings.bot_tokens:
        tokens_list = [t.strip() for t in settings.bot_tokens.split(',') if t.strip()]
        if token in tokens_list:
            return {
                "sub": "bot",
                "user_id": None,
                "role_id": settings.bot_role_id,
            }

    # Support for a static super administrator token defined via SUPER_ADMIN_TOKEN.
    # If present and matches the provided token, bypass JWT decoding and return
    # a user context with super_admin privileges.  The default user_id is 1 (the
    # first created super admin).  This mechanism allows integrations to
    # authenticate via a single long‑lived token instead of per‑user logins.
    if settings.super_admin_static_token and token == settings.super_admin_static_token:
        return {
            "sub": "static_super_admin",
            "user_id": 1,
            "role_id": 1,
        }
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Lookup user details (e.g., role) from the database.  If the
    # subject no longer exists (e.g., user was deleted), raise 401.
    try:
        from event_planner_api.app.core.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        user_row = cursor.execute(
            "SELECT id, role_id, disabled FROM users WHERE email = ?",
            (payload.get("sub"),),
        ).fetchone()
        if not user_row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User no longer exists",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if user_row["disabled"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account disabled",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Attach user_id and role_id to the token payload for convenience
        payload["user_id"] = user_row["id"]
        payload["role_id"] = user_row["role_id"]
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return payload


# ---------------------------------------------------------------------------
# Role-based access control (RBAC) helpers
# ---------------------------------------------------------------------------

def require_roles(*role_ids: int) -> Callable[[Dict[str, str]], Dict[str, str]]:
    """Dependency factory to enforce that the current user has one of the specified roles.

    Use this in FastAPI endpoints via ``Depends(require_roles(1, 2))`` to allow only
    super_admin (1) and admin (2) to access a route.  Role IDs correspond to
    entries in the ``roles`` table created during database migrations.  If the
    authenticated user does not match any of the given role IDs, an HTTP 403
    error is raised.

    Parameters
    ----------
    *role_ids : int
        One or more role identifiers permitted to access the endpoint.

    Returns
    -------
    Callable
        A dependency function that validates the current user's role and
        returns the user payload on success.
    """

    def _role_dependency(current_user: Dict[str, str] = Depends(get_current_user)) -> Dict[str, str]:
        if current_user.get("role_id") not in role_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _role_dependency



def hash_password(password: str) -> str:
    """Hash a password using PBKDF2‑HMAC with SHA‑256.

    A 16‑byte random salt is generated for each password.  The
    resulting string contains the salt and hash separated by a
    ``$`` (salt in hex, then hash in hex).  This format allows
    verifying the password later.  Increase the iterations for
    stronger security at the cost of performance.

    Parameters
    ----------
    password : str
        The plain text password to hash.

    Returns
    -------
    str
        Salt and hash concatenated with ``$``.
    """
    salt = os.urandom(16)
    iterations = 100_000
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    return f"{salt.hex()}${dk.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a stored salt+hash string.

    Splits the stored string into salt and hash, recomputes the
    PBKDF2‑HMAC digest and compares it using constant‑time comparison.

    Parameters
    ----------
    plain_password : str
        The password provided by the user.
    hashed_password : str
        The stored salt and hash separated by ``$``.

    Returns
    -------
    bool
        True if the password matches, otherwise False.
    """
    try:
        salt_hex, hash_hex = hashed_password.split('$', 1)
        salt = bytes.fromhex(salt_hex)
        stored_hash = bytes.fromhex(hash_hex)
        iterations = 100_000
        dk = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt, iterations)
        return hmac.compare_digest(dk, stored_hash)
    except Exception:
        return False