"""
OAuth 2.0 & JWT Authentication Routes
"""

import os
import httpx
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from auth import (
    create_access_token, create_refresh_token, verify_token,
    OAUTH_CONFIG, hash_password, verify_password
)
from database import SessionLocal
from models import Player
from schemas import PlayerCreate

# Check if running in production
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development") == "production"

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_db():
    """Database dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/login/{provider}")
async def oauth_login(provider: str, request: Request):
    """Initiate OAuth 2.0 login flow."""
    if provider not in OAUTH_CONFIG:
        raise HTTPException(status_code=400, detail="Invalid OAuth provider")
    
    config = OAUTH_CONFIG[provider]
    redirect_uri = str(request.url_for("oauth_callback", provider=provider))
    
    # Build authorization URL
    auth_url = (
        f"{config['authorize_url']}?"
        f"client_id={config['client_id']}&"
        f"redirect_uri={redirect_uri}&"
        f"scope={' '.join(config['scopes'])}&"
        f"response_type=code"
    )
    
    if provider == "google":
        auth_url += "&access_type=offline&prompt=consent"
    
    return RedirectResponse(url=auth_url)


@router.get("/callback/{provider}")
async def oauth_callback(provider: str, code: str, request: Request, db: Session = Depends(get_db)):
    """Handle OAuth 2.0 callback and create session."""
    if provider not in OAUTH_CONFIG:
        raise HTTPException(status_code=400, detail="Invalid OAuth provider")
    
    config = OAUTH_CONFIG[provider]
    redirect_uri = str(request.url_for("oauth_callback", provider=provider))
    
    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            config['token_url'],
            data={
                "client_id": config['client_id'],
                "client_secret": config['client_secret'],
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code"
            },
            headers={"Accept": "application/json"}
        )
        
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get access token")
        
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        
        # Get user info
        headers = {"Authorization": f"Bearer {access_token}"}
        userinfo_response = await client.get(config['userinfo_url'], headers=headers)
        
        if userinfo_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info")
        
        user_info = userinfo_response.json()
    
    # Extract email and name
    if provider == "google":
        email = user_info.get("email")
        name = user_info.get("name", email.split("@")[0])
    elif provider == "github":
        email = user_info.get("email")
        if not email:
            # Fetch primary email from GitHub
            async with httpx.AsyncClient() as client:
                emails_response = await client.get(
                    "https://api.github.com/user/emails",
                    headers=headers
                )
                emails = emails_response.json()
                email = next((e["email"] for e in emails if e["primary"]), None)
        name = user_info.get("name") or user_info.get("login")
    
    if not email:
        raise HTTPException(status_code=400, detail="Email not provided by OAuth provider")
    
    # Find or create user
    player = db.query(Player).filter(Player.email == email).first()
    
    if not player:
        # Create new user
        from uuid import uuid4
        player = Player(
            name=str(uuid4()),  # Generate UUID as account ID
            email=email,
            display_name=name,
            pin_hash=None  # OAuth users don't use password authentication
        )
        db.add(player)
        db.commit()
        db.refresh(player)
    
    # Create JWT tokens
    token_data = {"sub": str(player.id), "email": email, "name": name}
    access_token_jwt = create_access_token(token_data)
    refresh_token_jwt = create_refresh_token(token_data)
    
    # Set tokens in httpOnly cookies and redirect to cover page
    response = RedirectResponse(url=f"/cover?player_id={player.id}")
    response.set_cookie(
        key="access_token",
        value=access_token_jwt,
        httponly=True,
        secure=IS_PRODUCTION,  # True in production with HTTPS
        samesite="lax",
        max_age=900  # 15 minutes
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token_jwt,
        httponly=True,
        secure=IS_PRODUCTION,  # True in production with HTTPS
        samesite="lax",
        max_age=604800  # 7 days
    )
    
    return response


@router.post("/token/refresh")
async def refresh_access_token(request: Request, response: Response):
    """Refresh access token using refresh token."""
    refresh_token = request.cookies.get("refresh_token")
    
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not found")
    
    # Verify refresh token
    payload = verify_token(refresh_token, "refresh")
    
    # Create new access token
    token_data = {"sub": payload["sub"], "email": payload["email"], "name": payload["name"]}
    new_access_token = create_access_token(token_data)
    
    # Set new access token
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=IS_PRODUCTION,  # True in production with HTTPS
        samesite="lax",
        max_age=900
    )
    
    return {"message": "Token refreshed successfully"}


@router.post("/logout")
async def logout(response: Response):
    """Logout user by clearing tokens."""
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logged out successfully"}
