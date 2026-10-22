from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import config
from database import get_db
from auth import get_current_user
from schemas import ConsentCreate, ConsentResponse
from services import PlayerService, ConsentService, StudyService
from dependencies import limiter, player_or_ip

router = APIRouter(tags=["Evaluation"])

@router.post("/store_consent", response_model=ConsentResponse)
@limiter.limit(config.RATE_LIMITS["general"], key_func=player_or_ip)
def store_consent(
    request: Request, # Fix for slowapi crash
    consent_data: ConsentCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
) -> ConsentResponse:
    """Store the player's study consent (one record per player per study)."""
    if str(user.get("sub")) != str(consent_data.player_id):
        raise HTTPException(status_code=403, detail="Not authorized for this player")

    # Verify player exists
    player = PlayerService.get_player_by_id(db, consent_data.player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    # Also covers consent recorded before the study id was fixed (other study_uuid values)
    if StudyService.has_valid_consent(db, consent_data.player_id):
        raise HTTPException(status_code=409, detail="Consent is already recorded for this study")

    try:
        consent = ConsentService.create_consent(db, consent_data)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Consent is already recorded for this study")
    except Exception as e:
        db.rollback()
        # No str(e) in the response: SQL errors would echo the participant's details
        print(f"❌ Error storing consent for player {consent_data.player_id}: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Could not store consent")

    print(f"📋 Consent stored for player {consent.player_id}")
    return consent
