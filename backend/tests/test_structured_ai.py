import httpx
import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.services.structured_ai import (
    StructuredAIUnavailable,
    ai_is_configured,
    generate_structured,
    selected_ai_provider,
)


class ExampleResult(BaseModel):
    answer: str


def test_auto_provider_prefers_gemini_when_both_keys_exist() -> None:
    settings = Settings(
        ai_provider="auto",
        gemini_api_key="gemini-test",
        openai_api_key="openai-test",
    )
    assert selected_ai_provider(settings) == "gemini"
    assert ai_is_configured(settings) is True


def test_auto_provider_falls_back_to_openai() -> None:
    settings = Settings(
        ai_provider="auto",
        gemini_api_key=None,
        openai_api_key="openai-test",
    )
    assert selected_ai_provider(settings) == "openai"
    assert ai_is_configured(settings) is True


def test_explicit_provider_requires_its_own_key() -> None:
    settings = Settings(
        ai_provider="openai",
        gemini_api_key="gemini-test",
        openai_api_key=None,
    )
    assert selected_ai_provider(settings) == "openai"
    assert ai_is_configured(settings) is False


def test_invalid_provider_is_rejected() -> None:
    with pytest.raises(StructuredAIUnavailable):
        selected_ai_provider(Settings(ai_provider="unknown"))


def test_gemini_uses_current_structured_output_format(monkeypatch) -> None:
    captured: dict = {}

    class Response:
        status_code = 200

        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict:
            return {
                "candidates": [
                    {"content": {"parts": [{"text": '{"answer":"working"}'}]}}
                ]
            }

    def fake_post(*_args, **kwargs) -> Response:
        captured["body"] = kwargs["json"]
        return Response()

    monkeypatch.setattr("app.services.structured_ai.httpx.post", fake_post)

    result = generate_structured(
        Settings(ai_provider="gemini", gemini_api_key="test-key"),
        ExampleResult,
        "System",
        "User",
    )

    assert result.answer == "working"
    generation_config = captured["body"]["generationConfig"]
    assert generation_config["responseFormat"]["text"]["mimeType"] == "application/json"
    assert generation_config["responseFormat"]["text"]["schema"]["type"] == "object"
    assert "responseJsonSchema" not in generation_config


def test_gemini_retries_legacy_structured_output_on_bad_request(monkeypatch) -> None:
    captured_bodies: list[dict] = []

    def fake_post(url: str, **kwargs) -> httpx.Response:
        captured_bodies.append(kwargs["json"])
        request = httpx.Request("POST", url)
        if len(captured_bodies) == 1:
            return httpx.Response(
                400,
                json={"error": {"message": "Unknown structured output field"}},
                request=request,
            )
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": '{"answer":"legacy works"}'}]}}
                ]
            },
            request=request,
        )

    monkeypatch.setattr("app.services.structured_ai.httpx.post", fake_post)

    result = generate_structured(
        Settings(ai_provider="gemini", gemini_api_key="test-key"),
        ExampleResult,
        "System",
        "User",
    )

    assert result.answer == "legacy works"
    assert len(captured_bodies) == 2
    legacy_config = captured_bodies[1]["generationConfig"]
    assert legacy_config["responseMimeType"] == "application/json"
    assert legacy_config["responseJsonSchema"]["type"] == "object"
