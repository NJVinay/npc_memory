"""
OAuth 2.0 & JWT Authentication Routes
"""

import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import unquote, urlencode
from uuid import uuid4

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from auth import ALGORITHM, verify_token, set_auth_cookies, _set_token_cookie, OAUTH_CONFIG
from config import config
from database import get_db
from models import Player
from schemas import ConsentCreate
from services import ConsentService, StudyService
from dependencies import is_email_allowed, CONSENT_REQUIRED_URL, CONSENT_INVALID_URL

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Random value the provider must send back to the callback (CSRF protection)
STATE_COOKIE = "oauth_state"
STATE_MAX_AGE = 600
# login.html puts the consent given on the login page in this script-readable cookie right
# before a provider sign-in; /auth/login moves it straight into OAUTH_CONSENT_COOKIE
CONSENT_COOKIE = "pending_consent"
# The consent for one sign-in: httpOnly, signed, and tied to that sign-in's state value
OAUTH_CONSENT_COOKIE = "oauth_consent"
# Every cookie a sign-in uses; all are cleared when it completes or fails
SIGN_IN_COOKIES = (STATE_COOKIE, OAUTH_CONSENT_COOKIE, CONSENT_COOKIE)


def _same_value(a: Optional[str], b: Optional[str]) -> bool:
    """Constant-time comparison of two strings (bytes, so any characters are safe)."""
    return bool(a) and bool(b) and hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _seal_consent(consent: str, state: str) -> str:
    return jwt.encode(
        {"type": "oauth_consent", "state": state, "consent": consent,
         "exp": datetime.now(timezone.utc) + timedelta(seconds=STATE_MAX_AGE)},
        config.JWT_SECRET_KEY, algorithm=ALGORITHM
    )


def _open_consent(token: Optional[str], state: str) -> Optional[str]:
    """The consent sealed for this sign-in; None if missing, altered, expired or from another sign-in."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != "oauth_consent" or not _same_value(payload.get("state"), state):
        return None
    return payload.get("consent")


@router.get("/login/{provider}")
async def oauth_login(provider: str, request: Request):
    """Initiate OAuth 2.0 login flow."""
    if provider not in OAUTH_CONFIG:
        raise HTTPException(status_code=400, detail="Invalid OAuth provider")

    provider_config = OAUTH_CONFIG[provider]
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": provider_config["client_id"],
        "redirect_uri": str(request.url_for("oauth_callback", provider=provider)),
        "scope": " ".join(provider_config["scopes"]),
        "response_type": "code",
        "state": state,
    }
    response = RedirectResponse(url=f"{provider_config['authorize_url']}?{urlencode(params)}")
    _set_token_cookie(response, STATE_COOKIE, state, STATE_MAX_AGE)

    # Move the consent out of the script-readable cookie and tie it to this sign-in only,
    # so an earlier, abandoned sign-in on a shared computer can't hand its consent on
    pending_consent = request.cookies.get(CONSENT_COOKIE)
    if pending_consent:
        _set_token_cookie(response, OAUTH_CONSENT_COOKIE, _seal_consent(pending_consent, state), STATE_MAX_AGE)
    else:
        response.delete_cookie(OAUTH_CONSENT_COOKIE)
    response.delete_cookie(CONSENT_COOKIE)
    return response


async def _fetch_identity(provider: str, code: str, redirect_uri: str) -> dict:
    """Exchange the authorization code and return the provider's view of the user:
    {"subject", "email", "email_verified", "name"}."""
    provider_config = OAUTH_CONFIG[provider]

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_response = await client.post(
            provider_config['token_url'],
            data={
                "client_id": provider_config['client_id'],
                "client_secret": provider_config['client_secret'],
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code"
            },
            headers={"Accept": "application/json"}
        )
        access_token = token_response.json().get("access_token") if token_response.status_code == 200 else None
        if not access_token:
            raise HTTPException(status_code=400, detail="Failed to get access token")

        headers = {"Authorization": f"Bearer {access_token}"}
        userinfo_response = await client.get(provider_config['userinfo_url'], headers=headers)
        if userinfo_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info")
        user_info = userinfo_response.json()

        if provider == "google":
            email = user_info.get("email")
            return {
                "subject": str(user_info.get("id") or ""),
                "email": email,
                "email_verified": user_info.get("verified_email") is True,
                "name": user_info.get("name") or (email.split("@")[0] if email else "Player"),
            }

        # GitHub: the profile email can be missing or unverified, so use the verified primary address
        emails_response = await client.get("https://api.github.com/user/emails", headers=headers)
        emails = emails_response.json() if emails_response.status_code == 200 else []
        primary = next(
            (e for e in emails if isinstance(e, dict) and e.get("primary") and e.get("verified")),
            None
        )
        return {
            "subject": str(user_info.get("id") or ""),
            "email": primary.get("email") if primary else None,
            "email_verified": primary is not None,
            "name": user_info.get("name") or user_info.get("login") or "Player",
        }


def _find_or_link_player(db: Session, provider: str, identity: dict) -> Player:
    """The account for this provider identity, created or linked if needed.

    Accounts are matched by the provider's stable user id. An email match is only
    linked when that account has no password and no other sign-in attached, so a
    provider identity can never take over someone else's account.
    """
    player = db.query(Player).filter(
        Player.oauth_provider == provider,
        Player.oauth_subject == identity["subject"]
    ).first()
    if player:
        return player

    player = db.query(Player).filter(Player.email == identity["email"]).first()
    if player:
        if player.pin_hash or player.oauth_subject:
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists. Please sign in the way you signed up."
            )
        # Account from an OAuth sign-in made before identities were stored
        player.oauth_provider = provider
        player.oauth_subject = identity["subject"]
    else:
        player = Player(
            name=str(uuid4()),  # Generate UUID as account ID
            email=identity["email"],
            display_name=identity["name"],
            pin_hash=None,  # OAuth users don't use password authentication
            oauth_provider=provider,
            oauth_subject=identity["subject"]
        )
        db.add(player)
    db.commit()
    db.refresh(player)
    return player


def _store_sign_in_consent(db: Session, player_id: int, consent: Optional[str]) -> Optional[bool]:
    """Save the study consent given on the login page before a provider sign-in.

    Returns True if stored, False if it was given but couldn't be stored (e.g. failed
    validation), None if there was none to store.
    """
    if not consent or StudyService.has_valid_consent(db, player_id):
        return None
    try:
        data = json.loads(unquote(consent))
        ConsentService.create_consent(db, ConsentCreate(**{**data, "player_id": player_id}))
        return True
    except (ValueError, TypeError, SQLAlchemyError) as e:
        db.rollback()
        print(f"⚠️ Could not store consent from sign-in for player {player_id}: {type(e).__name__}")
        return False


async def _complete_sign_in(provider: str, request: Request, code: str, state: str, db: Session) -> RedirectResponse:
    if provider not in OAUTH_CONFIG:
        raise HTTPException(status_code=400, detail="Invalid OAuth provider")
    if not _same_value(state, request.cookies.get(STATE_COOKIE)):
        raise HTTPException(status_code=400, detail="This sign-in expired or was not started here. Please try again.")
    if not code:
        raise HTTPException(status_code=400, detail="Sign-in was cancelled or failed. Please try again.")

    identity = await _fetch_identity(provider, code, str(request.url_for("oauth_callback", provider=provider)))
    if not identity["subject"]:
        raise HTTPException(status_code=400, detail="Failed to get user info")
    if not identity["email"] or not identity["email_verified"]:
        raise HTTPException(status_code=400, detail=f"Your {provider.title()} account has no verified email address.")
    if not is_email_allowed(identity["email"]):
        raise HTTPException(status_code=403, detail="Email not allowed")

    player = _find_or_link_player(db, provider, identity)
    consent_stored = _store_sign_in_consent(db, player.id, _open_consent(request.cookies.get(OAUTH_CONSENT_COOKIE), state))

    # Without study consent the player goes back to the login page to give it
    if StudyService.has_valid_consent(db, player.id):
        target = f"/cover?player_id={player.id}"
    elif consent_stored is False:
        target = CONSENT_INVALID_URL
    else:
        target = CONSENT_REQUIRED_URL
    response = RedirectResponse(url=target)
    set_auth_cookies(response, {"sub": str(player.id), "email": identity["email"], "name": identity["name"]})
    return response


@router.get("/callback/{provider}")
async def oauth_callback(
    provider: str,
    request: Request,
    code: str = "",
    state: str = "",
    db: Session = Depends(get_db)
):
    """Handle OAuth 2.0 callback and create session."""
    try:
        response = await _complete_sign_in(provider, request, code, state, db)
    except HTTPException as e:
        response = JSONResponse({"detail": e.detail}, status_code=e.status_code)
    # Whatever happened, this sign-in's cookies (which can carry the participant's details) are used up
    for cookie in SIGN_IN_COOKIES:
        response.delete_cookie(cookie)
    return response


@router.post("/token/refresh")
async def refresh_access_token(request: Request, response: Response):
    """Refresh access token using refresh token with rotation."""
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not found")

    # Verify refresh token
    payload = verify_token(refresh_token, "refresh")

    # Create new access token AND rotate refresh token
    set_auth_cookies(response, {"sub": payload["sub"], "email": payload["email"], "name": payload["name"]})
    return {"message": "Token refreshed successfully"}


@router.post("/logout")
async def logout(response: Response):
    """Logout user by clearing tokens."""
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logged out successfully"}
