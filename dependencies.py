from fastapi import Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from config import config

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

def require_service_key(request: Request) -> None:
    """Dependency to require a service API key if enabled in config."""
    if not config.REQUIRE_SERVICE_API_KEY:
        return
        
    service_key = request.headers.get("x-service-key")
    if not service_key or service_key != config.SERVICE_API_KEY:
        raise HTTPException(
            status_code=401, 
            detail="Valid Service API Key required in x-service-key header"
        )

def is_email_allowed(email: str) -> bool:
    """Check if email or domain is allowed in config."""
    email_lower = email.lower()
    if config.ALLOWED_EMAILS and email_lower in config.ALLOWED_EMAILS:
        return True
    if config.ALLOWED_EMAIL_DOMAINS:
        domain = email_lower.split("@")[-1]
        return domain in config.ALLOWED_EMAIL_DOMAINS
    # If no restrictions, all are allowed
    return not (config.ALLOWED_EMAILS or config.ALLOWED_EMAIL_DOMAINS)
