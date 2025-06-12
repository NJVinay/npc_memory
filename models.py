from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from datetime import datetime
from database import Base

class NPCMemory(Base):
    __tablename__ = "npc_memory"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, nullable=False)
    npc_id = Column(Integer, nullable=False)
    dialogue = Column(String, nullable=False)
    sentiment = Column(String, nullable=True)  # Stores emotion-based response type
    timestamp = Column(DateTime, default=datetime.utcnow)
    npc_reply = Column(String, nullable=True)
    npc_sentiment = Column(String, nullable=True)

class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, nullable=True)
    role = Column(String, default="player")
    display_name = Column(String, nullable=True)  # NEW: stores human-readable name

class CarBuild(Base):
    __tablename__ = "car_builds"
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    chassis = Column(String)
    engine = Column(String)
    tires = Column(String)
    frontWing = Column(String)
    rearWing = Column(String)
    car_image = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow) 
