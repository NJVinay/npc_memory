from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class NPCMemory(Base):
    """Store NPC conversation memories with sentiment analysis."""
    __tablename__ = "npc_memory"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    npc_id = Column(Integer, nullable=False, index=True)
    dialogue = Column(Text, nullable=False)
    sentiment = Column(String(20), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    npc_reply = Column(Text, nullable=True)
    npc_sentiment = Column(String(20), nullable=True)
    # typed, part_click (automatic message when a part is picked) or static_option (TurboTom choice)
    source = Column(String(20), nullable=True)
    # ok, off_topic (flagged, not changed), fallback (canned reply), llm_error or scripted; NULL on older rows
    reply_status = Column(String(20), nullable=True)
    raw_reply = Column(Text, nullable=True)  # LLM output before cleanup
    llm_model = Column(String(100), nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    mentions_part = Column(Boolean, nullable=True)

    # Relationship
    player = relationship("Player", back_populates="memories")
    
    # Composite index for common query pattern
    __table_args__ = (
        Index('ix_player_npc_timestamp', 'player_id', 'npc_id', 'timestamp'),
    )
    
    def __repr__(self) -> str:
        return f"<NPCMemory(id={self.id}, player_id={self.player_id}, npc_id={self.npc_id}, timestamp={self.timestamp})>"


class Player(Base):
    """Store player information and credentials."""
    __tablename__ = "players"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), unique=True, index=True, nullable=False)  # Account ID
    email = Column(String(255), unique=True, index=True, nullable=True)  # Unique email for OAuth
    pin_hash = Column(Text, nullable=True)  # Bcrypt hash for email+password auth
    display_name = Column(String(255), nullable=True)  # User's real name
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    # OAuth identity this account signs in with (google/github + the provider's stable user id)
    oauth_provider = Column(String(20), nullable=True)
    oauth_subject = Column(String(255), nullable=True)

    # Relationships
    memories = relationship("NPCMemory", back_populates="player", lazy="dynamic", cascade="all, delete-orphan")
    builds = relationship("CarBuild", back_populates="player", lazy="dynamic", cascade="all, delete-orphan")
    consent_records = relationship("Consent", back_populates="player", lazy="dynamic", cascade="all, delete-orphan")
    assignment = relationship("StudyAssignment", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Player(id={self.id}, name='{self.name}', display_name='{self.display_name}')>"


class CarBuild(Base):
    """Store player car build configurations."""
    __tablename__ = "car_builds"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    chassis = Column(String(100), nullable=True)
    engine = Column(String(100), nullable=True)
    tires = Column(String(100), nullable=True)
    front_wing = Column(String(100), nullable=True)  # Fixed: snake_case
    rear_wing = Column(String(100), nullable=True)   # Fixed: snake_case
    car_image = Column(String(500), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    # Relationship
    player = relationship("Player", back_populates="builds")
    
    def __repr__(self) -> str:
        return f"<CarBuild(id={self.id}, player_id={self.player_id}, chassis='{self.chassis}', engine='{self.engine}')>" 


class StudyAssignment(Base):
    """The study condition (dax or static) a player was assigned to. Set once, never re-drawn."""
    __tablename__ = "study_assignments"

    player_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), primary_key=True)
    condition = Column(String(20), nullable=False, index=True)
    # balanced (drawn for group balance) or prior_dax_history (had talked to Dax before assignments existed)
    reason = Column(String(30), nullable=True)
    assigned_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self) -> str:
        return f"<StudyAssignment(player_id={self.player_id}, condition='{self.condition}')>"


class Consent(Base):
    """Store user consent and study participation data."""
    __tablename__ = "consent_data"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    study_uuid = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    course = Column(String(100), nullable=True)
    bth_email = Column(String(255), nullable=True)
    gender = Column(String(50), nullable=True)
    current_year = Column(String(50), nullable=True)
    origin = Column(String(100), nullable=True)
    gaming_experience = Column(String(50), nullable=True)
    ai_familiarity = Column(String(50), nullable=True)
    consent_participate = Column(Boolean, default=False, nullable=False)
    consent_data = Column(Boolean, default=False, nullable=False)
    consent_age = Column(Boolean, default=False, nullable=False)
    consent_future = Column(Boolean, default=False, nullable=False)
    consent_results = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    # Relationship
    player = relationship("Player", back_populates="consent_records", lazy="joined")
    
    # Unique constraint: one consent per player per study
    __table_args__ = (
        UniqueConstraint('player_id', 'study_uuid', name='uix_player_study_consent'),
    )
    
    def __repr__(self) -> str:
        return f"<Consent(id={self.id}, player_id={self.player_id}, study_uuid='{self.study_uuid}', name='{self.name}')>"
