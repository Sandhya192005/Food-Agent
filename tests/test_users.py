def test_read_current_user(client, auth_headers, test_user):
    response = client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == test_user.id
    assert body["email"] == test_user.email


def test_patch_weight_recomputes_metrics(client, auth_headers):
    before = client.get("/api/v1/users/me", headers=auth_headers).json()

    response = client.patch("/api/v1/users/me", json={"weight_kg": 65}, headers=auth_headers)
    assert response.status_code == 200
    after = response.json()

    assert after["weight_kg"] == 65
    assert after["metrics"]["bmi"] != before["metrics"]["bmi"]
    assert after["metrics"]["bmr"] != before["metrics"]["bmr"]
    assert after["metrics"]["tdee"] != before["metrics"]["tdee"]


def test_patch_preferred_name_does_not_change_metrics(client, auth_headers):
    before = client.get("/api/v1/users/me", headers=auth_headers).json()

    response = client.patch(
        "/api/v1/users/me", json={"preferred_name": "New Name"}, headers=auth_headers
    )
    after = response.json()

    assert after["preferred_name"] == "New Name"
    assert after["metrics"] == before["metrics"]


def test_patch_medical_conditions_fully_replaces_list(client, auth_headers):
    client.patch(
        "/api/v1/users/me", json={"medical_conditions": ["Thyroid"]}, headers=auth_headers
    )
    response = client.patch(
        "/api/v1/users/me", json={"medical_conditions": ["Hypertension"]}, headers=auth_headers
    )
    assert response.json()["medical_conditions"] == ["Hypertension"]


def test_delete_current_user(client, auth_headers):
    response = client.delete("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 204

    follow_up = client.get("/api/v1/users/me", headers=auth_headers)
    assert follow_up.status_code == 401
