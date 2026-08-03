import json

import httpx
import pytest
from openai import RateLimitError

from app.core.exceptions import AIResponseInvalidError, AIServiceUnavailableError
from app.services.ai import vision_service


class _FakeMessage:
    def __init__(self, content: str | None, refusal: str | None = None):
        self.content = content
        self.refusal = refusal


class _FakeChoice:
    def __init__(self, message: _FakeMessage):
        self.message = message


class _FakeResponse:
    def __init__(self, message: _FakeMessage):
        self.choices = [_FakeChoice(message)]


class _RespondingCompletions:
    def __init__(self, response=None, error: Exception | None = None):
        self._response = response
        self._error = error

    def create(self, **kwargs):
        if self._error:
            raise self._error
        return self._response


class _RespondingChat:
    def __init__(self, **kwargs):
        self.completions = _RespondingCompletions(**kwargs)


class _FakeClient:
    def __init__(self, **kwargs):
        self.chat = _RespondingChat(**kwargs)


def _valid_payload() -> str:
    return json.dumps(
        {
            "items": [
                {
                    "name": "Idli",
                    "quantity_value": 150,
                    "quantity_unit": "g",
                    "bbox": [0.1, 0.2, 0.3, 0.4],
                    "approx_calories": 195,
                    "protein_g": 4.5,
                    "fat_g": 3.2,
                    "confidence": 0.9,
                }
            ]
        }
    )


def test_analyze_food_image_parses_valid_response(monkeypatch):
    fake_client = _FakeClient(response=_FakeResponse(_FakeMessage(_valid_payload())))
    monkeypatch.setattr(vision_service, "get_openai_client", lambda: fake_client)

    items = vision_service.analyze_food_image(b"fake-bytes")

    assert len(items) == 1
    assert items[0].name == "Idli"
    assert items[0].bbox == (0.1, 0.2, 0.3, 0.4)


def test_analyze_food_image_clamps_out_of_range_bbox(monkeypatch):
    payload = json.dumps(
        {
            "items": [
                {
                    "name": "Weird",
                    "quantity_value": 1,
                    "quantity_unit": "piece",
                    "bbox": [-0.5, 0.0, 1.5, 1.0],
                    "approx_calories": 100,
                    "protein_g": 2.0,
                    "fat_g": 1.0,
                    "confidence": 0.5,
                }
            ]
        }
    )
    fake_client = _FakeClient(response=_FakeResponse(_FakeMessage(payload)))
    monkeypatch.setattr(vision_service, "get_openai_client", lambda: fake_client)

    items = vision_service.analyze_food_image(b"fake-bytes")

    assert items[0].bbox == (0.0, 0.0, 1.0, 1.0)


def test_analyze_food_image_empty_items_for_non_food_photo(monkeypatch):
    payload = json.dumps({"items": []})
    fake_client = _FakeClient(response=_FakeResponse(_FakeMessage(payload)))
    monkeypatch.setattr(vision_service, "get_openai_client", lambda: fake_client)

    assert vision_service.analyze_food_image(b"fake-bytes") == []


def test_analyze_food_image_raises_on_refusal(monkeypatch):
    fake_client = _FakeClient(response=_FakeResponse(_FakeMessage(None, refusal="can't help")))
    monkeypatch.setattr(vision_service, "get_openai_client", lambda: fake_client)

    with pytest.raises(AIResponseInvalidError) as exc_info:
        vision_service.analyze_food_image(b"fake-bytes")
    assert exc_info.value.code == "ai_refusal"


def test_analyze_food_image_raises_on_malformed_json(monkeypatch):
    fake_client = _FakeClient(response=_FakeResponse(_FakeMessage("not valid json")))
    monkeypatch.setattr(vision_service, "get_openai_client", lambda: fake_client)

    with pytest.raises(AIResponseInvalidError) as exc_info:
        vision_service.analyze_food_image(b"fake-bytes")
    assert exc_info.value.code == "ai_invalid_json"


def test_analyze_food_image_raises_on_empty_content(monkeypatch):
    fake_client = _FakeClient(response=_FakeResponse(_FakeMessage("")))
    monkeypatch.setattr(vision_service, "get_openai_client", lambda: fake_client)

    with pytest.raises(AIResponseInvalidError) as exc_info:
        vision_service.analyze_food_image(b"fake-bytes")
    assert exc_info.value.code == "ai_empty_response"


def test_analyze_food_image_maps_rate_limit_to_503(monkeypatch):
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(status_code=429, request=request)
    error = RateLimitError("slow down", response=response, body=None)

    fake_client = _FakeClient(error=error)
    monkeypatch.setattr(vision_service, "get_openai_client", lambda: fake_client)

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        vision_service.analyze_food_image(b"fake-bytes")
    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "ai_rate_limited"


@pytest.mark.parametrize(
    "raw_bytes,expected_mime",
    [
        (b"\x89PNG\r\n\x1a\n rest", "image/png"),
        (b"RIFF????WEBPVP8 ", "image/webp"),
        (b"\xff\xd8\xff rest", "image/jpeg"),
    ],
)
def test_guess_image_mime(raw_bytes, expected_mime):
    assert vision_service._guess_image_mime(raw_bytes) == expected_mime
