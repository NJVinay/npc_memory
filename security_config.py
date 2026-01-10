"""
Security Configuration for F1 Car Builder
Centralized security settings and validation rules
"""

import os
from typing import Dict, List

# Rate limiting configuration
RATE_LIMITS: Dict[str, str] = {
    "chat_api": "30/minute",  # Groq free tier limit
    "login": "5/minute",  # Prevent brute force
    "register": "3/minute",  # Prevent spam
    "general": "100/minute"  # General API rate limit
}

# Password policy
PASSWORD_MIN_LENGTH = 8
PASSWORD_REQUIRE_LETTER = True
PASSWORD_REQUIRE_NUMBER = True
PASSWORD_REQUIRE_SPECIAL = False  # Optional for now

# Email validation
EMAIL_MAX_LENGTH = 255
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

# Session security
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
ROTATE_REFRESH_TOKENS = True

# HTTPS enforcement (production only)
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development") == "production"
ENFORCE_HTTPS = IS_PRODUCTION
SECURE_COOKIES = IS_PRODUCTION

# CORS settings
def get_allowed_origins() -> List[str]:
    """Get allowed CORS origins from environment."""
    origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
    return [origin.strip() for origin in origins_str.split(",")]

# Security headers
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains" if IS_PRODUCTION else None,
}

# Request validation
MAX_REQUEST_SIZE = 1024 * 1024  # 1MB
MAX_DIALOGUE_LENGTH = 500  # characters
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB for future file uploads
