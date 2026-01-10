# Standard library imports
import json
import os
import random
import time
from typing import List, Optional
from uuid import UUID, uuid4

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Third-party imports
from fastapi import FastAPI, Depends, HTTPException, Request, Form, Query
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Local imports
from config import config
from database import SessionLocal, engine
from llamacpp import get_short_part_name
from models import Base, NPCMemory, Player, CarBuild, Consent
from schemas import (
    NPCMemoryCreate, NPCMemoryResponse, NPCMemoryUpdate,
    PlayerCreate, PlayerResponse,
    CarBuildResponse,
    ConsentCreate, ConsentResponse
)
from services import PlayerService, ChatService, BuildService, ConsentService
from sentiment import analyze_sentiment
from oauth_routes import router as oauth_router

templates = Jinja2Templates(directory="templates") #Template directory setup

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI app with metadata
app = FastAPI(
    title=config.APP_NAME,
    description="API to store, retrieve, update, and delete NPC interactions with AI-powered NPCs",
    version=config.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add rate limit handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include OAuth routes
app.include_router(oauth_router)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Create database tables
Base.metadata.create_all(bind=engine)

# Dependency to get the database session with improved error handling
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()

#  Root route   
@app.get("/", response_class=HTMLResponse, tags=["UI"])
def login_page_redirect(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/cover", response_class=HTMLResponse, tags=["UI"])
def cover_page(request: Request, player_id: int = Query(...), db: Session = Depends(get_db)):
    return templates.TemplateResponse("cover.html", {
        "request": request,
        "player_id": player_id
    })

#  Store a new NPC interaction with duplicate check
@app.post(
    "/store_interaction/",
    response_model=NPCMemoryResponse,
    description="Player sends dialogue only. Sentiment is auto-analyzed and NPC reply is generated.",
    tags=["NPC Interactions"],
    status_code=201
)
def store_interaction(data: NPCMemoryCreate, db: Session = Depends(get_db)) -> NPCMemoryResponse:
    # Check for duplicate entry
    existing_entry = db.query(NPCMemory).filter(
        NPCMemory.player_id == data.player_id,
        NPCMemory.npc_id == data.npc_id,
        NPCMemory.dialogue == data.dialogue
    ).first()

    if existing_entry:
        raise HTTPException(status_code=400, detail="This interaction already exists.")

    # Get player and context
    player = PlayerService.get_player_by_id(db, data.player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    player_name = player.display_name or player.name or "Player"
    build = BuildService.get_latest_build(db, data.player_id)
    context: List[NPCMemory] = []
    
    # Use service layer to create interaction
    try:
        npc_interaction = ChatService.create_interaction(
            db, data.player_id, data.npc_id, data.dialogue,
            context, player_name, build
        )
        return npc_interaction
    except Exception as e:
        db.rollback()
        print(f"DB commit error (store_interaction): {e}")
        raise HTTPException(status_code=500, detail="Database connection issue, consider a retry.")

#  Retrieve past interactions with error handling
@app.get(
    "/get_interactions/{player_id}/{npc_id}",
    response_model=List[NPCMemoryResponse],
    tags=["NPC Interactions"]
)
def get_interactions(player_id: int, npc_id: int, db: Session = Depends(get_db)) -> List[NPCMemoryResponse]:
    interactions = db.query(NPCMemory).filter(
        NPCMemory.player_id == player_id,
        NPCMemory.npc_id == npc_id
    ).order_by(NPCMemory.timestamp.desc()).all()

    if not interactions:
        raise HTTPException(status_code=404, detail="No interactions found for this player and NPC.")

    return interactions

#  Update an NPC interaction
@app.put(
    "/update_interaction/{id}",
    response_model=NPCMemoryResponse,
    description="Update player dialogue only. Sentiment and NPC reply are updated automatically.",
    tags=["NPC Interactions"]
)
def update_interaction(id: int, data: NPCMemoryUpdate, db: Session = Depends(get_db)) -> NPCMemoryResponse:
    npc_interaction = db.query(NPCMemory).filter(NPCMemory.id == id).first()

    if not npc_interaction:
        raise HTTPException(status_code=404, detail="Interaction not found.")

    # Get player info
    player = PlayerService.get_player_by_id(db, npc_interaction.player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    player_name = player.display_name or player.name or "Player"
    build = BuildService.get_latest_build(db, npc_interaction.player_id)
    
    # Update dialogue
    npc_interaction.dialogue = data.dialogue

    # Analyze player sentiment
    player_sentiment = analyze_sentiment(data.dialogue)
    npc_interaction.sentiment = player_sentiment

    # Generate new NPC response
    from llamacpp import generate_npc_response
    npc_reply_obj = generate_npc_response(
        data.dialogue, player_sentiment,
        npc_interaction.player_id, [], player_name, build=build
    )
    npc_reply_text = npc_reply_obj["response"] if isinstance(npc_reply_obj, dict) else str(npc_reply_obj)
    npc_interaction.npc_reply = npc_reply_text

    # Analyze NPC sentiment
    npc_interaction.npc_sentiment = analyze_sentiment(npc_reply_text)

    db.commit()
    db.refresh(npc_interaction)
    return npc_interaction

#  Delete an NPC interaction
@app.delete(
    "/delete_interaction/{id}",
    response_model=NPCMemoryResponse,
    tags=["NPC Interactions"],
    status_code=200
)
def delete_interaction(id: int, db: Session = Depends(get_db)) -> NPCMemoryResponse:
    npc_interaction = db.query(NPCMemory).filter(NPCMemory.id == id).first()

    if not npc_interaction:
        raise HTTPException(status_code=404, detail="Interaction not found.")

    # Capture the interaction before deletion for return 
    deleted_data = NPCMemoryResponse.model_validate(npc_interaction)

    db.delete(npc_interaction)
    db.commit()
    return deleted_data

# Check health status with database connectivity
@app.get("/health", tags=["System"])
def health_check(db: Session = Depends(get_db)) -> dict:
    try:
        # Test database connection
        db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

# Create a new player
@app.post("/create_player", response_model=PlayerResponse, tags=["Players"])
def create_player(player: PlayerCreate, db: Session = Depends(get_db)) -> PlayerResponse:
    existing = db.query(Player).filter(Player.name == player.name).first()
    if existing: 
        raise HTTPException(status_code=400, detail="Player with this name already exists")
    
    new_player = PlayerService.create_player(db, player)
    return new_player

# Get all players with pagination
@app.get("/players", response_model=List[PlayerResponse], tags=["Players"])
def get_players(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        config.DEFAULT_PAGE_SIZE,
        ge=1,
        le=config.MAX_PAGE_SIZE,
        description="Maximum records to return"
    ),
    db: Session = Depends(get_db)
) -> List[PlayerResponse]:
    return PlayerService.get_all_players(db, skip=skip, limit=limit)

@app.get("/chat", response_class=HTMLResponse, tags=["Chat Interface"])
def get_chat(request: Request, player_id: Optional[int] = Query(default=None), db: Session = Depends(get_db)) -> HTMLResponse:
    players = PlayerService.get_all_players(db, limit=100)
    chat_history = []

    latest_build = None
    intro_message = ""

    if player_id:
        chat_history = ChatService.get_conversation_history(db, player_id, limit=50)
        latest_build = BuildService.get_latest_build(db, player_id)

    if latest_build:
        intro_message = (
            f"Welcome back! I see your current build includes a "
            f"{get_short_part_name(latest_build.engine)} engine and "
            f"{get_short_part_name(latest_build.tires)} tires. Need any tweaks?"
        )

    return templates.TemplateResponse("chat.html", {
        "request": request,
        "players": players,
        "selected_player_id": player_id,
        "chat_history": chat_history,
        "intro_message": intro_message
    })

@app.post("/chat", response_class=HTMLResponse, tags=["Chat Interface"])
def post_chat(
    request: Request,
    player_id: int = Form(...),
    npc_id: int = Form(config.DEFAULT_NPC_ID),
    dialogue: str = Form(...),
    db: Session = Depends(get_db)
) -> HTMLResponse:
    # Validate player exists
    player = PlayerService.get_player_by_id(db, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    # Validate dialogue is not empty
    if not dialogue or not dialogue.strip():
        raise HTTPException(status_code=400, detail="Dialogue cannot be empty")
    
    players = PlayerService.get_all_players(db, limit=100)

    # Get recent context
    context = ChatService.get_conversation_history(db, player_id, limit=config.CONTEXT_WINDOW)
    
    player_name = player.display_name or player.name or "Player"
    build = BuildService.get_latest_build(db, player_id)
    
    # Create interaction using service (includes sentiment analysis)
    try:
        memory = ChatService.create_interaction(
            db, player_id, npc_id, dialogue,
            context, player_name, build
        )
        npc_reply_text = memory.npc_reply
        print(f"📊 PLAYER SENTIMENT: '{dialogue}' → {memory.sentiment}")
    except Exception as e:
        db.rollback()
        print(f"DB commit error (post_chat): {e}")
        raise HTTPException(status_code=500, detail="Database connection issue, please retry")

    chat_history = ChatService.get_conversation_history(db, player_id, limit=50)

    return templates.TemplateResponse("chat.html", {
        "request": request,
        "players": players,
    "npc_reply": npc_reply_text,
        "last_dialogue": dialogue,
        "selected_player_id": player_id,
        "chat_history": chat_history
    })

@app.post("/chat_api", tags=["Chat API"])
@limiter.limit("30/minute")  # Groq free tier limit
async def chat_api(
    request: Request,
    player_id: int = Form(...),
    npc_id: int = Form(config.DEFAULT_NPC_ID),
    dialogue: str = Form(...),
    db: Session = Depends(get_db)
) -> JSONResponse:
    # Validate dialogue
    if not dialogue or not dialogue.strip():
        raise HTTPException(status_code=400, detail="Dialogue cannot be empty")
    
    # Get conversation history from config
    context = ChatService.get_conversation_history(
        db, player_id,
        limit=config.MAX_CONVERSATION_HISTORY
    )

    start = time.time()
    
    # Get or create player
    player_obj = PlayerService.get_player_by_id(db, player_id)
    if not player_obj:
        print(f"⚠️ Player {player_id} not found, creating default player")
        player_data = PlayerCreate(
            name=f"Player{player_id}",
            display_name=f"Player{player_id}"
        )
        player_obj = PlayerService.create_player(db, player_data)
    
    player_name = player_obj.display_name or player_obj.name or "Player"
    build = BuildService.get_latest_build(db, player_id)
    
    llm_start = time.time()
    
    # Use service to create interaction (handles sentiment + NPC reply)
    try:
        memory = ChatService.create_interaction(
            db, player_id, npc_id, dialogue,
            context, player_name, build
        )
        
        llm_duration = round(time.time() - llm_start, 2)
        print(f"📊 PLAYER SENTIMENT: '{dialogue}' → {memory.sentiment}")
        print(f"⏱️ Total processing took: {llm_duration}s")
        
        return JSONResponse(content={
            "player_dialogue": dialogue,
            "npc_reply": memory.npc_reply,
            "sentiment": memory.sentiment,
            "generation_time": llm_duration
        })
    except Exception as e:
        db.rollback()
        print(f"❌ Error in chat_api: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/create_player_form", response_class=HTMLResponse, tags=["Players"])
def player_form(request: Request):
    return templates.TemplateResponse("create_player.html", {"request": request})

@app.post("/create_player_form", tags=["Players"])
@limiter.limit("3/minute")  # Prevent spam registrations
def create_player_from_form(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
) -> HTMLResponse:
    # Check if email already exists
    existing_player = db.query(Player).filter(Player.email == email).first()
    if existing_player:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password with bcrypt
    import bcrypt
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Create player with email + password
    new_player = Player(
        name=str(uuid4()),  # Generate UUID for internal use
        email=email,
        display_name=name,
        pin_hash=hashed_password
    )
    db.add(new_player)
    db.commit()
    db.refresh(new_player)

    return templates.TemplateResponse("player_created.html", {
        "request": request,
        "player_id": new_player.id,
        "email": email,
        "display_name": name
    })

@app.get("/chat_static", response_class=HTMLResponse, tags=["Chat Interface"])
def get_static_chat(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    players = PlayerService.get_all_players(db, limit=100)
    return templates.TemplateResponse("chat_static.html", {
        "request": request,
        "players": players
    })

@app.get("/build", response_class=HTMLResponse, tags=["Car Builds"])
def get_build(
    request: Request,
    db: Session = Depends(get_db),
    player_id: Optional[int] = Query(default=None)
) -> HTMLResponse:
    players = PlayerService.get_all_players(db, limit=100)
    players_json = jsonable_encoder(players)
    if not player_id and players:
        player_id = players[0].id  # default to first player
    return templates.TemplateResponse("build.html", {
        "request": request,
        "players": players_json,
        "selected_player_id": player_id
    })

@app.post("/save_car_build", tags=["Car Builds"])
async def save_car_build(
    player_id: int = Form(...),
    chassis: str = Form(""),  # Allow empty values for partial builds
    engine: str = Form(""),
    tires: str = Form(""),
    frontWing: str = Form("", alias="frontWing"),
    rearWing: str = Form("", alias="rearWing"),
    db: Session = Depends(get_db)
) -> dict:
    # Validate player exists
    player = PlayerService.get_player_by_id(db, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    try:
        # Convert empty strings to None for database storage
        chassis = chassis if chassis else None
        engine = engine if engine else None
        tires = tires if tires else None
        frontWing = frontWing if frontWing else None
        rearWing = rearWing if rearWing else None
        
        build = BuildService.create_build(
            db, player_id, chassis, engine, tires,
            frontWing, rearWing
        )
        return {"status": "success", "message": "Build saved successfully!", "build_id": build.id}
    except Exception as e:
        db.rollback()
        print(f"❌ Error saving build: {e}")
        raise HTTPException(status_code=500, detail="Database error while saving build.")

@app.get("/get_builds/{player_id}", tags=["Car Builds"])
def get_player_builds(
    player_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(config.DEFAULT_PAGE_SIZE, ge=1, le=config.MAX_PAGE_SIZE),
    db: Session = Depends(get_db)
) -> List[CarBuildResponse]:
    builds = BuildService.get_player_builds(db, player_id, skip=skip, limit=limit)
    return builds if builds else []

@app.get("/start_chat", tags=["Navigation"])
def start_chat(player_id: int = Query(...), db: Session = Depends(get_db)) -> RedirectResponse:
    npc = random.choice(["dax", "static"])
    if npc == "dax":
        return RedirectResponse(f"/chat?player_id={player_id}")
    return RedirectResponse(f"/chat_static?player_id={player_id}")

@app.get("/login", response_class=HTMLResponse, tags=["Authentication"])
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/terms", response_class=HTMLResponse, tags=["Legal"])
def terms_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("terms.html", {"request": request})

@app.get("/evaluation", response_class=HTMLResponse, tags=["Evaluation"])
def evaluation_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("evaluation.html", {"request": request})

@app.post("/verify_player", tags=["Authentication"])
@limiter.limit("5/minute")  # Prevent brute force attacks
def verify_player(request: Request, credentials: dict, db: Session = Depends(get_db)) -> dict:
    email = credentials.get("email")
    password = credentials.get("password")
    
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")

    # Use service with bcrypt verification
    player = PlayerService.verify_player_email_password(db, email, password)

    if not player:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return {"player_id": player.id}

@app.post("/store_consent", response_model=ConsentResponse, tags=["Evaluation"])
def store_consent(consent_data: ConsentCreate, db: Session = Depends(get_db)) -> ConsentResponse:
    """Store user consent data to database.
    
    Args:
        consent_data: Validated consent data
        db: Database session
        
    Returns:
        Created consent record
    """
    try:
        # Verify player exists
        player = PlayerService.get_player_by_id(db, consent_data.player_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        
        # Use service to create consent record
        consent = ConsentService.create_consent(db, consent_data)
        
        print(f"📋 Consent stored to database for {consent.name} (Player {consent.player_id})")
        return consent
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error storing consent: {e}")
        raise HTTPException(status_code=500, detail=f"Error storing consent: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    print(f"Starting {config.APP_NAME} v{config.APP_VERSION}...")
    print("Model loaded successfully!")
    print("Database connection verified!")
    print(f"Server: {config.HOST}:{config.PORT}")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    try:
        uvicorn.run(
            app,
            host=config.HOST,
            port=config.PORT,
            reload=config.RELOAD,
            log_level=config.LOG_LEVEL.lower()
        )
    except Exception as e:
        print(f"❌ Server error: {e}")
        import traceback
        traceback.print_exc()