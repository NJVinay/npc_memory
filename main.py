# Local imports
from config import config

# Third-party imports
from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional

# Component imports
from database import engine, Base, get_db, add_missing_columns
from dependencies import limiter, CONSENT_REQUIRED_URL, CONDITION_PAGES
from llamacpp import get_short_part_name
from auth import get_current_user, renew_expired_session
from services import PlayerService, ChatService, BuildService, StudyService
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

# Keep sessions alive past the access token's lifetime using the refresh token
app.middleware("http")(renew_expired_session)

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
    # create_all doesn't add new columns to tables that already exist
    add_missing_columns(engine, Base.metadata)
    print("✅ Database tables initialized")
except Exception as e:
    print(f"❌ Database init error: {type(e).__name__}")

# --- Root & Base UI Routes ---

def _authorized_player_id(user: dict, player_id: Optional[int]) -> int:
    """The logged-in player's id; a player_id belonging to anyone else is refused."""
    user_id = int(user.get("sub"))
    if player_id is not None and player_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized for this player")
    return user_id

def _study_redirect(db: Session, player_id: int, page_condition: Optional[str] = None) -> Optional[RedirectResponse]:
    """Where a study page should send the player instead, if anywhere.

    Players without study consent go to the consent step. On a condition's page,
    players assigned to the other condition go to their own page.
    """
    if not StudyService.has_valid_consent(db, player_id):
        return RedirectResponse(CONSENT_REQUIRED_URL, status_code=303)
    if page_condition:
        condition = StudyService.get_or_assign_condition(db, player_id)
        if condition != page_condition:
            return RedirectResponse(f"{CONDITION_PAGES[condition]}?player_id={player_id}", status_code=303)
    return None

@app.get("/", response_class=HTMLResponse, tags=["UI"])
@app.get("/login", response_class=HTMLResponse, tags=["UI"])
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html")

@app.get("/cover", response_class=HTMLResponse, tags=["UI"])
def cover_page(
    request: Request,
    player_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    player_id = _authorized_player_id(user, player_id)
    redirect = _study_redirect(db, player_id)
    if redirect:
        return redirect
    return templates.TemplateResponse(request, "cover.html", {
        "player_id": player_id
    })

@app.get("/chat", response_class=HTMLResponse, tags=["UI"])
def get_chat(
    request: Request,
    player_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
) -> HTMLResponse:
    player_id = _authorized_player_id(user, player_id)
    redirect = _study_redirect(db, player_id, "dax")
    if redirect:
        return redirect

    player = PlayerService.get_player_by_id(db, player_id)
    # The conversation as the player saw it: Dax turns that got a reply
    chat_history = ChatService.get_conversation_history(
        db, player_id, limit=50, npc_id=config.DEFAULT_NPC_ID, exclude_statuses=("llm_error",)
    )
    latest_build = BuildService.get_latest_build(db, player_id)

    intro_message = ""
    if latest_build:
        intro_message = (
            f"Welcome back! I see your current build includes a "
            f"{get_short_part_name(latest_build.engine)} engine and "
            f"{get_short_part_name(latest_build.tires)} tires."
        )

    return templates.TemplateResponse(request, "chat.html", {
        "players": [player] if player else [],
        "player_name": (player.display_name if player else None) or "Driver",
        "selected_player_id": player_id,
        "chat_history": chat_history,
        "intro_message": intro_message
    })

@app.get("/chat_static", response_class=HTMLResponse, tags=["UI"])
def get_static_chat(
    request: Request,
    player_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
) -> HTMLResponse:
    player_id = _authorized_player_id(user, player_id)
    redirect = _study_redirect(db, player_id, "static")
    if redirect:
        return redirect

    player = PlayerService.get_player_by_id(db, player_id)
    return templates.TemplateResponse(request, "chat_static.html", {
        "players": [player] if player else []
    })

@app.get("/start_chat", tags=["Navigation"])
def start_chat(
    player_id: int = Query(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
) -> RedirectResponse:
    player_id = _authorized_player_id(user, player_id)
    redirect = _study_redirect(db, player_id)
    if redirect:
        return redirect
    # Drawn once and kept, so a participant never sees both NPCs
    condition = StudyService.get_or_assign_condition(db, player_id)
    return RedirectResponse(f"{CONDITION_PAGES[condition]}?player_id={player_id}")

@app.get("/terms", response_class=HTMLResponse, tags=["UI"])
def terms_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "terms.html")

@app.get("/evaluation", response_class=HTMLResponse, tags=["UI"])
def evaluation_page(request: Request, user: dict = Depends(get_current_user)) -> HTMLResponse:
    return templates.TemplateResponse(request, "evaluation.html")

@app.get("/health", tags=["System"])
def health_check(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        # Keep database details (host, driver, user) out of a public endpoint
        print(f"❌ Health check failed: {type(e).__name__}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.RELOAD,
        log_level=config.LOG_LEVEL.lower()
    )
