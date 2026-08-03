SIGNUP_PAYLOAD = {
    "email": "newuser@example.com",
    "password": "supersecret123",
    "preferred_name": "New User",
    "age": 30,
    "gender": "female",
    "height_cm": 165,
    "weight_kg": 60,
    "medical_conditions": ["PCOS", "diabetes"],
    "goal": "maintain_weight",
    "diet_preference": "vegan",
    "activity_level": "light",
    "daily_budget": 300,
    "timezone": "Asia/Kolkata",
}


def test_signup_creates_user_with_computed_metrics(client):
    response = client.post("/api/v1/auth/signup", json=SIGNUP_PAYLOAD)
    assert response.status_code == 201
    body = response.json()

    assert body["user"]["email"] == "newuser@example.com"
    assert set(body["user"]["medical_conditions"]) == {"PCOS", "Diabetes"}
    assert body["user"]["metrics"]["bmi"] is not None
    assert body["user"]["metrics"]["bmr"] is not None
    assert body["user"]["metrics"]["tdee"] is not None
    assert body["user"]["metrics"]["daily_water_goal_ml"] is not None
    assert "access_token" in body["tokens"]
    assert "refresh_token" in body["tokens"]


def test_signup_rejects_duplicate_email(client):
    client.post("/api/v1/auth/signup", json=SIGNUP_PAYLOAD)
    response = client.post("/api/v1/auth/signup", json=SIGNUP_PAYLOAD)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


def test_signup_rejects_missing_required_fields(client):
    response = client.post("/api/v1/auth/signup", json={"email": "x@example.com"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_login_success(client):
    client.post("/api/v1/auth/signup", json=SIGNUP_PAYLOAD)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": SIGNUP_PAYLOAD["password"]},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_rejects_wrong_password(client):
    client.post("/api/v1/auth/signup", json=SIGNUP_PAYLOAD)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_protected_route_rejects_missing_token(client):
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401


def test_protected_route_rejects_garbage_token(client):
    response = client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


def test_protected_route_accepts_valid_token(client, auth_headers):
    response = client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200


def test_refresh_rotates_token_and_invalidates_old_one(client):
    signup = client.post("/api/v1/auth/signup", json=SIGNUP_PAYLOAD).json()
    old_refresh = signup["tokens"]["refresh_token"]

    first = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert first.status_code == 200
    new_refresh = first.json()["refresh_token"]
    assert new_refresh != old_refresh

    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "invalid_refresh_token"


def test_logout_revokes_refresh_token(client):
    signup = client.post("/api/v1/auth/signup", json=SIGNUP_PAYLOAD).json()
    refresh_token = signup["tokens"]["refresh_token"]

    logout = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout.status_code == 204

    attempt = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert attempt.status_code == 401
