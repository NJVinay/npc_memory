from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime
from database import Base

class NPCMemory(Base):
    __tablename__ = "npc_memory"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, nullable=False)
    npc_id = Column(Integer, nullable=False)
    dialogue = Column(Text, nullable=False)
    sentiment = Column(String, nullable=True)  # Stores emotion-based response type
    timestamp = Column(DateTime, default=datetime.utcnow)

npc_reply = Column(String, nullable=True)
npc_sentiment = Column(String, nullable=True)
