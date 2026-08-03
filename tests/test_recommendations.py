import httpx
import pytest
from openai import RateLimitError

from app.core.exceptions import AIServiceUnavailableError
from app.schemas.recommendation import MealSuggestionOut, RecommendationOut
from app.services.ai import recommendation_service


def _fake_recommendation() -> RecommendationOut:
    return RecommendationOut(
        summary="Great progress today! Here's what I'd suggest next.",
        meal_suggestions=[
            MealSuggestionOut(
                name="Moong dal khichdi",
                reason="Low-GI, budget-friendly",
                est_cost=80,
                est_calories=350,
            )
        ],
        hydration_tip="You're at 60% of your water goal — have a glass now.",
        warnings=["Avoided high-sugar suggestions due to Diabetes"],
    )


@pytest.fixture()
def mock_generate(monkeypatch):
    calls = []

    def _fake(context: dict):
        calls.append(context)
        return _fake_recommendation(), "gpt-4.1-mini"

    monkeypatch.setattr(recommendation_service, "generate_recommendation", _fake)
    return calls


def test_generate_recommendation_returns_and_persists(client, auth_headers, mock_generate):
    response = client.post("/api/v1/recommendations", headers=auth_headers)
    assert response.status_code == 201
    body = response.json()

    assert body["summary"]
    assert len(body["meal_suggestions"]) == 1
    assert body["warnings"] == ["Avoided high-sugar suggestions due to Diabetes"]
    assert len(mock_generate) == 1


def test_generate_recommendation_context_includes_profile_and_water(
    client, auth_headers, mock_generate
):
    client.post("/api/v1/recommendations", headers=auth_headers)
    context = mock_generate[0]

    assert "profile" in context
    assert "metrics" in context
    assert "recent_meals" in context
    assert "water_today" in context
    assert context["profile"]["diet_preference"] == "veg"


def test_latest_recommendation_returns_404_before_any_generated(client, auth_headers):
    response = client.get("/api/v1/recommendations/latest", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "no_recommendations"


def test_latest_recommendation_after_generating_does_not_call_openai_again(
    client, auth_headers, mock_generate
):
    client.post("/api/v1/recommendations", headers=auth_headers)
    response = client.get("/api/v1/recommendations/latest", headers=auth_headers)

    assert response.status_code == 200
    assert len(mock_generate) == 1  # /latest must not trigger another AI call


def test_recommendation_history_lists_past_recommendations(client, auth_headers, mock_generate):
    client.post("/api/v1/recommendations", headers=auth_headers)
    client.post("/api/v1/recommendations", headers=auth_headers)

    response = client.get("/api/v1/recommendations/history", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


class _RaisingCompletions:
    def __init__(self, error: Exception):
        self._error = error

    def create(self, **kwargs):
        raise self._error


class _RaisingChat:
    def __init__(self, error: Exception):
        self.completions = _RaisingCompletions(error)


class _RaisingClient:
    def __init__(self, error: Exception):
        self.chat = _RaisingChat(error)


def _make_rate_limit_error() -> RateLimitError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(status_code=429, request=request)
    return RateLimitError("slow down", response=response, body=None)


def test_openai_rate_limit_error_maps_to_503(monkeypatch):
    """Exercises the real error-mapping code in generate_recommendation, not a stub."""
    fake_client = _RaisingClient(_make_rate_limit_error())
    # recommendation_service does `from ...openai_client import get_openai_client`,
    # so the name to patch is the one bound in recommendation_service's namespace —
    # patching openai_client.get_openai_client itself would not be seen there.
    monkeypatch.setattr(recommendation_service, "get_openai_client", lambda: fake_client)

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        recommendation_service.generate_recommendation({"profile": {}})

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "ai_rate_limited"


def test_recommendation_endpoint_maps_rate_limit_to_503(client, auth_headers, monkeypatch):
    fake_client = _RaisingClient(_make_rate_limit_error())
    # recommendation_service does `from ...openai_client import get_openai_client`,
    # so the name to patch is the one bound in recommendation_service's namespace —
    # patching openai_client.get_openai_client itself would not be seen there.
    monkeypatch.setattr(recommendation_service, "get_openai_client", lambda: fake_client)

    response = client.post("/api/v1/recommendations", headers=auth_headers)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ai_rate_limited"
