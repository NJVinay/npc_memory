"""Study design: one condition per participant, TurboTom logging, and consent enforcement."""

from config import config
from database import SessionLocal
from models import Consent, NPCMemory, StudyAssignment
from services import StudyService

CONSENT = {"name": "Test Driver", "consent_participate": True, "consent_data": True, "consent_age": True}


def give_consent(client, player_id):
    r = client.post("/store_consent", json={**CONSENT, "player_id": player_id})
    assert r.status_code == 200, r.text


def condition_counts():
    with SessionLocal() as db:
        return {c: db.query(StudyAssignment).filter_by(condition=c).count() for c in config.STUDY_CONDITIONS}


def start_chat(client, player_id):
    return client.get(f"/start_chat?player_id={player_id}", follow_redirects=False)


# --- Condition assignment ---

def test_condition_is_drawn_once_and_kept(client, logged_in_player):
    give_consent(client, logged_in_player["id"])

    targets = {start_chat(client, logged_in_player["id"]).headers["location"] for _ in range(6)}

    assert len(targets) == 1
    assert targets.pop().split("?")[0] in {"/chat", "/chat_static"}


def test_new_participants_join_the_smaller_condition(client, logged_in_player):
    give_consent(client, logged_in_player["id"])
    before = condition_counts()

    location = start_chat(client, logged_in_player["id"]).headers["location"]

    assigned = "dax" if location.startswith("/chat?") else "static"
    if before["dax"] != before["static"]:
        assert assigned == min(before, key=before.get)
    assert condition_counts()[assigned] == before[assigned] + 1


def test_each_condition_page_sends_the_other_group_to_its_own_page(client, player, set_condition):
    r = client.get("/chat_static", follow_redirects=False)  # player is in the Dax condition
    assert r.status_code == 303
    assert r.headers["location"].startswith("/chat?")

    set_condition(player["id"], "static")
    r = client.get("/chat", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/chat_static?")


def test_turbotom_participants_cannot_chat_with_dax(client, player, set_condition, llm_prompts):
    set_condition(player["id"], "static")

    r = client.post("/chat_api", data={"player_id": player["id"], "dialogue": "Hi"})

    assert r.status_code == 403
    assert llm_prompts == []


# --- TurboTom logging ---

def log_turn(client, player_id, choice="Let's go!", npc_reply="Awesome! Let's build your car."):
    return client.post("/log_static_turn", json={"player_id": player_id, "choice": choice, "npc_reply": npc_reply})


def test_turbotom_choices_are_logged(client, player, set_condition, service_headers):
    set_condition(player["id"], "static")

    assert log_turn(client, player["id"]).status_code == 201

    rows = client.get(f"/get_interactions/{player['id']}/{config.STATIC_NPC_ID}", headers=service_headers).json()
    assert [(r["dialogue"], r["npc_reply"], r["source"], r["reply_status"]) for r in rows] == [
        ("Let's go!", "Awesome! Let's build your car.", "static_option", "scripted")
    ]


def test_dead_end_choice_is_logged_without_a_reply(client, player, set_condition, service_headers):
    set_condition(player["id"], "static")

    assert log_turn(client, player["id"], choice="Thanks, TurboTom!", npc_reply=None).status_code == 201


def test_dax_participants_cannot_log_turbotom_turns(client, player):
    assert log_turn(client, player["id"]).status_code == 403


def test_turbotom_turns_stay_out_of_dax_memory(client, player, set_condition, llm_prompts):
    set_condition(player["id"], "static")
    log_turn(client, player["id"], choice="TurboTomOnlyChoice")
    set_condition(player["id"], "dax")

    client.post("/chat_api", data={"player_id": player["id"], "dialogue": "Hello"})

    assert "TurboTomOnlyChoice" not in llm_prompts[0]


# --- Consent ---

def test_pages_send_players_without_consent_to_the_consent_step(client, logged_in_player):
    player_id = logged_in_player["id"]
    for path in [f"/cover?player_id={player_id}", f"/start_chat?player_id={player_id}", "/chat", "/chat_static"]:
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 303, path
        assert r.headers["location"] == "/login?consent=required", path


def test_study_endpoints_refuse_players_without_consent(client, logged_in_player, llm_prompts):
    player_id = logged_in_player["id"]

    assert client.post("/chat_api", data={"player_id": player_id, "dialogue": "Hi"}).status_code == 403
    assert client.post("/save_car_build", data={"player_id": player_id, "engine": "2004 V10"}).status_code == 403
    assert log_turn(client, player_id).status_code == 403
    assert llm_prompts == []


def test_consent_requires_the_three_mandatory_agreements(client, logged_in_player):
    for flag in ("consent_participate", "consent_data", "consent_age"):
        r = client.post("/store_consent", json={**CONSENT, flag: False, "player_id": logged_in_player["id"]})
        assert r.status_code == 422, flag


def test_consent_is_recorded_once_per_study(client, logged_in_player):
    give_consent(client, logged_in_player["id"])

    r = client.post("/store_consent", json={**CONSENT, "player_id": logged_in_player["id"], "study_uuid": "client-value"})

    assert r.status_code == 409
    # The conflict must not echo SQL or the participant's details
    assert "INSERT" not in r.text and "Test Driver" not in r.text
    with SessionLocal() as db:
        study_ids = [c.study_uuid for c in db.query(Consent).filter_by(player_id=logged_in_player["id"])]
    assert study_ids == [config.STUDY_ID]


def test_consent_given_before_the_fixed_study_id_still_counts_once(client, logged_in_player):
    player_id = logged_in_player["id"]
    with SessionLocal() as db:  # a consent row from before STUDY_ID existed
        db.add(Consent(player_id=player_id, study_uuid="old-random-uuid", **CONSENT))
        db.commit()

    assert client.get(f"/start_chat?player_id={player_id}", follow_redirects=False).status_code == 307
    assert client.post("/store_consent", json={**CONSENT, "player_id": player_id}).status_code == 409


# --- More on assignment and TurboTom logging ---

def test_players_who_already_talked_to_dax_stay_with_dax(client, logged_in_player):
    player_id = logged_in_player["id"]
    give_consent(client, player_id)
    with SessionLocal() as db:  # a Dax turn from before assignments were recorded
        db.add(NPCMemory(player_id=player_id, npc_id=config.DEFAULT_NPC_ID, dialogue="Hi Dax", npc_reply="Hello!"))
        db.commit()

    assert start_chat(client, player_id).headers["location"].startswith("/chat?")
    with SessionLocal() as db:
        assert db.get(StudyAssignment, player_id).reason == "prior_dax_history"


def test_concurrent_assignment_keeps_the_first(monkeypatch, logged_in_player):
    player_id = logged_in_player["id"]
    with SessionLocal() as other:  # another request assigns this player first
        other.add(StudyAssignment(player_id=player_id, condition="static", reason="balanced"))
        other.commit()

    real_get_condition = StudyService.get_condition
    calls = []
    def stale_first_read(db, pid):
        calls.append(pid)
        return None if len(calls) == 1 else real_get_condition(db, pid)
    monkeypatch.setattr(StudyService, "get_condition", staticmethod(stale_first_read))

    with SessionLocal() as db:
        assert StudyService.get_or_assign_condition(db, player_id) == "static"


def test_turbotom_steps_advanced_by_a_part_pick_are_marked(client, player, set_condition, service_headers):
    set_condition(player["id"], "static")

    r = client.post("/log_static_turn", json={
        "player_id": player["id"], "choice": "Engine selected.", "npc_reply": "Nice!", "source": "part_click"
    })

    assert r.status_code == 201
    [row] = client.get(f"/get_interactions/{player['id']}/{config.STATIC_NPC_ID}", headers=service_headers).json()
    assert row["source"] == "part_click"


def test_blank_or_unknown_turbotom_input_is_rejected(client, player, set_condition):
    set_condition(player["id"], "static")

    assert log_turn(client, player["id"], choice="   ").status_code == 422
    r = client.post("/log_static_turn", json={"player_id": player["id"], "choice": "Hi", "source": "typed"})
    assert r.status_code == 422
