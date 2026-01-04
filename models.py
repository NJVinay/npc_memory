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
    name = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), nullable=True)
    role = Column(Text, default="player")  # Stores bcrypt hash or role - Text for flexibility
    display_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    memories = relationship("NPCMemory", back_populates="player", lazy="dynamic", cascade="all, delete-orphan")
    builds = relationship("CarBuild", back_populates="player", lazy="dynamic", cascade="all, delete-orphan")
    consent_records = relationship("Consent", back_populates="player", lazy="dynamic", cascade="all, delete-orphan")
    
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
