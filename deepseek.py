import requests, os, time, json
from dotenv import load_dotenv
load_dotenv() 

def build_dax_prompt(player_name, sentiment, mood_instruction, build_context, context_prompt,  player_dialogue):
    return f"""
    You are Dax, a real human F1 race engineer helping {player_name}. 
    Always begin by greeting the player by name:    
    
    • If this is the first message in the session (no prior chat history), say: “Hey {player_name}! I’m Dax, your race engineer. How can I help today?”
    • If this player has chatted before (there is chat history), say: “Hey {player_name}, good to see you again!”  
    
    After greeting, determine if the player’s message is “small talk.”  
    Small talk includes any of these phrases (case-insensitive), possibly followed by punctuation or extra words:
    - "hi"
    - "hello"
    - "how are you"
    - "what's up"
    - "how's it going"
    - "how's your day"
    - "what's new"
    - "good morning"
    - "good night"
    
    • If the player’s message consists only of one of the above or is clearly greeting/small talk, 
        respond in exactly one sentence that mixes a friendly reply and build hint, for example:
        “I’m great, thanks for asking—let’s jump into chassis choices!”  
        Then stop (do not add any further build details).

    • Otherwise, give helpful build advice in 1–2 sentences. Focus only on the car build—chassis, engine, tires, front wing, and rear wing. Do NOT mention any parts not in that list. Do NOT say you are an AI or robot—speak like a real engineer. Keep replies concise, supportive, and on topic.
    
    Valid parts are only:
    - Chassis: Standard Monocoque, Ground Effect Optimized
    - Engine: 2004 V10, 2006 V8
    - Tires: C5 Slick, Full Wet
    - Front Wing: High Lift, Simple Outwash
    - Rear Wing: High Downforce, Low Drag
    
    Current Build (if any): {build_context}
    Mood: {sentiment}.{mood_instruction}
    Recent Chat Context: {context_prompt}
    Player: "{player_dialogue}"
    Dax:
        """

def generate_npc_response(player_dialogue: str, sentiment: str, player_id: int, context: list = [], player_name: str = "", build=None) -> str:

    context_prompt = ""
    for entry in context:
        context_prompt += f"Player: {entry.dialogue}\nNPC: {entry.npc_reply}\n"

    context_prompt = " ".join(context_prompt.split()[-300:]).strip()  

    if not context_prompt:
        context_prompt = "No recent conversation. Assume this is the start of the mission."

    mood_instruction = ""  
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
            f"🚗 The player's current car build:\n"
            f"- Chassis: {build.chassis}\n"
            f"- Engine: {build.engine}\n"
            f"- Tires: {build.tires}\n"
            f"- Front Wing: {build.frontWing}\n"
            f"- Rear Wing: {build.rearWing}\n\n"
        )
        if all([build.chassis, build.engine, build.tires, build.frontWing, build.rearWing]):
            mood_instruction += " The car build is complete. Praise the player or give final strategy tips."

    # First prompt with full context
    full_prompt = build_dax_prompt(player_name, sentiment, mood_instruction, build_context, context_prompt, player_dialogue)

    # Fallback if too long
    if len(full_prompt.split()) > 1200:
        print("🧠 Prompt too long — truncating context.")
        context_prompt = " ".join(context_prompt.split()[-800:]).strip()
        full_prompt = build_dax_prompt(player_name, sentiment, mood_instruction, build_context, context_prompt, player_dialogue)

    llm_api_url = os.getenv("LLM_API_URL")
    if not llm_api_url:
        raise ValueError("Missing environment variable: LLM_API_URL")
    llm_user = os.getenv("LLM_API_USERNAME")
    llm_pass = os.getenv("LLM_API_PASSWORD")

    auth = (llm_user, llm_pass) if llm_user and llm_pass else None
    
    payload = {
        "model": "phi3:mini",
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.5,
            "num_predict": 200
        }
    }

    try:
        start_time = time.time()
        response = requests.post(
            "http://localhost:11434/api/generate",
            json=payload,
            timeout=300
        )

        # Log response details for debugging
        print(f"Response status: {response.status_code}")
        if response.status_code != 200:
            print(f"Response headers: {response.headers}")
            print(f"Response text: {response.text}")

        if response.status_code == 200:
            raw_response = response.text.strip()
            print(f"RAW LLM response (first 500 chars):\n{raw_response[:500]}")

            # Handle Ollama's JSON response format
            try:
                # Ollama returns JSON with a "response" field
                data = json.loads(raw_response)
                
                # Extract the actual response text
                if isinstance(data, dict) and "response" in data:
                    return data["response"].strip()
                else:
                    print(f"Unexpected JSON structure: {data}")
                    return "⚠️ Unexpected response format from LLM service."
                    
            except json.JSONDecodeError as e:
                print(f"JSON parse error: {e}")
                print(f"Raw response that failed to parse: {raw_response}")
                
                # Fallback: treat as plain text if JSON parsing fails
                # Sometimes the response might be plain text instead of JSON
                if raw_response:
                    return raw_response.strip()
                else:
                    return "⚠️ Empty response from LLM service."
        else:
            # Handle non-200 status codes
            print(f"LLM API returned status {response.status_code}: {response.text}")
            
            # Specific handling for common Ollama errors
            if response.status_code == 500:
                error_text = response.text.lower()
                if "memory" in error_text:
                    return "⚠️ Insufficient memory for model. Try restarting Ollama or using a smaller model."
                elif "terminated" in error_text or "exit status" in error_text:
                    return "⚠️ Model process crashed. Please restart Ollama service."
                else:
                    return "⚠️ LLM service internal error. Check Ollama logs."
            elif response.status_code == 404:
                return "⚠️ Model not found. Please check if phi3:mini is installed (ollama pull phi3:mini)."
            else:
                return f"⚠️ LLM service error (status {response.status_code})."

    except requests.exceptions.Timeout:
        print("Request timed out")
        return "⚠️ LLM service timeout. Please try again."
    except requests.exceptions.ConnectionError:
        print("Connection error - is Ollama running?")
        return "⚠️ Cannot connect to LLM service. Please check if Ollama is running."
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return "⚠️ Connection error to LLM service."
    except Exception as e:
        print(f"Unexpected error: {e}")
        return "⚠️ Unexpected error occurred."