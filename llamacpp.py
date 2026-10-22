from typing import Dict, List, Optional, Any
import re
import time
import os

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from textblob import TextBlob

from config import config
from llm_adapter import LLMError, generate_llm_response

# Initialize local LLM only if not using external API
llm = None
if not config.USE_EXTERNAL_LLM:
    try:
        from llama_cpp import Llama
        llm = Llama(
            model_path=config.MODEL_PATH,
            n_threads=config.MODEL_N_THREADS,
            n_ctx=config.MODEL_N_CTX,
            n_batch=config.MODEL_N_BATCH,
            verbose=False
        )
        print(f"✅ Loaded local GGUF model: {config.MODEL_PATH}")
    except Exception as e:
        print(f"⚠️ Local model not loaded: {e}")

# Mapping for user-friendly car part names
PART_NAME_MAP: Dict[str, str] = {
    "standard monocoque": "Monocoque",
    "ground effect": "Ground Effect",
    "2004 v10": "V10 Engine",
    "2006 v8": "V8 Engine",
    "c5 slick": "Slick Tires",
    "full wet": "Wet Tires",
    "high lift": "High Lift Wing",
    "simple outwash": "Outwash Wing",
    "high downforce": "High Downforce",
    "low drag": "Low Drag"
}

# Every name the game uses for a part: the full names in the prompt, the short names in
# the build summary Dax is shown, and the bare words (V10, monocoque, ...). Feeds mentions_part.
PART_MENTION_NAMES = sorted(
    set(PART_NAME_MAP)
    | {name.lower() for name in PART_NAME_MAP.values()}
    | {"ground effect optimized", "v10", "v8", "monocoque", "slick", "slicks", "outwash"},
    key=len, reverse=True
)
PART_MENTION_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(name) for name in PART_MENTION_NAMES) + r")\b", re.IGNORECASE
)

# Road-car brands that point to an off-topic reply. Only flagged in the data, never
# rewritten. F1 names (Ferrari, Mercedes, Honda, Audi and Ford in 2026, ...) and real F1
# topics such as brakes or gears are legitimate race-engineer talk.
OFF_TOPIC_BRANDS = ["corvette", "porsche", "lamborghini", "nissan", "chevrolet"]
OFF_TOPIC_PATTERN = re.compile(r"\b(" + "|".join(OFF_TOPIC_BRANDS) + r")\b", re.IGNORECASE)

# End of a complete sentence: . ! or ? (optionally closing a quote) before whitespace or the end
SENTENCE_END_PATTERN = re.compile(r"[.!?][\"')\]]?(?=\s|$)")

def has_part(part: Optional[str]) -> bool:
    """True if a build slot holds a part. Older builds stored unselected parts as "null"/"undefined"."""
    return bool(part) and part.strip().lower() not in ("null", "undefined")

def get_short_part_name(part: Optional[str]) -> str:
    """Return a concise, user-friendly part name.

    Args:
        part: The full part name or identifier

    Returns:
        Short, user-friendly name or the original if no match found
    """
    if not has_part(part):
        return "-"
    
    part_lower = str(part).lower().strip()
    
    # Check for exact keywords (prioritize full matches)
    for key, short_name in PART_NAME_MAP.items():
        if key in part_lower:
            return short_name
    
    # Fallback for concatenated names (e.g., "GroundEffectOptimized_Monocoque")
    for key, short_name in PART_NAME_MAP.items():
        key_no_space = key.replace(" ", "")
        if key_no_space in part_lower:
            return short_name
    
    return part  # Return original if no match

def build_dax_prompt(
    player_name: str,
    sentiment: str,
    mood_instruction: str,
    build_context: str,
    context_prompt: str,
    player_dialogue: str,
    is_first_message: bool
) -> str:
    """Build the prompt for Dax NPC responses.
    
    Args:
        player_name: Name of the player
        sentiment: Detected sentiment of player message
        mood_instruction: Instruction for NPC mood/tone
        build_context: Current car build information
        context_prompt: Recent conversation history
        player_dialogue: Current player message
        is_first_message: Whether this is the first message in conversation
        
    Returns:
        Formatted prompt string for LLM
    """
    # DEBUG: Print the actual build_context to see its format
    print(f"🔍 DEBUG - Build context received:")
    print(f"'{build_context}'")
    print(f"🔍 DEBUG - End of build context")
    
    # Only greet on first message
    greeting = f"Hey {player_name}! I'm Dax, your F1 race engineer. How can I help today?" if is_first_message else ""
    
    # FIXED: Properly parse the actual build_context format
    build_status = "INCOMPLETE"
    build_summary = "No F1 parts selected yet"
    next_action = "Start by selecting your chassis: Standard Monocoque or Ground Effect Optimized."
    
    if build_context and "🚗 The player's current car build:" in build_context:
        # Parse the actual format: "- Chassis: Ground Effect\n- Engine: V10 Engine\n..."
        selected_parts = []
        missing_parts = []
        
        # Check each part from the actual build_context format
        if "- Chassis: " in build_context:
            chassis = build_context.split("- Chassis: ")[1].split("\n")[0].strip()
            if chassis != "-":
                selected_parts.append(f"Chassis: {chassis}")
            else:
                missing_parts.append("chassis")
        else:
            missing_parts.append("chassis")
            
        if "- Engine: " in build_context:
            engine = build_context.split("- Engine: ")[1].split("\n")[0].strip()
            if engine != "-":
                selected_parts.append(f"Engine: {engine}")
            else:
                missing_parts.append("engine")
        else:
            missing_parts.append("engine")
            
        if "- Tires: " in build_context:
            tires = build_context.split("- Tires: ")[1].split("\n")[0].strip()
            if tires != "-":
                selected_parts.append(f"Tires: {tires}")
            else:
                missing_parts.append("tires")
        else:
            missing_parts.append("tires")
            
        if "- Front Wing: " in build_context:
            fw = build_context.split("- Front Wing: ")[1].split("\n")[0].strip()
            if fw != "-":
                selected_parts.append(f"Front Wing: {fw}")
            else:
                missing_parts.append("front wing")
        else:
            missing_parts.append("front wing")
            
        if "- Rear Wing: " in build_context:
            rw = build_context.split("- Rear Wing: ")[1].split("\n")[0].strip()
            if rw != "-":
                selected_parts.append(f"Rear Wing: {rw}")
            else:
                missing_parts.append("rear wing")
        else:
            missing_parts.append("rear wing")
        
        # Determine build status and next action
        if len(selected_parts) == 5:
            build_status = "COMPLETE"
            build_summary = "✅ COMPLETE F1 BUILD: " + ", ".join(selected_parts)
            next_action = "Your F1 car is ready! I can discuss the build, answer F1 questions, or you can click 'Submit Feedback' to finish."
        elif len(selected_parts) > 0:
            build_status = "IN_PROGRESS" 
            build_summary = f"🔧 PARTIAL BUILD ({len(selected_parts)}/5): " + ", ".join(selected_parts)
            if missing_parts:
                next_part_suggestions = {
                    "chassis": "Standard Monocoque or Ground Effect Optimized",
                    "engine": "2004 V10 or 2006 V8", 
                    "tires": "C5 Slick or Full Wet",
                    "front wing": "High Lift or Simple Outwash",
                    "rear wing": "High Downforce or Low Drag"
                }
                next_missing = missing_parts[0]
                next_action = f"Next, select your {next_missing}: {next_part_suggestions.get(next_missing, 'continue building')}."
        else:
            build_status = "INCOMPLETE"
            next_action = "Start by selecting your chassis: Standard Monocoque or Ground Effect Optimized."
    
    # ENHANCED prompt with better state management and human-like responses
    return f"""You are Dax, an experienced F1 race engineer. You ONLY work with Formula 1 cars. {greeting}

BUILD STATUS: {build_status}
CURRENT BUILD: {build_summary}
NEXT ACTION: {next_action}
TONE: {mood_instruction}

RECENT CONVERSATION:
{context_prompt}

CRITICAL INSTRUCTIONS:
1. If BUILD STATUS is COMPLETE: Say the build is ready, offer to discuss it or answer questions, and suggest clicking "Submit Feedback"
2. If player asks about selected parts: Reference CURRENT BUILD above accurately
3. If player says they already selected everything but BUILD STATUS shows otherwise: Ask them to double-check their selections
4. Be conversational and helpful like a real engineer - avoid repetitive apologies
5. ONLY mention valid F1 parts: Standard Monocoque/Ground Effect chassis, 2004 V10/2006 V8 engines, C5 Slick/Full Wet tires, High Lift/Simple Outwash front wings, High Downforce/Low Drag rear wings
6. Use the player's name: {player_name} (NOT "Player12" or generic names)
7. Keep it short: at most 3 sentences, plain text only (no markdown, bold, or lists)

Player: "{player_dialogue}"

Dax:"""

def generate_npc_response(
    player_dialogue: str,
    sentiment: str,
    player_id: int,
    context: List[Any] = None,
    player_name: str = "",
    build: Optional[Any] = None
) -> Dict[str, Any]:
    """Generate NPC response using local LLM.
    
    Args:
        player_dialogue: The player's message
        sentiment: Detected sentiment of the message
        player_id: ID of the player
        context: List of previous conversation entries
        player_name: Display name of the player
        build: Current car build object (optional)
        
    Returns:
        Dictionary containing response text, timing, sentiment score, and accuracy metrics
    """
    if context is None:
        context = []
    
    # ENHANCED context processing for better memory - retrieve last 20 exchanges
    context_entries = []
    for entry in context[-20:]:  # Increased from 5 to 8 for better memory
        player_msg = entry.dialogue
        npc_msg = entry.npc_reply or ""

        # Clean historical responses
        if npc_msg.startswith('{"response":'):
            try:
                import json
                parsed = json.loads(npc_msg)
                npc_msg = parsed.get("response", npc_msg)
            except:
                pass
        
        # Remove any "Dax:" prefixes from history
        npc_msg = npc_msg.strip('"').replace("Dax:", "").strip()
        context_entries.append(f"Player: {player_msg}\nDax: {npc_msg}")
    
    # Keep more context for memory - last 15 exchanges for excellent continuity
    context_prompt = "\n".join(context_entries[-15:]) 
    if not context_prompt:
        context_prompt = "This is the start of the conversation."

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
            f"- Chassis: {get_short_part_name(build.chassis)}\n"
            f"- Engine: {get_short_part_name(build.engine)}\n"
            f"- Tires: {get_short_part_name(build.tires)}\n"
            f"- Front Wing: {get_short_part_name(build.front_wing)}\n"
            f"- Rear Wing: {get_short_part_name(build.rear_wing)}\n\n"
        )
        if all(has_part(p) for p in (build.chassis, build.engine, build.tires, build.front_wing, build.rear_wing)):
            mood_instruction += " The car build is complete. Praise the player or give final strategy tips."
            
    is_first_message = not context_entries
            
    full_prompt = build_dax_prompt(player_name, sentiment, mood_instruction, build_context, context_prompt, player_dialogue, is_first_message)

    # Generate response using local model or external API
    start_time = time.time()
    finish_reason = None
    try:
        if config.USE_EXTERNAL_LLM:
            llm_result = generate_llm_response(full_prompt, max_tokens=config.MODEL_MAX_TOKENS, temperature=config.MODEL_TEMPERATURE)
            reply_text = llm_result["response"]
            finish_reason = llm_result.get("finish_reason")
        elif llm is None:
            raise LLMError("Local model is not loaded")
        else:
            # Use local GGUF model
            output = llm(
                full_prompt,
                max_tokens=config.MODEL_MAX_TOKENS,
                temperature=config.MODEL_TEMPERATURE,
                stop=["Player:", "Human:", "Dax:", "\n\n"],
                echo=False,
                repeat_penalty=1.3
            )

            # Extract response text
            if isinstance(output, dict) and "choices" in output:
                reply_text = output["choices"][0]["text"].strip()
                finish_reason = output["choices"][0].get("finish_reason")
            elif hasattr(output, 'choices') and output.choices:
                reply_text = output.choices[0].text.strip()
            else:
                reply_text = str(output).strip()
    except Exception as e:
        print(f"❌ LLM generation failed: {e}")
        return _llm_error_result(start_time)

    response_time = time.time() - start_time
    raw_reply = reply_text
    print(f"🔍 Raw LLM output: '{reply_text}'")

    # AGGRESSIVE CLEANING to fix "Dax: Dax:" and prompt leaking
    # Remove all instances of "Dax:" at the start
    while reply_text.startswith("Dax:"):
        reply_text = reply_text[4:].strip()

    # Remove prompt instructions that leaked through
    if "Player Message:" in reply_text:
        reply_text = reply_text.split("Player Message:")[0].strip()
    if "Respond as Dax" in reply_text:
        reply_text = reply_text.split("Respond as Dax")[0].strip()

    # Remove quotes if they wrap the response
    if reply_text.startswith('"') and reply_text.endswith('"'):
        reply_text = reply_text[1:-1]
    elif reply_text.startswith('"'):
        reply_text = reply_text[1:]

    # Remove any remaining "Dax:" patterns
    reply_text = reply_text.replace("Dax:", "").strip()

    # Reasoning models (e.g. Qwen3) can emit a <think> block. A block that never closes
    # means the token limit ran out while reasoning, so there is no reply at all.
    reply_text = re.sub(r"<think>.*?</think>", "", reply_text, flags=re.DOTALL)
    if "<think>" in reply_text:
        print("❌ LLM reply was cut off inside its reasoning")
        return _llm_error_result(start_time, raw_reply)
    # The chat shows plain text, not markdown
    reply_text = reply_text.replace("**", "").strip()

    # A reply cut off by the token limit ends mid-sentence; keep only the complete sentences
    if finish_reason == "length":
        sentence_ends = list(SENTENCE_END_PATTERN.finditer(reply_text))
        if sentence_ends:
            reply_text = reply_text[:sentence_ends[-1].end()]

    status = "ok"
    # If still empty or too short, provide context-appropriate fallback
    if not reply_text or len(reply_text.strip()) < 10:
        status = "fallback"
        # Generate context-appropriate fallback based on build status
        if build and all(has_part(p) for p in (build.chassis, build.engine, build.tires, build.front_wing, build.rear_wing)):
            reply_text = f"Perfect build, {player_name}! Your car is race-ready. Focus on your racing line and you'll do great!"
        elif build:
            missing_parts = []
            if not has_part(build.chassis): missing_parts.append("chassis")
            if not has_part(build.engine): missing_parts.append("engine") 
            if not has_part(build.tires): missing_parts.append("tires")
            if not has_part(build.front_wing): missing_parts.append("front wing")
            if not has_part(build.rear_wing): missing_parts.append("rear wing")

            if missing_parts:
                next_part = missing_parts[0]
                reply_text = f"Let's focus on selecting your {next_part} next, {player_name}."
            else:
                reply_text = f"Great progress on your build, {player_name}! How are you feeling about the setup?"
        else:
            reply_text = f"Hey {player_name}! Let's start building your F1 car. What would you like to work on first?"

    print(f"🔍 Cleaned response: '{reply_text}'")

    sentiment_score = TextBlob(reply_text).sentiment.polarity
    npc_sentiment_label = 'positive' if sentiment_score > 0.1 else 'negative' if sentiment_score < -0.1 else 'neutral'
    print(f"📊 NPC SENTIMENT: '{reply_text[:50]}...' → {npc_sentiment_label} (score: {sentiment_score})")

    # Does the reply name one of the game's parts, and does it drift to road cars?
    accurate = bool(PART_MENTION_PATTERN.search(reply_text))
    if status == "ok" and OFF_TOPIC_PATTERN.search(reply_text):
        status = "off_topic"
        print("⚠️ Off-topic reply flagged (road-car brand mentioned)")

    print(f"🎯 ACCURACY: Mentions car parts: {accurate} ('✅' if accurate else '❌')")

    return {
        "response": reply_text,
        "status": status,
        "raw_reply": raw_reply,
        "response_time_sec": round(response_time, 2),
        "sentiment_score": round(sentiment_score, 3),
        "mentions_part": accurate
    }


def _llm_error_result(start_time: float, raw_reply: Optional[str] = None) -> Dict[str, Any]:
    """Result for a turn where the LLM produced no usable reply; nothing is shown as Dax's answer."""
    return {
        "response": None,
        "status": "llm_error",
        "raw_reply": raw_reply,
        "response_time_sec": round(time.time() - start_time, 2),
        "sentiment_score": None,
        "mentions_part": None
    }
