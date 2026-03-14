from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from config import config
from database import get_db
from auth import get_current_user
from models import NPCMemory
from schemas import NPCMemoryCreate, NPCMemoryResponse, NPCMemoryUpdate
from services import ChatService, PlayerService, BuildService
from sentiment import analyze_sentiment
from dependencies import limiter, require_service_key

router = APIRouter(tags=["NPC Interactions"])

@router.post(
    "/store_interaction/",
    response_model=NPCMemoryResponse,
    description="Player sends dialogue only. Sentiment is auto-analyzed and NPC reply is generated.",
    status_code=201
)
@limiter.limit(config.RATE_LIMITS["general"])
def store_interaction(
    request: Request, # Fix for slowapi crash
    data: NPCMemoryCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    _: None = Depends(require_service_key)
) -> NPCMemoryResponse:
    # Check for duplicate entry
    existing_entry = db.query(NPCMemory).filter(
        NPCMemory.player_id == data.player_id,
        NPCMemory.npc_id == data.npc_id,
        NPCMemory.dialogue == data.dialogue
    ).first()

    if existing_entry:
        raise HTTPException(status_code=400, detail="This interaction already exists.")

    if str(user.get("sub")) != str(data.player_id):
        raise HTTPException(status_code=403, detail="Not authorized for this player")

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

@router.get(
    "/get_interactions/{player_id}/{npc_id}",
    response_model=List[NPCMemoryResponse]
)
@limiter.limit(config.RATE_LIMITS["general"])
def get_interactions(
    request: Request, # Fix for slowapi crash
    player_id: int,
    npc_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    _: None = Depends(require_service_key)
) -> List[NPCMemoryResponse]:
    if str(user.get("sub")) != str(player_id):
        raise HTTPException(status_code=403, detail="Not authorized for this player")
    interactions = db.query(NPCMemory).filter(
        NPCMemory.player_id == player_id,
        NPCMemory.npc_id == npc_id
    ).order_by(NPCMemory.timestamp.desc()).all()

    if not interactions:
        raise HTTPException(status_code=404, detail="No interactions found for this player and NPC.")

    return interactions

@router.put(
    "/update_interaction/{id}",
    response_model=NPCMemoryResponse,
    description="Update player dialogue only. Sentiment and NPC reply are updated automatically."
)
@limiter.limit(config.RATE_LIMITS["general"])
def update_interaction(
    request: Request, # Fix for slowapi crash
    id: int,
    data: NPCMemoryUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    _: None = Depends(require_service_key)
) -> NPCMemoryResponse:
    npc_interaction = db.query(NPCMemory).filter(NPCMemory.id == id).first()

    if not npc_interaction:
        raise HTTPException(status_code=404, detail="Interaction not found.")

    if len(data.dialogue) > config.MAX_DIALOGUE_LENGTH:
        raise HTTPException(status_code=400, detail=f"Dialogue must be <= {config.MAX_DIALOGUE_LENGTH} characters")

    # Get player info
    player = PlayerService.get_player_by_id(db, npc_interaction.player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    if str(user.get("sub")) != str(player.id):
        raise HTTPException(status_code=403, detail="Not authorized for this player")
    
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

@router.delete(
    "/delete_interaction/{id}",
    response_model=NPCMemoryResponse,
    status_code=200
)
@limiter.limit(config.RATE_LIMITS["general"])
def delete_interaction(
    request: Request, # Fix for slowapi crash
    id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    _: None = Depends(require_service_key)
) -> NPCMemoryResponse:
    npc_interaction = db.query(NPCMemory).filter(NPCMemory.id == id).first()

    if not npc_interaction:
        raise HTTPException(status_code=404, detail="Interaction not found.")

    if str(user.get("sub")) != str(npc_interaction.player_id):
        raise HTTPException(status_code=403, detail="Not authorized for this player")

    # Capture the interaction before deletion for return 
    deleted_data = NPCMemoryResponse.model_validate(npc_interaction)

    db.delete(npc_interaction)
    db.commit()
    return deleted_data
