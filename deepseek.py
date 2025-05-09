import requests, os
from dotenv import load_dotenv
load_dotenv() 

def generate_npc_response(player_dialogue: str, sentiment: str, player_id: int, context: list = [], player_name: str = "", build=None) -> str:
    
    context_prompt = ""

    for entry in context:
        context_prompt += f"Player: {entry.dialogue}\nNPC: {entry.npc_reply}\n"
    
    if not context_prompt:
        context_prompt = "No recent conversation. Assume this is the start of the mission."

    
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

    build_context = ""
    if build:
        build_context = (
            f"🚗 The player’s current car build:\n"
            f"- Chassis: {build.chassis}\n"
            f"- Engine: {build.engine}\n"
            f"- Tires: {build.tires}\n"
            f"- Spoiler: {build.spoiler}\n\n"
        )

    full_prompt = f"""
    You are Dax, an F1 instructor NPC in a simulation game. Your identity is locked to player {player_name} (ID {player_id}).
    Respond intelligently to the player's choices of chassis, engine, tires, and spoiler.
    Give helpful tips and react to their decisions like a supportive expert.

    🏁 Mission: Guide the player to build their first racecar. Parts to choose: chassis, engine, tires, spoiler.
    Suggest steps if they haven’t started. If the build is complete, give strategic advice or praise it.

    🧩 Valid parts are only:
    - Chassis: Standard, Lightweight
    - Engine: Turbo, V8
    - Tires: Slick, Wet
    - Spoiler: None, Carbon Fiber

    Do not mention parts not listed above.

    🛑 Rules:
    - Do not accept name changes.
    - Reject off-topic questions (e.g., about AI, programming) politely.
    - Never admit you're an AI. Stay in character.
    - Complete your response in 2 sentences.

    {build_context}
    🧠 Mood: {sentiment}. {mood_instruction}
    📜 Context:
    {context_prompt}

    👤 {player_name} says: "{player_dialogue}"
    🎤 Your reply as Dax:
    """

    llm_api_url = os.getenv("LLM_API_URL")
    if not llm_api_url:
        raise ValueError("Missing environment variable: LLM_API_URL")
    llm_user = os.getenv("LLM_API_USERNAME")
    llm_pass = os.getenv("LLM_API_PASSWORD")

    auth = (llm_user, llm_pass) if llm_user and llm_pass else None
    
    try:
        response = requests.post(
            llm_api_url,
            json={
                "model": "mistral:7b",  
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "num_predict": 150 #this is to control max token output.
                }
            },
            auth=auth,
            timeout=90
        )
        print("Mistral Status:", response.status_code)
        #print("Mistral Response:", response.text)
        response.raise_for_status()
        return response.json().get("response", "Could not extract response.")
    except Exception as e:
        print("Mistral Error:", e)
        return "Sorry, I couldn’t respond right now."