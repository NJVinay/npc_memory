"""Dax's replies: tone, the off-topic flag, LLM failures, reply cleanup and stored metrics."""

from types import SimpleNamespace

import pytest

import llm_adapter
from config import config
from database import SessionLocal
from llm_adapter import LLMError, generate_with_groq as real_generate_with_groq
from models import NPCMemory


def chat(client, player, text, **extra):
    return client.post("/chat_api", data={"player_id": player["id"], "dialogue": text, **extra})


def reply_with(monkeypatch, text, finish_reason="stop"):
    monkeypatch.setattr(llm_adapter, "generate_with_groq",
                        lambda *args, **kwargs: {"text": text, "finish_reason": finish_reason})


def latest_row(player_id):
    with SessionLocal() as db:
        return db.query(NPCMemory).filter_by(player_id=player_id).order_by(NPCMemory.id.desc()).first()


def history_section(prompt):
    return prompt.split("RECENT CONVERSATION:")[1].split("CRITICAL INSTRUCTIONS:")[0]


# --- Tone ---

def test_player_mood_sets_dax_tone(client, player, llm_prompts):
    chat(client, player, "I love this, it is great and awesome!")
    chat(client, player, "This is terrible, I hate it and feel awful.")

    assert "TONE: Respond in an excited, supportive, and energetic tone." in llm_prompts[0]
    assert "TONE: Respond warmly and empathetically." in llm_prompts[1]


# --- Off-topic flag ---

@pytest.mark.parametrize("reply", [
    "You can afford to push the V10 at Monza.",
    "Ferrari and Mercedes both ran V10 engines in 2004.",
    "Strong brakes and short gear ratios help in the hairpin.",
])
def test_ordinary_f1_talk_is_not_rewritten(client, player, monkeypatch, reply):
    reply_with(monkeypatch, reply)

    body = chat(client, player, "Tell me something").json()

    assert body["npc_reply"] == reply
    assert body["reply_status"] == "ok"


def test_road_car_talk_is_flagged_not_rewritten(client, player, monkeypatch):
    reply = "A Corvette engine would be fun, but stick with the 2004 V10."
    reply_with(monkeypatch, reply)

    body = chat(client, player, "Tell me something").json()

    assert body["npc_reply"] == reply
    assert body["reply_status"] == "off_topic"


# --- LLM failures ---

def test_llm_failure_returns_503_and_stays_out_of_memory(client, player, monkeypatch):
    def fail(*args, **kwargs):
        raise LLMError("429 rate_limit_exceeded")
    monkeypatch.setattr(llm_adapter, "generate_with_groq", fail)

    assert chat(client, player, "My lucky number is 27").status_code == 503
    row = latest_row(player["id"])
    assert row.reply_status == "llm_error"
    assert row.npc_reply is None

    prompts = []
    def answer(prompt, *args, **kwargs):
        prompts.append(prompt)
        return {"text": "Sure thing, driver.", "finish_reason": "stop"}
    monkeypatch.setattr(llm_adapter, "generate_with_groq", answer)

    assert chat(client, player, "Hello again").status_code == 200
    assert "lucky number" not in history_section(prompts[0])


def test_reply_cut_off_while_reasoning_counts_as_a_failure(client, player, monkeypatch):
    reply_with(monkeypatch, "<think>The player wants an engine for Monza and", "length")

    assert chat(client, player, "Which engine?").status_code == 503
    assert latest_row(player["id"]).reply_status == "llm_error"


# --- Reply cleanup ---

@pytest.mark.parametrize("reply", [
    "You gain 0.3 seconds a lap at Monza",
    "Great pick! Next, choose your tires 🏎️",
])
def test_complete_replies_are_not_trimmed(client, player, monkeypatch, reply):
    reply_with(monkeypatch, reply, "stop")

    assert chat(client, player, "Hi").json()["npc_reply"] == reply


def test_cut_off_reply_keeps_complete_sentences_and_decimals(client, player, monkeypatch):
    reply_with(monkeypatch, "You gain 0.3 seconds a lap. The V10 helps on the straights and", "length")

    assert chat(client, player, "Hi").json()["npc_reply"] == "You gain 0.3 seconds a lap."


# --- Stored metrics and message source ---

def test_reply_metrics_are_stored(client, player, stub_reply):
    chat(client, player, "Which engine?")

    row = latest_row(player["id"])
    assert row.source == "typed"
    assert row.reply_status == "ok"
    assert row.raw_reply == stub_reply
    assert row.llm_model == f"{config.LLM_PROVIDER}:{config.LLM_MODEL}"
    assert row.response_time_ms is not None
    assert row.mentions_part is True


@pytest.mark.parametrize("reply, mentions", [
    ("Your V10 Engine and Slick Tires are locked in.", True),   # short names from the build summary
    ("Go with the V8 and a monocoque.", True),                  # bare names
    ("Ground Effect Optimized suits Monza.", True),             # full name from the prompt
    ("Lovely weather for racing today.", False),
])
def test_mentions_part_recognises_every_name_dax_is_given(client, player, monkeypatch, reply, mentions):
    reply_with(monkeypatch, reply)

    chat(client, player, "Hi")

    assert latest_row(player["id"]).mentions_part is mentions


def test_older_turns_without_a_status_still_count_as_memory(client, player, llm_prompts):
    with SessionLocal() as db:  # a turn stored before reply_status existed
        db.add(NPCMemory(player_id=player["id"], npc_id=config.DEFAULT_NPC_ID,
                         dialogue="My car number is 44", npc_reply="Noted, 44 it is."))
        db.commit()

    chat(client, player, "What is my number?")

    assert "My car number is 44" in history_section(llm_prompts[0])


def test_part_click_messages_are_marked_as_automatic(client, player):
    assert chat(client, player, "I selected the 2004 V10 for the engine.", source="part_click").status_code == 200

    assert latest_row(player["id"]).source == "part_click"


def test_unknown_message_source_is_rejected(client, player):
    assert chat(client, player, "Hi", source="robot").status_code == 400


# --- Programmatic store / edit endpoints ---

def store(client, player, service_headers, text, npc_id=1):
    return client.post("/store_interaction/", headers=service_headers,
                       json={"player_id": player["id"], "npc_id": npc_id, "dialogue": text})


def test_store_refuses_turbotom_rows_and_turbotom_participants(client, player, set_condition, service_headers):
    assert store(client, player, service_headers, "Hi", npc_id=config.STATIC_NPC_ID).status_code == 400
    set_condition(player["id"], "static")
    assert store(client, player, service_headers, "Hi").status_code == 403


def test_store_failure_is_503_and_can_be_retried(client, player, monkeypatch, service_headers):
    def fail(*args, **kwargs):
        raise LLMError("timeout")
    monkeypatch.setattr(llm_adapter, "generate_with_groq", fail)
    assert store(client, player, service_headers, "Which wing?").status_code == 503

    reply_with(monkeypatch, "High Downforce for the corners.")
    assert store(client, player, service_headers, "Which wing?").status_code == 201


def test_edit_failure_leaves_the_turn_unchanged(client, player, monkeypatch, service_headers):
    chat(client, player, "Original question")
    row = latest_row(player["id"])
    def fail(*args, **kwargs):
        raise LLMError("timeout")
    monkeypatch.setattr(llm_adapter, "generate_with_groq", fail)

    r = client.put(f"/update_interaction/{row.id}", headers=service_headers, json={"dialogue": "Edited question"})

    assert r.status_code == 503
    after = latest_row(player["id"])
    assert (after.dialogue, after.npc_reply, after.reply_status) == ("Original question", row.npc_reply, "ok")


def test_turbotom_turns_cannot_be_edited(client, player, set_condition, service_headers):
    set_condition(player["id"], "static")
    client.post("/log_static_turn", json={"player_id": player["id"], "choice": "Let's go!", "npc_reply": "Awesome!"})
    row = latest_row(player["id"])

    r = client.put(f"/update_interaction/{row.id}", headers=service_headers, json={"dialogue": "Changed"})

    assert r.status_code == 400
    assert latest_row(player["id"]).npc_reply == "Awesome!"


# --- Groq adapter ---

class FakeGroq:
    """Stands in for groq.Groq; records the arguments of the last completion request."""

    def __init__(self, content="Pick the V10.", finish_reason="stop", error=None):
        self.content, self.finish_reason, self.error = content, finish_reason, error
        self.kwargs = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=self.finish_reason)])


def use_fake_groq(monkeypatch, fake, model="qwen/qwen3.8-27b"):
    monkeypatch.setattr(llm_adapter, "_groq_client", lambda: fake)
    monkeypatch.setattr(config, "LLM_MODEL", model)


def test_groq_call_turns_off_qwen_reasoning(monkeypatch):
    fake = FakeGroq()
    use_fake_groq(monkeypatch, fake)

    assert real_generate_with_groq("prompt") == {"text": "Pick the V10.", "finish_reason": "stop"}
    assert fake.kwargs["extra_body"] == {"reasoning_effort": "none"}


def test_groq_call_leaves_other_models_alone(monkeypatch):
    fake = FakeGroq()
    use_fake_groq(monkeypatch, fake, model="openai/gpt-oss-20b")

    real_generate_with_groq("prompt")
    assert fake.kwargs["extra_body"] is None


@pytest.mark.parametrize("fake", [
    FakeGroq(content=None, finish_reason="length"),
    FakeGroq(content="   "),
    FakeGroq(error=RuntimeError("429 rate_limit_exceeded")),
])
def test_groq_failures_raise_instead_of_returning_text(monkeypatch, fake):
    use_fake_groq(monkeypatch, fake)

    with pytest.raises(LLMError):
        real_generate_with_groq("prompt")
