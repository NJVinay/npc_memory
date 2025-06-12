from sqlalchemy.orm import Session
from fastapi import HTTPException

TOM_TREE = {
    "start": {
        "npc": "Hey, rookie! Ready to build this machine?",
        "options": {
        "Let's go!": "chassis_step",
        "What is this?": "intro_info"
        }
    },
    "intro_info": {
        "npc": "I’m TurboTom, retired F1 engineer. I’ll guide you step-by-step.",
        "options": {"Let’s build!": "chassis_step"}
    },
    "chassis_step": {
        "npc": "First up: pick a chassis. Standard or Lightweight?",
        "options": {"Standard": "engine_step", "Lightweight": "engine_step"}
    },
    "engine_step": {
        "npc": "Great. Now choose your engine: Turbo or V8?",
        "options": {"Turbo": "tires_step", "V8": "tires_step"}
    },
    "tires_step": {
        "npc": "Tires next. Slick for dry, Wet for rain. Your call.",
        "options": {"Slick": "spoiler_step", "Wet": "spoiler_step"}
    },
    "spoiler_step": {
        "npc": "Last piece: spoiler. None or Carbon Fiber?",
        "options": {"None": "final_step", "Carbon Fiber": "final_step"}
    },
    "final_step": {
        "npc": "All set! Good luck on the track—don’t forget to warm up those tires!",
        "options": {}
    }
}

# in-memory state per player (for demo only—consider DB in long run)
PLAYER_STATE = {}

def turbotom_response(dialogue: str, player_id: int, db: Session) -> str:
    # initialize state
    state = PLAYER_STATE.get(player_id, "start")
    node = TOM_TREE.get(state)
    if not node:
        raise HTTPException(500, "TurboTom state error.")

    # if user reply matches an option label, advance
    for label, next_state in node["options"].items():
        if dialogue.strip().lower() == label.lower():
            PLAYER_STATE[player_id] = next_state
            node = TOM_TREE[next_state]
            return node["npc"]
    # fallback
    return node["npc"]