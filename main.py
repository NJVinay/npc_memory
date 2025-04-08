from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base, NPCMemory
from schemas import NPCMemoryCreate, NPCMemoryResponse, NPCMemoryUpdate
from typing import List
from sentiment import analyze_sentiment
from deepseek import generate_npc_response
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware


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
    allow_origins=["*"],  # Or restrict to your game domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ✅ Root route
@app.get("/")
def read_root():
    return {"message": "NPC Memory API is running!"}

# ✅ Store a new NPC interaction with duplicate check
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
    db.commit()
    db.refresh(npc_interaction)
    return npc_interaction

# ✅ Retrieve past interactions with error handling
@app.get("/get_interactions/{player_id}/{npc_id}", response_model=List[NPCMemoryResponse], tags=["Retrieval"])
def get_interactions(player_id: int, npc_id: int, db: Session = Depends(get_db)):
    interactions = db.query(NPCMemory).filter(
        NPCMemory.player_id == player_id,
        NPCMemory.npc_id == npc_id
    ).order_by(NPCMemory.timestamp.desc()).all()

    if not interactions:
        raise HTTPException(status_code=404, detail="No interactions found for this player and NPC.")

    return interactions

# ✅ Update an NPC interaction
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

# ✅ Delete an NPC interaction
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

@app.get("/health", tags=["System"])
def health_check():
    return {"status": "OK"}