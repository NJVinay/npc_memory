from llama_cpp import Llama
from textblob import TextBlob
import time

# Use a smaller Q2_K model that uses ~2GB RAM instead of 4GB
llm = Llama(
    model_path="./models/mistral-7b-instruct-v0.1.Q2_K.gguf", 
    n_threads=18,
    n_ctx=1024,  # Smaller context to save RAM
    n_batch=512,  # Process more tokens at once
    verbose=False,
    use_mlock=True,  # Keep model in RAM
    use_mmap=True    # Memory map the model
)

def build_dax_prompt(player_name, sentiment, mood_instruction, build_context, context_prompt,  player_dialogue):
    return f"""You are Dax, an F1 race engineer helping {player_name}. 

{mood_instruction}

{build_context}

Recent chat: {context_prompt}

Player says: "{player_dialogue}"

Dax responds:"""

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
            full_prompt,  # Don't use named parameter
            max_tokens=200,  # Increased to prevent cut-off
            temperature=0.3,  # Lower for consistency
            stop=["Player:", "Human:", "You:", "\n\n"],  # Remove single \n, keep double
            echo=False  # Don't echo the prompt back
        )

        response_time = time.time() - start_time

        # llama.cpp returns text directly, not in choices format
        if isinstance(output, dict) and "choices" in output:
            # Some versions return choices format
            reply_text = output["choices"][0]["text"].strip()
        elif hasattr(output, 'choices') and output.choices:
            # Pydantic model format
            reply_text = output.choices[0].text.strip()
        else:
            # Direct text output (most common for llama.cpp)
            reply_text = str(output).strip()
        
        print(f"🔍 Raw LLM output: '{reply_text}'")  # Debug
        
        # Remove quotes if they wrap the entire response
        if reply_text.startswith('"') and reply_text.endswith('"'):
            reply_text = reply_text[1:-1]
        elif reply_text.startswith('"') and not reply_text.endswith('"'):
            # Handle incomplete quotes (common with max_tokens limit)
            reply_text = reply_text[1:]
        
        # Clean up the response - remove any prompt echo
        if "Player:" in reply_text:
            reply_text = reply_text.split("Player:")[0].strip()
        if reply_text.startswith("Dax:"):
            reply_text = reply_text.replace("Dax:", "", 1).strip()
        
        # If empty, provide fallback
        if not reply_text or len(reply_text.strip()) < 3:
            reply_text = f"Hey {player_name}! Let's talk about your car setup."
        
        print(f"🔍 Cleaned response: '{reply_text}'")  # Debug
            
        sentiment_score = TextBlob(reply_text).sentiment.polarity
        npc_sentiment_label = 'positive' if sentiment_score > 0.1 else 'negative' if sentiment_score < -0.1 else 'neutral'
        print(f"📊 NPC SENTIMENT: '{reply_text[:50]}...' → {npc_sentiment_label} (score: {sentiment_score})")

        valid_parts = ["standard monocoque", "ground effect", "2004 v10", "2006 v8", "c5 slick", "full wet", "high lift", "simple outwash", "high downforce", "low drag"]
        accurate = any(part in reply_text.lower() for part in valid_parts)
        print(f"🎯 ACCURACY: Mentions car parts: {accurate} ({'✅' if accurate else '❌'})")

        return {
            "response": reply_text,
            "response_time_sec": round(response_time, 2),
            "sentiment_score": round(sentiment_score, 3),
            "mentions_part": accurate
        }

    except Exception as e:
        print(f"Error running LLaMA model: {e}")
        return {
            "response": "⚠️ Error generating response from local model.",
            "response_time_sec": None,
            "sentiment_score": None,
            "mentions_part": False
        }