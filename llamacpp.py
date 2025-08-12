from llama_cpp import Llama
from textblob import TextBlob
import time

# Load your model
llm = Llama(
    model_path="./models/mistral-7b-instruct-v0.1.Q2_K.gguf",
    n_threads=18,
    n_ctx=1024,
    n_batch=512,
    verbose=False,
    use_mlock=True,
    use_mmap=True
)

# --- Workflow check ---

def get_workflow_state_and_message(build, player_name):
    if not build:
        return "CHASSIS", "chassis", f"Let's start building your F1 car, {player_name}! First, choose your chassis: Standard Monocoque or Ground Effect Optimized."
    has_chassis = build.chassis and build.chassis.strip() != "" and build.chassis.strip() != "-"
    has_engine = build.engine and build.engine.strip() != "" and build.engine.strip() != "-"
    has_tires = build.tires and build.tires.strip() != "" and build.tires.strip() != "-"
    has_front_wing = build.frontWing and build.frontWing.strip() != "" and build.frontWing.strip() != "-"
    has_rear_wing = build.rearWing and build.rearWing.strip() != "" and build.rearWing.strip() != "-"
    if not has_chassis:
        return "CHASSIS", "chassis", f"First step, {player_name}: choose your chassis - Standard Monocoque or Ground Effect Optimized."
    elif not has_engine:
        return "ENGINE", "engine", f"Great chassis choice! Now select your engine: 2004 V10 or 2006 V8."
    elif not has_tires:
        return "TIRES", "tires", f"Perfect! Time for tires: C5 Slick or Full Wet."
    elif not has_front_wing:
        return "FRONT_WING", "front wing", f"Excellent! Choose your front wing: High Lift or Simple Outwash."
    elif not has_rear_wing:
        return "REAR_WING", "rear wing", f"Final step! Pick your rear wing: High Downforce or Low Drag."
    else:
        return "COMPLETE", "complete", f"Perfect, {player_name}! Your F1 car is fully built and race-ready. Click 'Submit Feedback' to finish!"

def build_dax_prompt(player_name, sentiment, mood_instruction, build, context_prompt, player_dialogue):
    workflow_state, current_step, workflow_message = get_workflow_state_and_message(build, player_name)
    selected_parts = []
    if build:
        if build.chassis and build.chassis != "-": selected_parts.append(f"✅ Chassis: {build.chassis}")
        if build.engine and build.engine != "-": selected_parts.append(f"✅ Engine: {build.engine}")
        if build.tires and build.tires != "-": selected_parts.append(f"✅ Tires: {build.tires}")
        if build.frontWing and build.frontWing != "-": selected_parts.append(f"✅ Front Wing: {build.frontWing}")
        if build.rearWing and build.rearWing != "-": selected_parts.append(f"✅ Rear Wing: {build.rearWing}")
    parts_summary = "\n".join(selected_parts) if selected_parts else "No parts selected yet"
    return f'''You are Dax, a witty, enthusiastic F1 race engineer helping {player_name} build the perfect race car. 
Follow the exact workflow order and NEVER repeat completed steps. 

WORKFLOW STATE: {workflow_state}
NEXT STEP: {current_step}
INSTRUCTION: {workflow_message}

BUILD PROGRESS:
{parts_summary}

RECENT CHAT:
{context_prompt}

RULES:
1. Only ask about the next missing part (Chassis → Engine → Tires → Front Wing → Rear Wing)
2. If workflow is complete, congratulate and suggest "Submit Feedback"
3. If off-topic, briefly acknowledge and redirect
4. Use racing metaphors, stay lively
5. Use {player_name}, never "Player"
6. Valid parts: Standard Monocoque/Ground Effect, 2004 V10/2006 V8, C5 Slick/Full Wet, High Lift/Simple Outwash, High Downforce/Low Drag

{mood_instruction}

Player says: "{player_dialogue}"

Dax:'''

# --- Main responder ---

def generate_npc_response(player_dialogue, sentiment, player_id, context=[], player_name="", build=None):
    # context: list of objects with .dialogue and .npc_reply
    context_prompt = ""
    for entry in context[-3:]:
        npc_reply = entry.npc_reply
        if isinstance(npc_reply, str) and npc_reply.startswith('{"response":'):
            # Clean any JSON from recent chat history
            try:
                import json
                npc_reply = json.loads(npc_reply).get("response", npc_reply)
            except Exception:
                pass
        npc_reply = str(npc_reply).strip('"')
        context_prompt += f"Player: {entry.dialogue}\nDax: {npc_reply}\n"
    context_prompt = context_prompt.strip()
    if not context_prompt:
        context_prompt = "This is the start of the conversation."
    mood_instruction = {
        "positive": "Be excited and energetic!",
        "happy": "Be excited and energetic!",
        "negative": "Be warm and encouraging.",
        "sad": "Be warm and encouraging.",
        "angry": "Stay calm and professional.",
        "neutral": "Be friendly and helpful."
    }.get(sentiment.lower(), "Be professional and focused.")
    full_prompt = build_dax_prompt(player_name, sentiment, mood_instruction, build, context_prompt, player_dialogue)
    try:
        start_time = time.time()
        output = llm(
            full_prompt,
            max_tokens=100,
            temperature=0.3,
            stop=["Player:", "Human:", "You:", "\n\n"],
            echo=False
        )
        response_time = time.time() - start_time
        # Extract response
        if isinstance(output, dict) and "choices" in output:
            reply_text = output["choices"][0]["text"].strip()
        elif hasattr(output, 'choices') and output.choices:
            reply_text = output.choices[0].text.strip()
        else:
            reply_text = str(output).strip()
        # Clean up the reply
        reply_text = reply_text.strip().strip('"')
        if "Player:" in reply_text:
            reply_text = reply_text.split("Player:")[0].strip()
        if reply_text.startswith("Dax:"):
            reply_text = reply_text.replace("Dax:", "", 1).strip()
        # Only show the first, proper output as the user's UI reply, else fallback to workflow message
        if len(reply_text) > 5:
            return reply_text
        # Fallback: use proper workflow prompt
        workflow_state, current_step, workflow_message = get_workflow_state_and_message(build, player_name)
        return workflow_message
    except Exception as e:
        print(f"Error running LLaMA model: {e}")
        workflow_state, current_step, workflow_message = get_workflow_state_and_message(build, player_name)
        return workflow_message
