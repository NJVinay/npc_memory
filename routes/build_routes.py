from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, Form, Query
from sqlalchemy.orm import Session

from config import config
from database import get_db
from auth import get_current_user
from schemas import CarBuildResponse
from services import PlayerService, BuildService
from dependencies import limiter

router = APIRouter(tags=["Car Builds"])

@router.post("/save_car_build")
@limiter.limit(config.RATE_LIMITS["general"])
async def save_car_build(
    request: Request, # Fix for slowapi crash
    player_id: int = Form(...),
    chassis: str = Form(""),
    engine: str = Form(""),
    tires: str = Form(""),
    front_wing: str = Form("", alias="frontWing"),
    rear_wing: str = Form("", alias="rearWing"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
) -> dict:
    if str(user.get("sub")) != str(player_id):
        raise HTTPException(status_code=403, detail="Not authorized for this player")
    # Validate player exists
    player = PlayerService.get_player_by_id(db, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    try:
        # Convert empty strings to None
        chassis = chassis if chassis else None
        engine = engine if engine else None
        tires = tires if tires else None
        front_wing = front_wing if front_wing else None
        rear_wing = rear_wing if rear_wing else None
        
        build = BuildService.create_build(
            db, player_id, chassis, engine, tires,
            front_wing, rear_wing
        )
        return {"status": "success", "message": "Build saved successfully!", "build_id": build.id}
    except Exception as e:
        db.rollback()
        print(f"❌ Error saving build: {e}")
        raise HTTPException(status_code=500, detail="Database error while saving build.")

@router.get("/get_builds/{player_id}", response_model=List[CarBuildResponse])
@limiter.limit(config.RATE_LIMITS["general"])
def get_player_builds(
    request: Request, # Fix for slowapi crash
    player_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(config.DEFAULT_PAGE_SIZE, ge=1, le=config.MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
) -> List[CarBuildResponse]:
    if str(user.get("sub")) != str(player_id):
        raise HTTPException(status_code=403, detail="Not authorized for this player")
    builds = BuildService.get_player_builds(db, player_id, skip=skip, limit=limit)
    return builds if builds else []
