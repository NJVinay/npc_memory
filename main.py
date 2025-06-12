from fastapi import FastAPI, Depends, HTTPException, Request, Form, Query
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base, NPCMemory, Player, CarBuild
from schemas import NPCMemoryCreate, NPCMemoryResponse, NPCMemoryUpdate, PlayerCreate, PlayerResponse
from typing import List
from sentiment import analyze_sentiment
from deepseek import generate_npc_response
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder
from turbotom import turbotom_response
import os, json, hashlib, time, random
from uuid import UUID, uuid4

templates = Jinja2Templates(directory="templates") #Template directory setup

# Initialize FastAPI app with metadata
app = FastAPI(
    title="NPC Memory API",
    description="API to store, retrieve, update, and delete NPC interactions",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Can be modified to allow only the game specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Create database tables
Base.metadata.create_all(bind=engine)

class ChatRequest(BaseModel):
    player_id: int
    npc_id: int
    dialogue: str

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

#  Root route   
@app.get("/", response_class=HTMLResponse)
def login_page_redirect(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/cover", response_class=HTMLResponse)
def cover_page(request: Request, player_id: int = Query(...), db: Session = Depends(get_db)):
    return templates.TemplateResponse("cover.html", {
        "request": request,
        "player_id": player_id
    })

#  Store a new NPC interaction with duplicate check
@app.post("/store_interaction/", response_model=NPCMemoryResponse, description="Player sends dialogue only. Sentiment is auto-analyzed and NPC reply is generated.", tags=["Create"])
def store_interaction(data: NPCMemoryCreate, db: Session = Depends(get_db)):
    # Check for duplicate entry
    existing_entry = db.query(NPCMemory).filter(
        NPCMemory.player_id == data.player_id,
        NPCMemory.npc_id == data.npc_id,
        NPCMemory.dialogue == data.dialogue
    ).first()

    if existing_entry:
        raise HTTPException(status_code=400, detail="This interaction already exists.")

    # Analyze player sentiment
    player_sentiment = analyze_sentiment(data.dialogue)

    # Generate NPC response
    npc_reply = generate_npc_response(data.dialogue, player_sentiment)

    # Analyze NPC sentiment
    npc_sentiment = analyze_sentiment(npc_reply)

    # Create the object manually to inject the predicted sentiment  
    npc_interaction = NPCMemory(
        player_id=data.player_id,
        npc_id=data.npc_id,
        dialogue=data.dialogue,
        sentiment=player_sentiment,
        npc_reply=npc_reply,
        npc_sentiment=npc_sentiment
    )
    db.add(npc_interaction)
    try:
        db.commit()
        db.refresh(npc_interaction)
    except Exception as e:
        db.rollback()
        print("DB commit error (store_interaction): ", e)
        raise HTTPException(status_code=500, detail="Database connection issue, consider a retry.")
    return npc_interaction

#  Retrieve past interactions with error handling
@app.get("/get_interactions/{player_id}/{npc_id}", response_model=List[NPCMemoryResponse], tags=["Retrieval"])
def get_interactions(player_id: int, npc_id: int, db: Session = Depends(get_db)):
    interactions = db.query(NPCMemory).filter(
        NPCMemory.player_id == player_id,
        NPCMemory.npc_id == npc_id
    ).order_by(NPCMemory.timestamp.desc()).all()

    if not interactions:
        raise HTTPException(status_code=404, detail="No interactions found for this player and NPC.")

    return interactions

#  Update an NPC interaction
@app.put("/update_interaction/{id}", response_model=NPCMemoryResponse, description="Update player dialogue only. Sentiment and NPC reply are updated automatically.", tags=["Update"])
def update_interaction(id: int, data: NPCMemoryUpdate, db: Session = Depends(get_db)):
    npc_interaction = db.query(NPCMemory).filter(NPCMemory.id == id).first()

    if not npc_interaction:
        raise HTTPException(status_code=404, detail="Interaction not found.")

    # Always update dialogue
    npc_interaction.dialogue = data.dialogue

    # Analyze or accept player sentiment
    player_sentiment = analyze_sentiment(data.dialogue)
    npc_interaction.sentiment = player_sentiment

    # Generate NPC response via Deepseek
    npc_reply = generate_npc_response(data.dialogue, player_sentiment)
    npc_interaction.npc_reply = npc_reply

    # Analyze NPC sentiment
    npc_interaction.npc_sentiment = analyze_sentiment(npc_reply)

    db.commit()
    db.refresh(npc_interaction)
    return npc_interaction

#  Delete an NPC interaction
@app.delete("/delete_interaction/{id}", response_model=NPCMemoryResponse, tags=["Delete"])
def delete_interaction(id: int, db: Session = Depends(get_db)):
    npc_interaction = db.query(NPCMemory).filter(NPCMemory.id == id).first()

    if not npc_interaction:
        raise HTTPException(status_code=404, detail="Interaction not found.")

    # Capture the interaction before deletion for return 
    deleted_data = NPCMemoryResponse.model_validate(npc_interaction)

    db.delete(npc_interaction)
    db.commit()
    return deleted_data

# Check health status
@app.get("/health", tags=["System"])
def health_check():
    return {"status": "OK"}

# Create a new player
@app.post("/create_player", response_model=PlayerResponse, tags=["Players"])
def create_player(player: PlayerCreate, db: Session = Depends(get_db)):

    existing = db.query(Player).filter(Player.name == player.name).first()
    if existing: 
        raise HTTPException(status_code=400, detail="Player with this name already exists")
    
    new_player = Player(**player.dict())
    db.add(new_player)
    db.commit()
    db.refresh(new_player)
    
    return new_player

# Get all players
@app.get("/players", response_model=List[PlayerResponse], tags=["Players"])
def get_players(db: Session = Depends(get_db)):
    return db.query(Player).all()

@app.get("/chat", response_class=HTMLResponse)
def get_chat(request: Request, player_id: int = Query(default=None), db: Session = Depends(get_db)):
    players = db.query(Player).all()
    chat_history = []

    latest_build = None
    intro_message = ""

    if player_id:
        chat_history = (
            db.query(NPCMemory)
            .filter(NPCMemory.player_id == player_id)
            .order_by(NPCMemory.timestamp.asc())
            .all()
        )
        latest_build = get_latest_build(player_id, db)

    if latest_build:
        intro_message = f"Welcome back! I see your current build includes a {latest_build.engine} engine and {latest_build.tires} tires. Need any tweaks?"

    return templates.TemplateResponse("chat.html", {
        "request": request,
        "players": players,
        "selected_player_id": player_id,
        "chat_history": chat_history,
        "intro_message": intro_message
    })

@app.post("/chat", response_class=HTMLResponse)
def post_chat(
    request: Request,
    player_id: int = Form(...),
    npc_id: int = Form(1),
    dialogue: str = Form(...),
    db: Session = Depends(get_db)
):
    players = db.query(Player).all()

    #Fetches last 3 interactions for player
    history = (
        db.query(NPCMemory)
        .filter(NPCMemory.player_id == player_id)
        .order_by(NPCMemory.timestamp.desc())
        .limit(1)
        .all()
    )
    context = list(reversed(history)) #reversing from old to new to fetch the last 2

    sentiment = analyze_sentiment(dialogue)
    player_name = db.query(Player).filter(Player.id == player_id).first().name
    npc_reply = generate_npc_response(dialogue, sentiment, player_id, context, player_name)

    memory = NPCMemory(
        player_id = player_id,
        npc_id = 1,
        dialogue = dialogue,
        sentiment = sentiment,
        npc_reply = npc_reply,
        npc_sentiment = analyze_sentiment(npc_reply)
    )

    db.add(memory)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print("DB commit error (post_chat): ", e)
        raise HTTPException(status_code=500, detail="Database connection issue, please retry")

    chat_history = (
        db.query(NPCMemory)
        .filter(NPCMemory.player_id == player_id)
        .order_by(NPCMemory.timestamp.asc())
        .all()
    )

    return templates.TemplateResponse("chat.html", {
        "request": request,
        "players": players,
        "npc_reply": npc_reply,
        "last_dialogue": dialogue,
        "selected_player_id": player_id,
        "chat_history": chat_history
    })

@app.post("/chat_api")
async def chat_api(
    request: Request,
    player_id: int = Form(...),
    npc_id: int = Form(1),
    dialogue: str = Form(...),
    db: Session = Depends(get_db)
):
    history = (
        db.query(NPCMemory)
        .filter(NPCMemory.player_id == player_id)  
        .order_by(NPCMemory.timestamp.desc())
        .limit(2)
        .all()
    )
    context = list(reversed(history))

    start = time.time()
    sentiment = analyze_sentiment(dialogue)
    print("Sentiment analysis took:", round(time.time() - start, 2), "s")
    player_obj = db.query(Player).filter(Player.id == player_id).first()
    player_name = player_obj.display_name or player_obj.name
    build = get_latest_build(player_id, db)
    llm_start = time.time()
    npc_reply = generate_npc_response(dialogue, sentiment, player_id, context, player_name, build=build)
    llm_duration = round(time.time() - llm_start, 2)
    print(f"⏱️ LLM generation took: {llm_duration}s")
    
    commit_start = time.time()
    memory = NPCMemory(
        player_id=player_id,
        npc_id=1,
        dialogue=dialogue,
        sentiment=sentiment,
        npc_reply=npc_reply,
        npc_sentiment=analyze_sentiment(npc_reply)
    )
    db.add(memory)
    db.commit()
    print("🗃️ DB commit took:", round(time.time() - commit_start, 2), "s")

    try:
        db_commit_start = time.time()
        db_duration = round(time.time() - db_commit_start, 2)
        print(f"🗃️ DB commit took: {db_duration}s")

    except Exception as e:
        db.rollback()
        print("DB commit error (chat_api): ", e)
        raise HTTPException(status_code=500, detail="Database issue")

    return JSONResponse(content={
        "player_dialogue": dialogue,
        "npc_reply": npc_reply["response"] if isinstance(npc_reply, dict) else str(npc_reply)
        })
    

@app.get("/create_player_form", response_class=HTMLResponse)
def player_form(request: Request):
    return templates.TemplateResponse("create_player.html", {"request": request})

@app.post("/create_player_form")
def create_player_from_form(
    request: Request,
    name: str = Form(...),
    pin: str = Form(...),
    db: Session = Depends(get_db)
):
    new_uuid = str(uuid4())
    hashed_pin = hashlib.sha256(pin.encode()).hexdigest()

    new_player = Player(name=new_uuid, role=hashed_pin, display_name=name)
    db.add(new_player)
    db.commit()
    db.refresh(new_player)

    return templates.TemplateResponse("player_created.html", {
        "request": request,
        "player_id": new_player.id,
        "uuid": new_uuid, 
        "display_name": name
    })

@app.get("/chat_static", response_class=HTMLResponse)
def get_static_chat(request: Request, db: Session = Depends(get_db)):
    players = db.query(Player).all()
    return templates.TemplateResponse("chat_static.html", {
        "request": request,
        "players": players
    })

@app.post("/chat_api_static")
async def chat_api_static(
    request = Request,
    player_id: int = Form(...),
    npc_id: int = Form(...),
    dialogue: str = Form(...),
    db : Session = Depends(get_db)
):
    response = turbotom_response(dialogue, player_id, db)
    return JSONResponse(content={
        "player_dialogue": dialogue,
        "npc_reply": response}
    )


@app.get("/build", response_class=HTMLResponse)
def get_build(request: Request, db: Session = Depends(get_db), player_id: int = Query(default=None)):
    players = db.query(Player).all()
    players_json = jsonable_encoder(players)
    if not player_id and players:
        player_id = players[0].id  # default to first player
    return templates.TemplateResponse("build.html", {
        "request": request,
        "players": players_json,
        "selected_player_id": player_id
    })

@app.post("/save_car_build")
async def save_car_build(
    player_id: int = Form(...),
    chassis: str = Form(...),
    engine: str = Form(...),
    tires: str = Form(...),
    frontWing: str = Form(...),
    rearWing: str = Form(...),
    db: Session = Depends(get_db)
):
    build = CarBuild(
        player_id=player_id,
        chassis=chassis,
        engine=engine,
        tires=tires,
        frontWing=frontWing,
        rearWing=rearWing
    )

    db.add(build)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error while saving build.")

    return {"status": "success", "message": "Build saved successfully!"}

@app.get("/get_builds/{player_id}")
def get_player_builds(player_id: int, db: Session = Depends(get_db)):
    return db.query(CarBuild).filter(CarBuild.player_id == player_id).all()

def get_latest_build(player_id: int, db: Session): #Most recent build (for chat context)
    build = (
        db.query(CarBuild)
        .filter(CarBuild.player_id == player_id)
        .order_by(CarBuild.id.desc())
        .first()
    )
    return build

@app.get("/start_chat")
def start_chat(player_id: int = Query(...), db: Session = Depends(get_db)):
    npc = random.choice(["dax", "static"])
    if npc == "dax":
        return RedirectResponse(f"/chat?player_id={player_id}")
    return RedirectResponse(f"/chat_static?player_id={player_id}")

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/evaluation", response_class=HTMLResponse)
def evaluation_page(request: Request):
    return templates.TemplateResponse("evaluation.html", {"request": request})

@app.get("/verify_player")
def verify_player(uuid: str, pin: str, db: Session = Depends(get_db)):
    try:
        UUID(uuid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    hashed_pin = hashlib.sha256(pin.encode()).hexdigest()
    player = db.query(Player).filter(Player.name == uuid, Player.role == hashed_pin).first()

    if not player:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return {"player_id": player.id}
