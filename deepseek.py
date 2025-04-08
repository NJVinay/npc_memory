import requests

def generate_npc_response(player_dialogue: str, sentiment: str) -> str:
    prompt = f"""You are an NPC in a game. The player just said: '{player_dialogue}'.
Respond appropriately with emotion and in-game character tone.
The player's emotion is: {sentiment}.
If the topic seems out of the game world, gently say:
"Hey, are we not going out of this context?" before continuing.

Respond in a natural, immersive way.
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "deepseek-chat",
            "prompt": prompt,
            "stream": False
        }
    )

    if response.status_code == 200:
        return response.json().get("response", "").strip()
    else:
        return "Sorry, I couldn’t respond right now."
