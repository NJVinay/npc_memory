import time
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from sqlalchemy.orm import Session

from config import config
from database import get_db
from auth import get_current_user
from models import NPCMemory
from schemas import NPCMemoryCreate, NPCMemoryResponse, NPCMemoryUpdate, StaticTurnCreate
from services import ChatService, PlayerService, BuildService
from dependencies import limiter, player_or_ip, require_service_key, require_consent, require_condition

router = APIRouter(tags=["NPC Interactions"])

# How a chat message was produced: typed by the player, or sent automatically when they pick a part
CHAT_SOURCES = ("typed", "part_click")

@router.post(
    "/chat_api",
    description="Browser chat endpoint (chat.html). Dax replies using the player's recent conversation history and build."
)
@limiter.limit(config.RATE_LIMITS["chat_api"], key_func=player_or_ip)
def chat_api(
    request: Request, # Fix for slowapi crash
    player_id: int = Form(...),
    dialogue: str = Form(...),
    source: str = Form("typed"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
) -> dict:
    if str(user.get("sub")) != str(player_id):
        raise HTTPException(status_code=403, detail="Not authorized for this player")

    dialogue = dialogue.strip()
    if not dialogue:
        raise HTTPException(status_code=400, detail="Dialogue cannot be empty")
    if len(dialogue) > config.MAX_DIALOGUE_LENGTH:
        raise HTTPException(status_code=400, detail=f"Dialogue must be <= {config.MAX_DIALOGUE_LENGTH} characters")
    if source not in CHAT_SOURCES:
        raise HTTPException(status_code=400, detail=f"source must be one of {', '.join(CHAT_SOURCES)}")

    player = PlayerService.get_player_by_id(db, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    require_consent(db, player_id)
    require_condition(db, player_id, "dax")

    player_name = player.display_name or player.name or "Player"
    build = BuildService.get_latest_build(db, player_id)
    context = ChatService.get_memory_for_prompt(db, player_id)

    start = time.time()
    try:
        memory = ChatService.create_interaction(
            db, player_id, config.DEFAULT_NPC_ID, dialogue,
            context, player_name, build, source=source
        )
    except Exception as e:
        db.rollback()
        print(f"DB commit error (chat_api): {e}")
        raise HTTPException(status_code=500, detail="Database connection issue, consider a retry.")

    if memory.reply_status == "llm_error":
        # The turn is recorded, but there is no reply to show; chat.html offers a retry
        raise HTTPException(status_code=503, detail="Dax couldn't answer just now. Please try again.")

    return {
        "player_dialogue": dialogue,
        "npc_reply": memory.npc_reply,
        "sentiment": memory.sentiment,
        "reply_status": memory.reply_status,
        "generation_time": round(time.time() - start, 2)
    }

@router.post(
    "/log_static_turn",
    status_code=201,
    description="Records one TurboTom exchange (option chosen and scripted answer) for the study."
)
@limiter.limit(config.RATE_LIMITS["general"], key_func=player_or_ip)
def log_static_turn(
    request: Request, # Fix for slowapi crash
    turn: StaticTurnCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
) -> dict:
    if str(user.get("sub")) != str(turn.player_id):
        raise HTTPException(status_code=403, detail="Not authorized for this player")
    require_consent(db, turn.player_id)
    require_condition(db, turn.player_id, "static")

    memory = ChatService.log_static_turn(db, turn.player_id, turn.choice, turn.npc_reply, turn.source)
    return {"status": "logged", "id": memory.id}

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
    if str(user.get("sub")) != str(data.player_id):
        raise HTTPException(status_code=403, detail="Not authorized for this player")
    if data.npc_id != config.DEFAULT_NPC_ID:
        raise HTTPException(status_code=400, detail="Only conversations with Dax can be stored here")

    # Check for duplicate entry (a turn that failed doesn't count, so it can be retried)
    existing_entry = db.query(NPCMemory).filter(
        NPCMemory.player_id == data.player_id,
        NPCMemory.npc_id == data.npc_id,
        NPCMemory.dialogue == data.dialogue,
        (NPCMemory.reply_status.is_(None)) | (NPCMemory.reply_status != "llm_error")
    ).first()

    if existing_entry:
        raise HTTPException(status_code=400, detail="This interaction already exists.")

    # Get player and context
    player = PlayerService.get_player_by_id(db, data.player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    require_consent(db, data.player_id)
    require_condition(db, data.player_id, "dax")

    player_name = player.display_name or player.name or "Player"
    build = BuildService.get_latest_build(db, data.player_id)
    context = ChatService.get_memory_for_prompt(db, data.player_id)

    # Use service layer to create interaction
    try:
        npc_interaction = ChatService.create_interaction(
            db, data.player_id, data.npc_id, data.dialogue,
            context, player_name, build
        )
    except Exception as e:
        db.rollback()
        print(f"DB commit error (store_interaction): {e}")
        raise HTTPException(status_code=500, detail="Database connection issue, consider a retry.")

    if npc_interaction.reply_status == "llm_error":
        raise HTTPException(status_code=503, detail="Dax couldn't answer just now. Please try again.")
    return npc_interaction

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
    if npc_interaction.npc_id != config.DEFAULT_NPC_ID:
        # TurboTom turns are scripted records of what happened; they are never regenerated
        raise HTTPException(status_code=400, detail="Only conversations with Dax can be edited")
    require_consent(db, player.id)
    require_condition(db, player.id, "dax")

    player_name = player.display_name or player.name or "Player"
    build = BuildService.get_latest_build(db, npc_interaction.player_id)
    # Dax answers the edited message as it stood in the conversation: only earlier messages count
    context = ChatService.get_memory_for_prompt(db, npc_interaction.player_id, before_id=npc_interaction.id)

    try:
        updated = ChatService.update_interaction(db, npc_interaction, data.dialogue, context, player_name, build)
    except Exception as e:
        db.rollback()
        print(f"DB commit error (update_interaction): {e}")
        raise HTTPException(status_code=500, detail="Database connection issue, consider a retry.")

    if updated is None:
        # No reply was generated; the recorded turn is left as it was
        raise HTTPException(status_code=503, detail="Dax couldn't answer just now. Please try again.")
    return updated

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
