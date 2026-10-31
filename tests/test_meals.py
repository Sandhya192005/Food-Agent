import io

import pytest
from PIL import Image

from app.services.ai import vision_service
from app.services.meal_validation import RawFoodItem
from app.services.storage import factory


def _jpeg_bytes(color=(200, 150, 100)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), color=color).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture()
def mock_vision(monkeypatch):
    def _fake_analyze(image_bytes: bytes) -> list[RawFoodItem]:
        return [
            RawFoodItem("Idli", 150, "g", (0.1, 0.2, 0.3, 0.4), 195, 0.9),
            RawFoodItem("Sambar", 150, "g", (0.5, 0.2, 0.8, 0.4), 120, 0.8),
        ]

    calls = []
    original = _fake_analyze

    def _tracked(image_bytes: bytes) -> list[RawFoodItem]:
        calls.append(image_bytes)
        return original(image_bytes)

    monkeypatch.setattr(vision_service, "analyze_food_image", _tracked)
    return calls


def test_analyze_meal_persists_items_and_returns_response(client, auth_headers, mock_vision):
    response = client.post(
        "/api/v1/meals/analyze",
        headers=auth_headers,
        files={"file": ("meal.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["is_duplicate"] is False
    assert body["total_calories"] == 315.0
    assert {item["name"] for item in body["items"]} == {"Idli", "Sambar"}
    assert len(mock_vision) == 1


def test_analyze_meal_rejects_unsupported_content_type(client, auth_headers, mock_vision):
    response = client.post(
        "/api/v1/meals/analyze",
        headers=auth_headers,
        files={"file": ("meal.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_image_type"
    assert len(mock_vision) == 0


def test_analyze_meal_rejects_corrupt_image_bytes(client, auth_headers, mock_vision):
    response = client.post(
        "/api/v1/meals/analyze",
        headers=auth_headers,
        files={"file": ("meal.jpg", b"totally not a jpeg", "image/jpeg")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "corrupt_image"
    assert len(mock_vision) == 0


def test_duplicate_upload_within_window_skips_second_vision_call(client, auth_headers, mock_vision):
    image_bytes = _jpeg_bytes()

    first = client.post(
        "/api/v1/meals/analyze",
        headers=auth_headers,
        files={"file": ("meal.jpg", image_bytes, "image/jpeg")},
    )
    second = client.post(
        "/api/v1/meals/analyze",
        headers=auth_headers,
        files={"file": ("meal.jpg", image_bytes, "image/jpeg")},
    )

    assert first.json()["is_duplicate"] is False
    assert second.json()["is_duplicate"] is True
    assert second.json()["meal_id"] == first.json()["meal_id"]
    assert len(mock_vision) == 1  # second upload never called the vision service


def test_list_and_get_and_delete_meal(client, auth_headers, mock_vision):
    upload = client.post(
        "/api/v1/meals/analyze",
        headers=auth_headers,
        files={"file": ("meal.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    meal_id = upload.json()["meal_id"]

    listing = client.get("/api/v1/meals", headers=auth_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["title"] == "Idli, Sambar"
    # Photo meals get their meal type from the time they were eaten.
    assert listing.json()[0]["meal_type"] in {"breakfast", "lunch", "dinner", "snack"}

    detail = client.get(f"/api/v1/meals/{meal_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert len(detail.json()["items"]) == 2

    delete = client.delete(f"/api/v1/meals/{meal_id}", headers=auth_headers)
    assert delete.status_code == 204

    follow_up = client.get(f"/api/v1/meals/{meal_id}", headers=auth_headers)
    assert follow_up.status_code == 404


def test_meal_not_found_for_other_users_meal(client, auth_headers, mock_vision):
    upload = client.post(
        "/api/v1/meals/analyze",
        headers=auth_headers,
        files={"file": ("meal.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    meal_id = upload.json()["meal_id"]

    other_signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "other@example.com",
            "password": "supersecret123",
            "preferred_name": "Other",
            "age": 25,
            "gender": "female",
            "height_cm": 160,
            "weight_kg": 55,
            "medical_conditions": [],
            "goal": "maintain_weight",
            "diet_preference": "veg",
            "activity_level": "light",
            "timezone": "UTC",
        },
    ).json()
    other_headers = {"Authorization": f"Bearer {other_signup['tokens']['access_token']}"}

    response = client.get(f"/api/v1/meals/{meal_id}", headers=other_headers)
    assert response.status_code == 404
    # Nor can they fetch its photo.
    response = client.get(f"/api/v1/meals/{meal_id}/image", headers=other_headers)
    assert response.status_code == 404


def test_meal_photo_is_stored_and_can_be_fetched(
    client, auth_headers, mock_vision, photo_storage, db_session
):
    from app.models.meal import Meal

    photo = _jpeg_bytes()
    upload = client.post(
        "/api/v1/meals/analyze",
        headers=auth_headers,
        files={"file": ("meal.jpg", photo, "image/jpeg")},
    )
    meal_id = upload.json()["meal_id"]

    # The database keeps the photo's key and which storage holds it.
    meal = db_session.get(Meal, meal_id)
    assert meal.image_storage == "local"
    assert meal.image_key.startswith(f"meals/user-{meal.user_id}/")
    assert meal.image_key.endswith(".jpg")

    detail = client.get(f"/api/v1/meals/{meal_id}", headers=auth_headers).json()
    assert detail["has_image"] is True
    assert detail["image_url"] is None  # local disk has no direct link

    image = client.get(f"/api/v1/meals/{meal_id}/image", headers=auth_headers)
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/jpeg"
    assert image.content == photo

    # Deleting the meal removes the photo too.
    client.delete(f"/api/v1/meals/{meal_id}", headers=auth_headers)
    assert not (photo_storage.root / meal.image_key).exists()


def test_meal_detail_uses_s3_link_for_s3_photos(
    client, auth_headers, mock_vision, monkeypatch, db_session
):
    from app.models.meal import Meal
    from app.services.storage.base import StorageBackend

    class FakeS3(StorageBackend):
        name = "s3"

        def __init__(self):
            self.objects = {}

        def save(self, content, filename, *, folder="", content_type=None):
            key = f"{folder}/abc.jpg"
            self.objects[key] = content
            return key

        def delete(self, key):
            self.objects.pop(key, None)

        def read(self, key):
            return self.objects[key]

        def url_for(self, key):
            return f"https://bucket.s3.amazonaws.com/{key}?X-Amz-Signature=sig"

    fake = FakeS3()
    monkeypatch.setattr(factory, "get_storage", lambda name: fake)

    upload = client.post(
        "/api/v1/meals/analyze",
        headers=auth_headers,
        files={"file": ("meal.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    meal_id = upload.json()["meal_id"]
    meal = db_session.get(Meal, meal_id)
    assert meal.image_storage == "s3"
    assert meal.image_key in fake.objects

    detail = client.get(f"/api/v1/meals/{meal_id}", headers=auth_headers).json()
    assert detail["image_url"].startswith(f"https://bucket.s3.amazonaws.com/{meal.image_key}")


def test_menu_meal_has_no_photo(client, auth_headers, db_session, test_user):
    from datetime import UTC, datetime

    from app.models.meal import Meal

    meal = Meal(
        user_id=test_user.id,
        source="menu_template",
        status="analyzed",
        total_calories=300,
        captured_at=datetime.now(UTC),
    )
    db_session.add(meal)
    db_session.commit()

    detail = client.get(f"/api/v1/meals/{meal.id}", headers=auth_headers).json()
    assert detail["has_image"] is False
    response = client.get(f"/api/v1/meals/{meal.id}/image", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "meal_image_not_found"


def test_meal_type_for_time_uses_meal_windows():
    from datetime import time

    from app.core.constants import MealType, meal_type_for_time

    assert meal_type_for_time(time(9, 30)) == MealType.BREAKFAST
    assert meal_type_for_time(time(14, 0)) == MealType.LUNCH
    assert meal_type_for_time(time(20, 0)) == MealType.DINNER
    assert meal_type_for_time(time(16, 0)) == MealType.SNACK
