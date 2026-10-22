import hmac

from fastapi import Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from auth import _token_payload
from config import config
from services import StudyService

# Where pages send a logged-in player who hasn't given study consent yet
CONSENT_REQUIRED_URL = "/login?consent=required"
# ...and where a sign-in goes when the consent it carried couldn't be saved
CONSENT_INVALID_URL = "/login?consent=invalid"

# Page that serves each study condition
CONDITION_PAGES = {"dax": "/chat", "static": "/chat_static"}


def client_ip(request: Request) -> str:
    """Rate-limit key: the visitor's address as seen by the proxy in front of the app.

    Behind Render's proxy every connection comes from the proxy itself. The proxy
    appends the address it received the request from to X-Forwarded-For, so the
    right-most entry is the one a visitor can't fake. Without a proxy, use the
    connection's address.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[-1].strip()
    return get_remote_address(request)


def player_or_ip(request: Request) -> str:
    """Rate-limit key for per-player limits: the logged-in player, else the visitor's address."""
    payload = _token_payload(request.cookies.get("access_token"), "access")
    if payload and payload.get("sub"):
        return f"player:{payload['sub']}"
    return client_ip(request)


# Initialize rate limiter
limiter = Limiter(key_func=client_ip)


def _service_key_matches(request: Request) -> bool:
    service_key = request.headers.get("x-service-key") or ""
    # Compare bytes: compare_digest raises on non-ASCII str input
    return bool(config.SERVICE_API_KEY) and hmac.compare_digest(
        service_key.encode("utf-8"), config.SERVICE_API_KEY.encode("utf-8")
    )


def require_service_key(request: Request) -> None:
    """Dependency to require a service API key if enabled in config."""
    if not config.REQUIRE_SERVICE_API_KEY:
        return

    if not _service_key_matches(request):
        raise HTTPException(
            status_code=401,
            detail="Valid Service API Key required in x-service-key header"
        )


def require_admin_key(request: Request) -> None:
    """Dependency for admin-only endpoints (listing participants, creating accounts by API).

    These have no player login, so the service key is always required, whatever
    REQUIRE_SERVICE_API_KEY says, and everything is refused when no key is configured.
    """
    if not _service_key_matches(request):
        raise HTTPException(
            status_code=401,
            detail="Valid Service API Key required in x-service-key header"
        )


def require_consent(db: Session, player_id: int) -> None:
    """Refuse study endpoints for a player who hasn't given study consent."""
    if not StudyService.has_valid_consent(db, player_id):
        raise HTTPException(status_code=403, detail="Study consent required")


def require_condition(db: Session, player_id: int, condition: str) -> None:
    """Refuse an endpoint that belongs to the other study condition."""
    if StudyService.get_or_assign_condition(db, player_id) != condition:
        raise HTTPException(status_code=403, detail="Not part of your study condition")


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
