from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# NPC Memory Schemas
# =============================================================================

class NPCMemoryCreate(BaseModel):
    """Schema for creating a new NPC interaction."""
    player_id: int = Field(..., gt=0, description="ID of the player")
    npc_id: int = Field(..., gt=0, description="ID of the NPC")
    dialogue: str = Field(..., min_length=1, max_length=5000, description="Player's dialogue")
    
    @field_validator('dialogue')
    @classmethod
    def validate_dialogue(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Dialogue cannot be empty or whitespace only")
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "player_id": 1,
                "npc_id": 101,
                "dialogue": "Hello Dax, I need help choosing an engine for my F1 car."
            }
        }

class NPCMemoryUpdate(BaseModel):
    """Schema for updating an NPC interaction."""
    dialogue: str = Field(..., min_length=1, max_length=5000, description="Updated player dialogue")
    
    @field_validator('dialogue')
    @classmethod
    def validate_dialogue(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Dialogue cannot be empty or whitespace only")
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "dialogue": "Actually, I'd like to ask about tire choices instead."
            }
        }

class NPCMemoryResponse(NPCMemoryCreate):
    """Schema for NPC interaction responses (includes all fields)."""
    id: int = Field(..., description="Unique interaction ID")
    sentiment: str = Field(..., description="Detected player sentiment")
    npc_reply: Optional[str] = Field(None, description="NPC's response")
    npc_sentiment: Optional[str] = Field(None, description="NPC response sentiment")
    timestamp: datetime = Field(..., description="When the interaction occurred")

    class Config:
        from_attributes = True


# =============================================================================
# Player Schemas
# =============================================================================

class PlayerCreate(BaseModel):
    """Schema for creating a new player."""
    name: str = Field(..., min_length=1, max_length=255, description="Unique player identifier")
    email: Optional[str] = Field(None, max_length=255, description="Player email (optional)")
    role: Optional[str] = Field("player", max_length=50, description="Player role")
    display_name: Optional[str] = Field(None, max_length=255, description="Human-readable display name")
    
    @field_validator('name', 'display_name')
    @classmethod
    def validate_name_fields(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Name fields cannot be empty or whitespace only")
        return v.strip() if v else v


class PlayerResponse(BaseModel):
    """Schema for player responses."""
    id: int = Field(..., description="Unique player ID")
    name: str = Field(..., description="Player's unique identifier")
    email: Optional[str] = Field(None, description="Player email")
    role: Optional[str] = Field(None, description="Player role")
    display_name: Optional[str] = Field(None, description="Player's display name")

    class Config:
        from_attributes = True


# =============================================================================
# Car Build Schemas
# =============================================================================

class CarBuildResponse(BaseModel):
    """Schema for car build responses."""
    id: int = Field(..., description="Unique build ID")
    player_id: int = Field(..., description="Player ID who created the build")
    chassis: Optional[str] = Field(None, description="Chassis type")
    engine: Optional[str] = Field(None, description="Engine type")
    tires: Optional[str] = Field(None, description="Tire type")
    front_wing: Optional[str] = Field(None, description="Front wing configuration")
    rear_wing: Optional[str] = Field(None, description="Rear wing configuration")
    created_at: datetime = Field(..., description="When the build was created")

    class Config:
        from_attributes = True


# =============================================================================
# Consent Schemas
# =============================================================================

class ConsentCreate(BaseModel):
    """Schema for creating a new consent record."""
    player_id: int = Field(..., gt=0, description="ID of the player")
    study_uuid: str = Field(..., min_length=1, max_length=255, description="Unique study identifier")
    name: str = Field(..., min_length=1, max_length=255, description="Participant's full name")
    course: Optional[str] = Field(None, max_length=100, description="Academic course")
    bth_email: Optional[str] = Field(None, max_length=255, description="BTH email address")
    gender: Optional[str] = Field(None, max_length=50, description="Gender")
    current_year: Optional[str] = Field(None, max_length=50, description="Current academic year")
    origin: Optional[str] = Field(None, max_length=100, description="Country of origin")
    gaming_experience: Optional[str] = Field(None, max_length=50, description="Gaming experience level")
    ai_familiarity: Optional[str] = Field(None, max_length=50, description="AI familiarity level")
    consent_participate: bool = Field(..., description="Consent to participate in study")
    consent_data: bool = Field(..., description="Consent to data collection")
    consent_age: bool = Field(..., description="Confirmation of legal age")
    consent_future: bool = Field(False, description="Consent for future contact")
    consent_results: bool = Field(False, description="Consent to receive results")
    
    @field_validator('name', 'study_uuid')
    @classmethod
    def validate_required_strings(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Required fields cannot be empty")
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "player_id": 1,
                "study_uuid": "550e8400-e29b-41d4-a716-446655440000",
                "name": "John Doe",
                "consent_participate": True,
                "consent_data": True,
                "consent_age": True
            }
        }


class ConsentResponse(BaseModel):
    """Schema for consent record responses."""
    id: int = Field(..., description="Unique consent record ID")
    player_id: int = Field(..., description="Player ID")
    study_uuid: str = Field(..., description="Study UUID")
    name: str = Field(..., description="Participant name")
    course: Optional[str] = Field(None, description="Course")
    bth_email: Optional[str] = Field(None, description="BTH email")
    gender: Optional[str] = Field(None, description="Gender")
    current_year: Optional[str] = Field(None, description="Academic year")
    origin: Optional[str] = Field(None, description="Origin")
    gaming_experience: Optional[str] = Field(None, description="Gaming experience")
    ai_familiarity: Optional[str] = Field(None, description="AI familiarity")
    consent_participate: bool = Field(..., description="Participation consent")
    consent_data: bool = Field(..., description="Data consent")
    consent_age: bool = Field(..., description="Age confirmation")
    consent_future: bool = Field(..., description="Future contact consent")
    consent_results: bool = Field(..., description="Results consent")
    created_at: datetime = Field(..., description="When consent was recorded")
    
    class Config:
        from_attributes = True
