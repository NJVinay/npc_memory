from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Form, Query, Response
from sqlalchemy.orm import Session
from fastapi.responses import HTMLResponse
from uuid import uuid4
import bcrypt

from config import config
from database import get_db
from auth import set_auth_cookies
from models import Player
from schemas import PlayerCreate, PlayerResponse
from services import PlayerService
from dependencies import limiter, require_admin_key, is_email_allowed

router = APIRouter(tags=["Players"])
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory="templates")

@router.post("/create_player", response_model=PlayerResponse)
@limiter.limit(config.RATE_LIMITS["general"])
def create_player(
    request: Request, # Fix for slowapi crash
    player: PlayerCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_key)
) -> PlayerResponse:
    existing = db.query(Player).filter(Player.name == player.name).first()
    if existing: 
        raise HTTPException(status_code=400, detail="Player with this name already exists")
    
    new_player = PlayerService.create_player(db, player)
    return new_player

@router.get("/players", response_model=List[PlayerResponse])
@limiter.limit(config.RATE_LIMITS["general"])
def get_players(
    request: Request, # Fix for slowapi crash
    skip: int = Query(0, ge=0),
    limit: int = Query(config.DEFAULT_PAGE_SIZE, ge=1, le=config.MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_key)
) -> List[PlayerResponse]:
    return PlayerService.get_all_players(db, skip=skip, limit=limit)

@router.get("/create_player_form", response_class=HTMLResponse)
def player_form(request: Request):
    return templates.TemplateResponse(request, "create_player.html")

@router.post("/create_player_form")
@limiter.limit(config.RATE_LIMITS["register"])
def create_player_from_form(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
) -> HTMLResponse:
    if not is_email_allowed(email):
        raise HTTPException(status_code=403, detail="Email not allowed")
    # Check if email already exists
    existing_player = db.query(Player).filter(Player.email == email).first()
    if existing_player:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    new_player = Player(
        name=str(uuid4()),
        email=email,
        display_name=name,
        pin_hash=hashed_password
    )
    db.add(new_player)
    db.commit()
    db.refresh(new_player)

    return templates.TemplateResponse(request, "player_created.html", {
        "player_id": new_player.id,
        "email": email,
        "display_name": name
    })

@router.post("/verify_player")
@limiter.limit(config.RATE_LIMITS["login"])
def verify_player(
    request: Request,
    response: Response,
    credentials: dict,
    db: Session = Depends(get_db)
) -> dict:
    email = credentials.get("email")
    password = credentials.get("password")
    
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")
    if not is_email_allowed(email):
        raise HTTPException(status_code=403, detail="Email not allowed")

    player = PlayerService.verify_player_email_password(db, email, password)

    if not player:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    set_auth_cookies(response, {"sub": str(player.id), "email": player.email, "name": player.display_name or player.name})
    return {"player_id": player.id}
