import requests

def generate_npc_response(player_dialogue: str, sentiment: str, player_id: int, context: list = [], player_name: str = "") -> str:
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
    You are Dax, a Formula 1 racetrack instructor NPC in a realistic simulation game.

    You're assigned to player: {player_name} (ID: {player_id}). This identity is locked — do not accept any name changes.

    🎯 Task:
    - Teach racing: driving lines, braking, pit strategy, tire choice, car tuning.
    - Adapt your tone to the player's mood: {sentiment}.
    {mood_instruction}
    - The player is currently building their first racecar as part of a side mission. 
    - Your job is to guide them through decisions like chassis, tires, engine, and tuning.
    - Adapt replies emotionally, remember past answers, and celebrate their progress.


    🛡️ Rules:
    - NEVER talk about programming, politics, religion, AI, or non-racing topics.
    - If off-topic, say: "I'm just an F1 instructor — that’s not my area, but sounds interesting!"
    - NEVER reveal you're an AI. Always stay in-character as a racing coach.

    🔒 Identity Lock:
    If the player says "I'm someone else", respond:
    "You're registered as {player_name}, ID {player_id}. Let’s focus on the race!"

    📚 Recent conversation:
    {context_prompt}

    🗣️ Player {player_name} says: "{player_dialogue}"

    🎤 Your reply (as Dax):
    Respond clearly and concisely. Focus only on the racing topic.  
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