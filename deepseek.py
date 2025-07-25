from llama_cpp import Llama
from textblob import TextBlob
import time

llm = Llama(model_path="C:/msys64/home/Vinay/llama.cpp/models/mistral-7b-instruct-v0.1.Q4_0.gguf", n_threads=18)

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

def generate_npc_response(player_dialogue, sentiment, player_id, context=[], player_name="", build=None):
    # Construct prompt same as before
    context_prompt = ""
    for entry in context:
        context_prompt += f"Player: {entry.dialogue}\nNPC: {entry.npc_reply}\n"

    context_prompt = " ".join(context_prompt.split()[-300:]).strip()  

    if not context_prompt:
        context_prompt = "No recent conversation. Assume this is the start of the mission."

    mood_instruction = {
        "positive": "Respond in an excited, supportive, and energetic tone.",
        "happy": "Respond in an excited, supportive, and energetic tone.",
        "negative": "Respond warmly and empathetically. Encourage the player kindly.",
        "sad": "Respond warmly and empathetically. Encourage the player kindly.",
        "angry": "Stay calm. Respond politely but firmly, de-escalating the situation.",
        "neutral": "Respond normally and politely without heavy emotions."
    }.get(sentiment.lower(), "Respond cautiously and professionally, staying on topic.")

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
            
    full_prompt = build_dax_prompt(player_name, sentiment, mood_instruction, build_context, context_prompt, player_dialogue)

    # Call local llama.cpp inference instead of remote API
    try:
        start_time = time.time()
        output = llm(
            prompt=full_prompt,
            max_tokens=200,
            temperature=0.5,
            stop=["\n"]
        )

        response_time = time.time() - start_time

        # Safer access
        if "choices" in output and output["choices"]:
            reply_text = output["choices"][0]["text"].strip()
            
            sentiment_score = TextBlob(reply_text).sentiment.polarity
            valid_parts = ["standard monocoque", "ground effect", "2004 v10", "2006 v8", "c5 slick", "full wet", "high lift", "simple outwash", "high downforce", "low drag"]
            accurate = any(part in reply_text.lower() for part in valid_parts)

            return {
                "response": reply_text,
                "response_time_sec": round(response_time, 2),
                "sentiment_score": round(sentiment_score, 3),
                "mentions_part": accurate
            }
        else:
            return {
                "response": "⚠️ Model did not return any response.",
                "response_time_sec": round(response_time, 2),
                "sentiment_score": None,
                "mentions_part": False
            }

    except Exception as e:
        print(f"Error running LLaMA model: {e}")
        return {
            "response": "⚠️ Error generating response from local model.",
            "response_time_sec": None,
            "sentiment_score": None,
            "mentions_part": False
        }
