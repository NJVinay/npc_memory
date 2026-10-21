"""Dax chat: the /chat_api endpoint used by chat.html, and conversation memory."""

import llm_adapter


def chat(client, player, text):
    return client.post("/chat_api", data={"player_id": player["id"], "npc_id": 1, "dialogue": text})


def history_section(prompt):
    """The RECENT CONVERSATION block of a Dax prompt."""
    return prompt.split("RECENT CONVERSATION:")[1].split("CRITICAL INSTRUCTIONS:")[0]


def test_chat_api_returns_dax_reply(client, player, llm_prompts, stub_reply):
    r = chat(client, player, "Which engine should I pick?")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["npc_reply"] == stub_reply
    assert body["player_dialogue"] == "Which engine should I pick?"
    assert body["sentiment"] in {"positive", "neutral", "negative"}
    assert len(llm_prompts) == 1


def test_reply_is_cleaned_of_reasoning_markdown_and_cut_off_text(client, player, monkeypatch):
    raw = "<think>They want an engine.</think>Go with the **2004 V10**. It loves long straights. However, the"
    monkeypatch.setattr(llm_adapter, "generate_with_groq", lambda *args, **kwargs: raw)

    r = chat(client, player, "Which engine?")
    assert r.json()["npc_reply"] == "Go with the 2004 V10. It loves long straights."


def test_prompt_asks_for_short_plain_text(client, player, llm_prompts):
    chat(client, player, "Hi")
    assert "no markdown" in llm_prompts[0]


def test_chat_page_greets_player_by_name(client, player):
    r = client.get("/chat")
    assert r.status_code == 200
    assert 'const rawPlayerName = "Test Driver";' in r.text


def test_chat_api_requires_login(client):
    r = client.post("/chat_api", data={"player_id": 1, "dialogue": "hi"})
    assert r.status_code == 401


def test_chat_api_rejects_other_player(client, player):
    r = client.post("/chat_api", data={"player_id": player["id"] + 1000, "dialogue": "hi"})
    assert r.status_code == 403


def test_chat_api_rejects_blank_and_overlong_dialogue(client, player, llm_prompts):
    assert chat(client, player, "   ").status_code == 400
    assert chat(client, player, "x" * 501).status_code == 400
    assert llm_prompts == []


def test_dax_remembers_earlier_messages(client, player, llm_prompts):
    chat(client, player, "My favourite circuit is Spa-Francorchamps")
    chat(client, player, "Which circuit did I say I like?")

    assert "start of the conversation" in history_section(llm_prompts[0])
    assert "My favourite circuit is Spa-Francorchamps" in history_section(llm_prompts[1])


def test_first_message_greets_player_and_later_ones_do_not(client, player, llm_prompts):
    chat(client, player, "Hello")
    chat(client, player, "Which tires for rain?")

    assert "Hey Test Driver!" in llm_prompts[0]
    assert "Hey Test Driver!" not in llm_prompts[1]


def test_dax_sees_current_build(client, player, llm_prompts):
    client.post("/save_car_build", data={
        "player_id": player["id"], "chassis": "Ground Effect Optimized", "engine": "2004 V10"
    })
    chat(client, player, "What have I picked so far?")

    assert "PARTIAL BUILD (2/5)" in llm_prompts[0]
    assert "Engine: V10 Engine" in llm_prompts[0]


def test_store_interaction_api_uses_history(client, player, llm_prompts, service_headers):
    chat(client, player, "Remember that my car number is 44")
    r = client.post("/store_interaction/", headers=service_headers, json={
        "player_id": player["id"], "npc_id": 1, "dialogue": "What is my car number?"
    })

    assert r.status_code == 201, r.text
    assert "my car number is 44" in history_section(llm_prompts[-1])


def test_store_interaction_requires_service_key(client, player):
    r = client.post("/store_interaction/", json={
        "player_id": player["id"], "npc_id": 1, "dialogue": "Hi"
    })
    assert r.status_code == 401


def test_editing_a_message_uses_only_earlier_history(client, player, llm_prompts, service_headers):
    chat(client, player, "My favourite circuit is Monza")
    chat(client, player, "Original question about tires")
    chat(client, player, "A later message about wings")
    interactions = client.get(f"/get_interactions/{player['id']}/1", headers=service_headers).json()
    middle = next(i for i in interactions if i["dialogue"] == "Original question about tires")

    r = client.put(f"/update_interaction/{middle['id']}", headers=service_headers,
                   json={"dialogue": "Edited question about engines"})

    assert r.status_code == 200, r.text
    assert r.json()["dialogue"] == "Edited question about engines"
    history = history_section(llm_prompts[-1])
    assert "My favourite circuit is Monza" in history
    assert "Original question about tires" not in history
    assert "A later message about wings" not in history


def test_interactions_can_be_listed_and_deleted(client, player, service_headers):
    chat(client, player, "Hello Dax")
    url = f"/get_interactions/{player['id']}/1"

    r = client.get(url, headers=service_headers)
    assert r.status_code == 200
    interactions = r.json()
    assert [i["dialogue"] for i in interactions] == ["Hello Dax"]

    r = client.delete(f"/delete_interaction/{interactions[0]['id']}", headers=service_headers)
    assert r.status_code == 200
    assert client.get(url, headers=service_headers).status_code == 404
