"""
OAuth 2.0 + JWT Authentication System
Supports Google & GitHub OAuth with JWT token management
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import HTTPException, status, Depends, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext

from config import config

# JWT Configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Bearer token extraction (allow cookie fallback)
security = HTTPBearer(auto_error=False)


def _get_token_from_request(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials]
) -> Optional[str]:
    """Extract JWT from Authorization header or httpOnly cookie."""
    if credentials and credentials.credentials:
        return credentials.credentials
    return request.cookies.get("access_token")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, config.JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, config.JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> dict:
    """Verify JWT token and return payload."""
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )


def _set_token_cookie(response: Response, key: str, value: str, max_age: int) -> None:
    response.set_cookie(
        key=key,
        value=value,
        httponly=True,
        secure=config.ENVIRONMENT == "production",  # HTTPS-only cookies in production
        samesite="lax",
        max_age=max_age
    )


def set_auth_cookies(response: Response, token_data: dict) -> None:
    """Issue a fresh access + refresh token pair as httpOnly cookies."""
    _set_token_cookie(response, "access_token", create_access_token(token_data), ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    _set_token_cookie(response, "refresh_token", create_refresh_token(token_data), REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60)


def _token_payload(token: Optional[str], token_type: str) -> Optional[dict]:
    """Decode a token, returning None instead of raising if it is missing or invalid."""
    if not token:
        return None
    try:
        return verify_token(token, token_type)
    except HTTPException:
        return None


async def renew_expired_session(request: Request, call_next):
    """HTTP middleware: when the access token has expired but the refresh token is
    still valid, issue a new access token for this request and the browser.

    The pages never call /auth/token/refresh themselves, so without this a session
    would end when the access token expires, even in the middle of a chat.
    """
    if request.url.path.startswith("/static") or _token_payload(request.cookies.get("access_token"), "access"):
        return await call_next(request)

    refresh = _token_payload(request.cookies.get("refresh_token"), "refresh")
    if not refresh:
        return await call_next(request)

    new_access = create_access_token(
        {"sub": refresh["sub"], "email": refresh.get("email"), "name": refresh.get("name")}
    )

    # Swap the new token into this request so get_current_user accepts it
    cookies = {**request.cookies, "access_token": new_access}
    headers = [(k, v) for k, v in request.scope["headers"] if k != b"cookie"]
    headers.append((b"cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()).encode("latin-1")))
    request.scope["headers"] = headers

    response = await call_next(request)

    # A route that set or cleared the access cookie itself (login, OAuth callback, logout) wins
    if not any(c.startswith("access_token=") for c in response.headers.getlist("set-cookie")):
        _set_token_cookie(response, "access_token", new_access, ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    return response


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """Dependency to get current authenticated user from JWT or cookie."""
    token = _get_token_from_request(request, credentials)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token"
        )
    payload = verify_token(token, "access")
    return payload


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# OAuth 2.0 Configuration
OAUTH_CONFIG = {
    "google": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scopes": ["openid", "email", "profile"],
    },
    "github": {
        "client_id": os.getenv("GITHUB_CLIENT_ID", ""),
        "client_secret": os.getenv("GITHUB_CLIENT_SECRET", ""),
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scopes": ["user:email"],
    }
}
