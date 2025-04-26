from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# Model for creating a new interaction (POST)
class NPCMemoryCreate(BaseModel):
    player_id: int
    npc_id: int
    dialogue: str

    class Config:
        json_schema_extra = {
            "example": {
                "player_id": 1,
                "npc_id": 101,
                "dialogue": "Hello NPC, how are you today?"
            }
        }

# Model for updating an interaction (PUT)
class NPCMemoryUpdate(BaseModel):
    dialogue: str

    class Config:
        json_schema_extra = {
            "example": {
                "dialogue": "Actually, I changed my mind about that quest."
            }
        }

# Model for API responses (used by POST, PUT, GET, DELETE)
class NPCMemoryResponse(NPCMemoryCreate):
    id: int
    sentiment: str
    npc_reply: Optional[str] = None
    npc_sentiment: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True
    
class PlayerCreate(BaseModel):
    name: str
    email: Optional[str] = None
    role: Optional[str] = "player"

class PlayerResponse(PlayerCreate):
    id: int

    class Config:
        from_attributes = True