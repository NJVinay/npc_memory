from pydantic import BaseModel
from datetime import datetime

# Schema for storing NPC memory interactions
class NPCMemoryCreate(BaseModel):
    player_id: int
    npc_id: int
    dialogue: str
    sentiment: str

# Schema for returning NPC memory data
class NPCMemoryResponse(NPCMemoryCreate):
    id: int
    timestamp: datetime

    class Config:
        orm_mode = True

class NPCMemoryUpdate(BaseModel):
    dialogue: str
    sentiment: str