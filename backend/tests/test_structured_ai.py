import pytest

from app.core.config import Settings
from app.services.structured_ai import (
    StructuredAIUnavailable,
    ai_is_configured,
    selected_ai_provider,
)


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
