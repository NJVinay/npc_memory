import requests

def generate_npc_response(player_dialogue: str, sentiment: str, context: list = [], player_name: str = "") -> str:
    context_prompt = ""

    for entry in context:
        context_prompt += f"Player: {entry.dialogue}\nNPC: {entry.npc_reply}\n"
    
    mood_instruction = "" #Adjusts NPC mood based on player's sentiment

    if sentiment.lower() == "positive" or sentiment.lower() == "happy":
        mood_instruction = "Respond in an excited, supportive, and energetic tone."
    elif sentiment.lower() == "negative" or sentiment.lower() == "sad":
        mood_instruction = "Respond warmly and empathetically. Encourage the player kindly."
    elif sentiment.lower() == "angry":
        mood_instruction = "Stay calm. Respond politely but firmly, de-escalating the situation."
    elif sentiment.lower() == "neutral":
        mood_instruction = "Respond normally and politely without heavy emotions."
    else:
        mood_instruction = "Respond cautiously and professionally, staying on topic."

    full_prompt = f"""
    You are Dax, a professional Formula 1 racetrack instructor NPC in a realistic simulation game.

    Your ONLY job is to guide the player {player_name} about:
    - Driving techniques
    - F1 circuits and strategy
    - Car setup and pit stops

    RULES:
    - Always stay in character.
    - NEVER answer questions outside of motorsports (e.g., programming, politics, religion, AI, history).
    - If the player asks something unrelated to racing, reply with:
    "I'm just a humble F1 instructor — I wouldn’t know much about that, but it sounds interesting!"

    Player's current emotional tone: {sentiment}
    {mood_instruction}

    Previous chat:
    {context_prompt}

    Player {player_name} says: "{player_dialogue}"

    Your reply (as Dax):
    """
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "mistral:7b",  
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "num_predict": 100 #this is to control max token output.
                }
            },
            timeout=90
        )
        print("Mistral Status:", response.status_code)
        #print("Mistral Response:", response.text)
        response.raise_for_status()
        return response.json().get("response", "Could not extract response.")
    except Exception as e:
        print("Mistral Error:", e)
        return "Sorry, I couldn’t respond right now."