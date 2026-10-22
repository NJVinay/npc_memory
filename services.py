"""
Service layer for business logic separation.
Handles player management, chat operations, and build management.
"""

import os
import random
import bcrypt
from typing import Any, Dict, List, Optional, Sequence
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from config import config
from models import Player, NPCMemory, CarBuild, Consent, StudyAssignment
from schemas import PlayerCreate, ConsentCreate
from sentiment import analyze_sentiment
from llamacpp import generate_npc_response


# =============================================================================
# Player Service
# =============================================================================

class PlayerService:
    """Handles player-related operations."""
    
    @staticmethod
    def get_player_by_id(db: Session, player_id: int) -> Optional[Player]:
        """Get player by ID with error handling."""
        return db.query(Player).filter(Player.id == player_id).first()
    
    @staticmethod
    def get_player_by_uuid(db: Session, uuid: str) -> Optional[Player]:
        """Get player by UUID."""
        return db.query(Player).filter(Player.name == uuid).first()
    
    @staticmethod
    def create_player(db: Session, player_data: PlayerCreate) -> Player:
        """Create a new player, storing a bcrypt hash of the password if one is given."""
        # Player has no password/role columns; the password is stored as pin_hash
        fields = player_data.model_dump(exclude={"password", "role"})
        if player_data.password:
            fields["pin_hash"] = bcrypt.hashpw(
                player_data.password.encode('utf-8'), bcrypt.gensalt()
            ).decode('utf-8')

        try:
            new_player = Player(**fields)
            db.add(new_player)
            db.commit()
            db.refresh(new_player)
            return new_player
        except SQLAlchemyError as e:
            db.rollback()
            print(f"❌ Database error creating player: {e}")
            raise
    
    @staticmethod
    def create_player_with_credentials(
        db: Session,
        uuid: str,
        pin: str,
        display_name: str
    ) -> Player:
        """Create a player with hashed PIN credentials.
        
        Args:
            db: Database session
            uuid: Unique identifier for the player
            pin: Plain text PIN to be hashed
            display_name: Human-readable name
            
        Returns:
            Created Player object
        """
        # Hash PIN with bcrypt (secure salt included automatically)
        hashed_pin = bcrypt.hashpw(pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        try:
            new_player = Player(
                name=uuid,
                pin_hash=hashed_pin,
                display_name=display_name
            )
            db.add(new_player)
            db.commit()
            db.refresh(new_player)
            return new_player
        except SQLAlchemyError as e:
            db.rollback()
            print(f"❌ Database error creating player with credentials: {e}")
            raise
    
    @staticmethod
    def verify_player_credentials(db: Session, uuid: str, pin: str) -> Optional[Player]:
        """Verify player credentials with bcrypt (legacy UUID + PIN).
        
        Args:
            db: Database session
            uuid: Player's UUID
            pin: Plain text PIN to verify
            
        Returns:
            Player object if credentials valid, None otherwise
        """
        player = db.query(Player).filter(Player.name == uuid).first()
        
        if not player or not player.pin_hash:
            return None
        
        # Verify PIN with bcrypt
        try:
            if bcrypt.checkpw(pin.encode('utf-8'), player.pin_hash.encode('utf-8')):
                return player
        except (ValueError, AttributeError) as e:
            # Handle legacy SHA256 hashes or invalid formats
            print(f"⚠️ Legacy/invalid hash format for player {uuid}: {e}")
            pass
        
        return None
    
    @staticmethod
    def verify_player_email_password(db: Session, email: str, password: str) -> Optional[Player]:
        """Verify player credentials using email + password (OAuth fallback).
        
        Args:
            db: Database session
            email: Player's email address
            password: Plain text password to verify
            
        Returns:
            Player object if credentials valid, None otherwise
        """
        player = db.query(Player).filter(Player.email == email).first()
        
        if not player or not player.pin_hash:
            return None
        
        # Verify password with bcrypt
        try:
            if bcrypt.checkpw(password.encode('utf-8'), player.pin_hash.encode('utf-8')):
                return player
        except (ValueError, AttributeError) as e:
            print(f"⚠️ Invalid hash format for player {email}: {e}")
            pass
        
        return None
    
    @staticmethod
    def get_all_players(
        db: Session,
        skip: int = 0,
        limit: int = config.DEFAULT_PAGE_SIZE
    ) -> List[Player]:
        """Get all players with pagination.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of Player objects
        """
        return db.query(Player).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_player_count(db: Session) -> int:
        """Get total player count."""
        return db.query(Player).count()


# =============================================================================
# Chat Service
# =============================================================================

class ChatService:
    """Handles chat and NPC interaction operations."""

    # Turns kept out of Dax's memory: no reply was shown (llm_error) or the reply was canned (fallback)
    NOT_IN_MEMORY = ("llm_error", "fallback")

    @staticmethod
    def get_conversation_history(
        db: Session,
        player_id: int,
        limit: int = config.MAX_CONVERSATION_HISTORY,
        before_id: Optional[int] = None,
        npc_id: Optional[int] = None,
        exclude_statuses: Sequence[str] = ()
    ) -> List[NPCMemory]:
        """Get conversation history for a player (newest first, then reversed).

        Args:
            db: Database session
            player_id: Player's ID
            limit: Maximum number of messages to retrieve
            before_id: Only include messages created before this interaction
            npc_id: Only include turns with this NPC
            exclude_statuses: Leave out turns with these reply statuses

        Returns:
            List of NPCMemory objects in chronological order (oldest first)
        """
        query = db.query(NPCMemory).filter(NPCMemory.player_id == player_id)
        if before_id is not None:
            query = query.filter(NPCMemory.id < before_id)
        if npc_id is not None:
            query = query.filter(NPCMemory.npc_id == npc_id)
        if exclude_statuses:
            # Older rows have no status and count as ordinary replies
            query = query.filter(
                (NPCMemory.reply_status.is_(None)) | (NPCMemory.reply_status.notin_(exclude_statuses))
            )

        history = (
            query
            .order_by(NPCMemory.timestamp.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(history))

    @staticmethod
    def get_memory_for_prompt(db: Session, player_id: int, before_id: Optional[int] = None) -> List[NPCMemory]:
        """Dax's memory: earlier turns with Dax whose reply the player actually saw."""
        return ChatService.get_conversation_history(
            db, player_id,
            limit=config.MAX_CONVERSATION_HISTORY,
            before_id=before_id,
            npc_id=config.DEFAULT_NPC_ID,
            exclude_statuses=ChatService.NOT_IN_MEMORY
        )

    @staticmethod
    def _apply_npc_reply(memory: NPCMemory, result: Dict[str, Any]) -> None:
        """Copy a generate_npc_response result (reply, status and metrics) onto a memory row."""
        reply = result.get("response")
        response_time = result.get("response_time_sec")
        memory.npc_reply = reply
        memory.npc_sentiment = analyze_sentiment(reply) if reply else None
        memory.reply_status = result.get("status", "ok")
        memory.raw_reply = result.get("raw_reply")
        memory.mentions_part = result.get("mentions_part")
        memory.response_time_ms = int(response_time * 1000) if response_time is not None else None
        memory.llm_model = (
            f"{config.LLM_PROVIDER}:{config.LLM_MODEL}" if config.USE_EXTERNAL_LLM
            else f"local:{os.path.basename(config.MODEL_PATH)}"
        )

    @staticmethod
    def _generate(dialogue: str, sentiment: str, player_id: int, context: List[NPCMemory],
                  player_name: str, build: Optional[CarBuild]) -> Dict[str, Any]:
        try:
            return generate_npc_response(dialogue, sentiment, player_id, context, player_name, build=build)
        except Exception as e:
            print(f"⚠️ LLM generation failed: {e}")
            return {"response": None, "status": "llm_error"}

    @staticmethod
    def create_interaction(
        db: Session,
        player_id: int,
        npc_id: int,
        dialogue: str,
        context: List[NPCMemory],
        player_name: str,
        build: Optional[CarBuild] = None,
        source: str = "typed"
    ) -> NPCMemory:
        """Create a new chat interaction with NPC response.

        Args:
            db: Database session
            player_id: Player's ID
            npc_id: NPC's ID
            dialogue: Player's message
            context: Conversation history
            player_name: Player's display name
            build: Optional car build for context
            source: How the message was produced: "typed" or "part_click"

        Returns:
            Created NPCMemory object. A turn where the LLM failed is still stored,
            with reply_status "llm_error" and no npc_reply.
        """
        player_sentiment = analyze_sentiment(dialogue)
        result = ChatService._generate(dialogue, player_sentiment, player_id, context, player_name, build)

        memory = NPCMemory(
            player_id=player_id,
            npc_id=npc_id,
            dialogue=dialogue,
            sentiment=player_sentiment,
            source=source
        )
        ChatService._apply_npc_reply(memory, result)

        try:
            db.add(memory)
            db.commit()
            db.refresh(memory)
            return memory
        except SQLAlchemyError as e:
            db.rollback()
            print(f"❌ Database error creating interaction: {e}")
            raise

    @staticmethod
    def update_interaction(
        db: Session,
        memory: NPCMemory,
        dialogue: str,
        context: List[NPCMemory],
        player_name: str,
        build: Optional[CarBuild] = None
    ) -> Optional[NPCMemory]:
        """Replace the player's message on an existing turn and regenerate the NPC reply.

        Returns None, leaving the turn unchanged, if the LLM produced no reply.
        """
        sentiment = analyze_sentiment(dialogue)
        result = ChatService._generate(dialogue, sentiment, memory.player_id, context, player_name, build)
        if result.get("status") == "llm_error":
            return None

        memory.dialogue = dialogue
        memory.sentiment = sentiment
        ChatService._apply_npc_reply(memory, result)

        try:
            db.commit()
            db.refresh(memory)
            return memory
        except SQLAlchemyError as e:
            db.rollback()
            print(f"❌ Database error updating interaction: {e}")
            raise

    @staticmethod
    def log_static_turn(
        db: Session,
        player_id: int,
        choice: str,
        npc_reply: Optional[str],
        source: str = "static_option"
    ) -> NPCMemory:
        """Record one TurboTom exchange: the option chosen (or advanced by a part pick) and TurboTom's scripted answer."""
        memory = NPCMemory(
            player_id=player_id,
            npc_id=config.STATIC_NPC_ID,
            dialogue=choice,
            npc_reply=npc_reply,
            source=source,
            reply_status="scripted"
        )
        try:
            db.add(memory)
            db.commit()
            db.refresh(memory)
            return memory
        except SQLAlchemyError as e:
            db.rollback()
            print(f"❌ Database error logging TurboTom turn: {e}")
            raise


# =============================================================================
# Study Service
# =============================================================================

class StudyService:
    """Study consent and the Dax / TurboTom condition each player is assigned to."""

    @staticmethod
    def has_valid_consent(db: Session, player_id: int) -> bool:
        """True if the player has given all three required consents."""
        return db.query(Consent.id).filter(
            Consent.player_id == player_id,
            Consent.consent_participate.is_(True),
            Consent.consent_data.is_(True),
            Consent.consent_age.is_(True)
        ).first() is not None

    @staticmethod
    def get_condition(db: Session, player_id: int) -> Optional[str]:
        assignment = db.get(StudyAssignment, player_id)
        return assignment.condition if assignment else None

    @staticmethod
    def get_or_assign_condition(db: Session, player_id: int) -> str:
        """Return the player's condition, assigning one the first time.

        A player who already talked to Dax before assignments were recorded stays
        with Dax (reason "prior_dax_history", so analysis can tell them apart).
        Everyone else goes to the condition with fewer participants so far (ties
        broken at random), which keeps the two groups the same size.
        """
        existing = StudyService.get_condition(db, player_id)
        if existing:
            return existing

        seen_dax = db.query(NPCMemory.id).filter(
            NPCMemory.player_id == player_id,
            NPCMemory.npc_id == config.DEFAULT_NPC_ID
        ).first() is not None
        if seen_dax:
            condition, reason = "dax", "prior_dax_history"
        else:
            counts = dict(
                db.query(StudyAssignment.condition, func.count())
                .group_by(StudyAssignment.condition)
                .all()
            )
            fewest = min(counts.get(c, 0) for c in config.STUDY_CONDITIONS)
            condition = random.choice([c for c in config.STUDY_CONDITIONS if counts.get(c, 0) == fewest])
            reason = "balanced"

        db.add(StudyAssignment(player_id=player_id, condition=condition, reason=reason))
        try:
            db.commit()
        except IntegrityError:
            # A concurrent request assigned this player first; keep that assignment
            db.rollback()
            return StudyService.get_condition(db, player_id)
        return condition


# =============================================================================
# Build Service
# =============================================================================

class BuildService:
    """Handles car build operations."""
    
    @staticmethod
    def get_latest_build(db: Session, player_id: int) -> Optional[CarBuild]:
        """Get the most recent car build for a player.
        
        Args:
            db: Database session
            player_id: Player's ID
            
        Returns:
            CarBuild object or None if no builds exist
        """
        return (
            db.query(CarBuild)
            .filter(CarBuild.player_id == player_id)
            .order_by(CarBuild.id.desc())
            .first()
        )
    
    @staticmethod
    def get_player_builds(
        db: Session,
        player_id: int,
        skip: int = 0,
        limit: int = config.DEFAULT_PAGE_SIZE
    ) -> List[CarBuild]:
        """Get all builds for a player with pagination.
        
        Args:
            db: Database session
            player_id: Player's ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of CarBuild objects
        """
        return (
            db.query(CarBuild)
            .filter(CarBuild.player_id == player_id)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    @staticmethod
    def create_build(
        db: Session,
        player_id: int,
        chassis: str,
        engine: str,
        tires: str,
        front_wing: str,
        rear_wing: str
    ) -> CarBuild:
        """Create a new car build.
        
        Args:
            db: Database session
            player_id: Player's ID
            chassis: Chassis component
            engine: Engine component
            tires: Tires component
            front_wing: Front wing component
            rear_wing: Rear wing component
            
        Returns:
            Created CarBuild object
        """
        try:
            build = CarBuild(
                player_id=player_id,
                chassis=chassis,
                engine=engine,
                tires=tires,
                front_wing=front_wing,
                rear_wing=rear_wing
            )
            
            db.add(build)
            db.commit()
            db.refresh(build)
            
            return build
        except SQLAlchemyError as e:
            db.rollback()
            print(f"❌ Database error creating build: {e}")
            raise


# =============================================================================
# Consent Service
# =============================================================================

class ConsentService:
    """Handles consent and study participation data."""
    
    @staticmethod
    def create_consent(db: Session, consent_data: ConsentCreate) -> Consent:
        """Create a new consent record.

        Args:
            db: Database session
            consent_data: Validated consent data

        Returns:
            Created Consent object. Raises IntegrityError if the player already
            has a consent record for this study.
        """
        try:
            # One record per player per study: the study id is set here, not by the client
            consent = Consent(**consent_data.model_dump(exclude={"study_uuid"}), study_uuid=config.STUDY_ID)
            db.add(consent)
            db.commit()
            db.refresh(consent)
            return consent
        except SQLAlchemyError as e:
            db.rollback()
            print(f"❌ Database error creating consent for player {consent_data.player_id}: {type(e).__name__}")
            raise
    
    @staticmethod
    def get_player_consents(db: Session, player_id: int) -> List[Consent]:
        """Get all consent records for a player.
        
        Args:
            db: Database session
            player_id: Player's ID
            
        Returns:
            List of Consent objects
        """
        return (
            db.query(Consent)
            .filter(Consent.player_id == player_id)
            .order_by(Consent.created_at.desc())
            .all()
        )
