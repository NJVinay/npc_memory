# Standard library imports
import os
import random
from typing import Optional

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Third-party imports
from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# Local imports
from config import config
from database import engine, Base, get_db
from dependencies import limiter
from llamacpp import get_short_part_name
from auth import get_current_user
from services import PlayerService, ChatService, BuildService
import oauth_routes
from routes import npc_routes, build_routes, player_routes, consent_routes

# Template directory setup
templates = Jinja2Templates(directory="templates")

# Check if running in production
IS_PRODUCTION = config.ENVIRONMENT == "production"

# Initialize FastAPI app
app = FastAPI(
    title=config.APP_NAME,
    description="Refactored F1 Car Builder & NPC Memory API",
    version=config.APP_VERSION,
    docs_url=None if IS_PRODUCTION else "/docs",
)

# Set up rate limiting
app.state.limiter = limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    for header, value in config.SECURITY_HEADERS.items():
        if value:
            response.headers[header] = value
    return response

# Static and Routers
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(oauth_routes.router)
app.include_router(npc_routes.router)
app.include_router(build_routes.router)
app.include_router(player_routes.router)
app.include_router(consent_routes.router)

# Database tables
try:
    print("🚀 Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables initialized")
except Exception as e:
    print(f"❌ Database init error: {e}")

# --- Root & Base UI Routes ---

@app.get("/", response_class=HTMLResponse, tags=["UI"])
@app.get("/login", response_class=HTMLResponse, tags=["UI"])
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/cover", response_class=HTMLResponse, tags=["UI"])
def cover_page(
    request: Request,
    player_id: int,
    user: dict = Depends(get_current_user)
):
    if str(user.get("sub")) != str(player_id):
        raise HTTPException(status_code=403, detail="Not authorized for this player")
    return templates.TemplateResponse("cover.html", {
        "request": request,
        "player_id": player_id
    })

@app.get("/chat", response_class=HTMLResponse, tags=["UI"])
def get_chat(
    request: Request,
    player_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
) -> HTMLResponse:
    user_id = int(user.get("sub"))
    if player_id is None:
        player_id = user_id
    elif player_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized for this player")
        
    player = PlayerService.get_player_by_id(db, player_id)
    chat_history = ChatService.get_conversation_history(db, player_id, limit=50)
    latest_build = BuildService.get_latest_build(db, player_id)

    intro_message = ""
    if latest_build:
        intro_message = (
            f"Welcome back! I see your current build includes a "
            f"{get_short_part_name(latest_build.engine)} engine and "
            f"{get_short_part_name(latest_build.tires)} tires."
        )

    return templates.TemplateResponse("chat.html", {
        "request": request,
        "players": [player] if player else [],
        "selected_player_id": player_id,
        "chat_history": chat_history,
        "intro_message": intro_message
    })

@app.get("/chat_static", response_class=HTMLResponse, tags=["UI"])
def get_static_chat(
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
) -> HTMLResponse:
    player = PlayerService.get_player_by_id(db, int(user.get("sub")))
    return templates.TemplateResponse("chat_static.html", {
        "request": request,
        "players": [player] if player else []
    })

@app.get("/start_chat", tags=["Navigation"])
def start_chat(
    player_id: int = Query(...),
    user: dict = Depends(get_current_user)
) -> RedirectResponse:
    if str(user.get("sub")) != str(player_id):
        raise HTTPException(status_code=403, detail="Not authorized for this player")
    npc = random.choice(["dax", "static"])
    target = "/chat" if npc == "dax" else "/chat_static"
    return RedirectResponse(f"{target}?player_id={player_id}")

@app.get("/terms", response_class=HTMLResponse, tags=["UI"])
def terms_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("terms.html", {"request": request})

@app.get("/evaluation", response_class=HTMLResponse, tags=["UI"])
def evaluation_page(request: Request, user: dict = Depends(get_current_user)) -> HTMLResponse:
    return templates.TemplateResponse("evaluation.html", {"request": request})

@app.get("/health", tags=["System"])
def health_check(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.RELOAD,
        log_level=config.LOG_LEVEL.lower()
    )
