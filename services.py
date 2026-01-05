"""
Service layer for business logic separation.
Handles player management, chat operations, and build management.
"""

import bcrypt
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from config import config
from models import Player, NPCMemory, CarBuild, Consent
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
        """Create a new player."""
        try:
            new_player = Player(**player_data.model_dump())
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
    
    @staticmethod
    def get_conversation_history(
        db: Session,
        player_id: int,
        limit: int = config.MAX_CONVERSATION_HISTORY
    ) -> List[NPCMemory]:
        """Get conversation history for a player (newest first, then reversed).
        
        Args:
            db: Database session
            player_id: Player's ID
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of NPCMemory objects in chronological order (oldest first)
        """
        history = (
            db.query(NPCMemory)
            .filter(NPCMemory.player_id == player_id)
            .order_by(NPCMemory.timestamp.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(history))
    
    @staticmethod
    def create_interaction(
        db: Session,
        player_id: int,
        npc_id: int,
        dialogue: str,
        context: List[NPCMemory],
        player_name: str,
        build: Optional[CarBuild] = None
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
            
        Returns:
            Created NPCMemory object
        """
        # Analyze player sentiment
        player_sentiment = analyze_sentiment(dialogue)
        
        # Generate NPC response with error handling
        try:
            npc_reply_obj = generate_npc_response(
                dialogue,
                player_sentiment,
                player_id,
                context,
                player_name,
                build=build
            )
            npc_reply_text = (
                npc_reply_obj["response"]
                if isinstance(npc_reply_obj, dict)
                else str(npc_reply_obj)
            )
        except Exception as e:
            print(f"⚠️ LLM generation failed: {e}. Using fallback response.")
            npc_reply_text = f"Hey {player_name}! I'm having trouble with my systems right now. Let's talk about your F1 car build!"
        
        # Analyze NPC sentiment
        npc_sentiment = analyze_sentiment(npc_reply_text)
        
        # Create memory record
        try:
            memory = NPCMemory(
                player_id=player_id,
                npc_id=npc_id,
                dialogue=dialogue,
                sentiment=player_sentiment,
                npc_reply=npc_reply_text,
                npc_sentiment=npc_sentiment
            )
            
            db.add(memory)
            db.commit()
            db.refresh(memory)
            
            return memory
        except SQLAlchemyError as e:
            db.rollback()
            print(f"❌ Database error creating interaction: {e}")
            raise


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
            Created Consent object
        """
        try:
            consent = Consent(**consent_data.model_dump())
            db.add(consent)
            db.commit()
            db.refresh(consent)
            return consent
        except SQLAlchemyError as e:
            db.rollback()
            print(f"❌ Database error creating consent: {e}")
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
