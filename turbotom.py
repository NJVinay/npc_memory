from models import CarBuild
from sqlalchemy.orm import Session
import re

# Define keyword-based rules
RESPONSE_RULES = {
    "engine": {
        "turbo": "Turbo’s fast but burns out easy. You sure you can handle it?",
        "v8": "Good call! V8s are heavy but reliable."
    },
    "tires": {
        "slick": "Slicks grip the track like a dream — if it’s dry.",
        "wet": "Rainy day? Wet tires are the way to go."
    },
    "spoiler": {
        "none": "No spoiler? You might lose traction at high speeds.",
        "carbon fiber": "Now we’re talking! That’ll keep you glued to the road."
    },
    "chassis": {
        "standard": "Sturdy choice. Nothing flashy, but it works.",
        "lightweight": "Lightweight’s fast — but don’t crash, or it’s over."
    }
}

def get_latest_build(player_id: int, db: Session):
    return db.query(CarBuild).filter(CarBuild.player_id == player_id).order_by(CarBuild.id.desc()).first()

def turbotom_response(dialogue: str, player_id: int, db: Session) -> str:
    dialogue = dialogue.lower()
    build = get_latest_build(player_id, db)
    
    # Intent: Ask about parts
    if any(kw in dialogue for kw in ["engine", "v8", "turbo"]):
        return RESPONSE_RULES["engine"].get(build.engine.lower(), "Pick wisely — speed’s nothing without control.") if build else "Pick your engine first!"
    if any(kw in dialogue for kw in ["tire", "slick", "wet"]):
        return RESPONSE_RULES["tires"].get(build.tires.lower(), "Tires decide traction. Choose carefully.") if build else "Choose tires before asking!"
    if any(kw in dialogue for kw in ["spoiler", "aero", "wing"]):
        return RESPONSE_RULES["spoiler"].get(build.spoiler.lower(), "Spoilers keep you grounded.") if build else "Pick a spoiler first!"
    if any(kw in dialogue for kw in ["chassis", "frame", "body"]):
        return RESPONSE_RULES["chassis"].get(build.chassis.lower(), "Chassis is your foundation.") if build else "Pick a chassis first!"
    
    # Intent: Build complete
    if any(kw in dialogue for kw in ["done", "start", "ready"]):
        return "Got guts, huh? Let’s see what this beast can do."

    # Intent: Help/restart
    if any(kw in dialogue for kw in ["help", "lost", "confused", "restart"]):
        return "Step one: pick a chassis. Then engine, tires, and spoiler. I’ve got your back."

    return "Hmm... I don’t quite follow. Try asking about your car parts or tell me if you’re done."

