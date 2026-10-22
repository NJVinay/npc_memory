"""Health, car builds, the programmatic player API, and consent records."""

import uuid

FULL_BUILD = {
    "chassis": "Standard Monocoque",
    "engine": "2006 V8",
    "tires": "C5 Slick",
    "frontWing": "High Lift",
    "rearWing": "Low Drag",
}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "healthy", "database": "connected"}


def test_save_and_list_builds(client, player):
    r = client.post("/save_car_build", data={"player_id": player["id"], **FULL_BUILD})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "success"

    r = client.get(f"/get_builds/{player['id']}")
    assert r.status_code == 200, r.text
    [build] = r.json()
    assert build["engine"] == "2006 V8"
    assert build["front_wing"] == "High Lift"
    assert build["rear_wing"] == "Low Drag"
    assert build["timestamp"]


def test_unselected_parts_are_stored_as_missing(client, player):
    # Older TurboTom pages sent unselected parts as the strings "null"/"undefined"
    client.post("/save_car_build", data={
        "player_id": player["id"], "chassis": "Standard Monocoque",
        "engine": "null", "tires": "undefined", "frontWing": "",
    })

    [build] = client.get(f"/get_builds/{player['id']}").json()
    assert build["chassis"] == "Standard Monocoque"
    assert [build["engine"], build["tires"], build["front_wing"], build["rear_wing"]] == [None] * 4


def test_cannot_save_or_read_another_players_builds(client, player):
    other_id = player["id"] + 1000
    assert client.post("/save_car_build", data={"player_id": other_id, **FULL_BUILD}).status_code == 403
    assert client.get(f"/get_builds/{other_id}").status_code == 403


def test_create_player_api_hashes_password(client, service_headers):
    email = f"{uuid.uuid4().hex[:12]}@example.com"
    r = client.post("/create_player", headers=service_headers, json={
        "name": f"api-{uuid.uuid4()}", "email": email,
        "password": "racecar123", "display_name": "API Driver",
    })
    assert r.status_code == 200, r.text
    assert "password" not in r.json()

    # The stored hash works with the normal email/password login
    r = client.post("/verify_player", json={"email": email, "password": "racecar123"})
    assert r.status_code == 200


def test_create_player_api_requires_service_key(client):
    r = client.post("/create_player", json={"name": f"api-{uuid.uuid4()}"})
    assert r.status_code == 401


def test_store_consent(client, logged_in_player):
    r = client.post("/store_consent", json={
        "player_id": logged_in_player["id"], "name": "Test Driver",
        "consent_participate": True, "consent_data": True, "consent_age": True,
    })
    assert r.status_code == 200, r.text
    assert r.json()["consent_participate"] is True


def test_store_consent_for_another_player_is_forbidden(client, player):
    r = client.post("/store_consent", json={
        "player_id": player["id"] + 1000, "study_uuid": str(uuid.uuid4()), "name": "Someone",
        "consent_participate": True, "consent_data": True, "consent_age": True,
    })
    assert r.status_code == 403
