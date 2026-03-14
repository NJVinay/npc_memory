from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from config import config
from database import get_db
from auth import get_current_user
from schemas import ConsentCreate, ConsentResponse
from services import PlayerService, ConsentService
from dependencies import limiter

router = APIRouter(tags=["Evaluation"])

@router.post("/store_consent", response_model=ConsentResponse)
@limiter.limit(config.RATE_LIMITS["general"])
def store_consent(
    request: Request, # Fix for slowapi crash
    consent_data: ConsentCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
) -> ConsentResponse:
    """Store user consent data to database."""
    try:
        if str(user.get("sub")) != str(consent_data.player_id):
            raise HTTPException(status_code=403, detail="Not authorized for this player")

        # Verify player exists
        player = PlayerService.get_player_by_id(db, consent_data.player_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        
        # Use service to create consent record
        consent = ConsentService.create_consent(db, consent_data)
        
        print(f"📋 Consent stored to database for {consent.name} (Player {consent.player_id})")
        return consent
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error storing consent: {e}")
        raise HTTPException(status_code=500, detail=f"Error storing consent: {str(e)}")
