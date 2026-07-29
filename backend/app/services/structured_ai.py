import httpx
from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ValidationError

from app.core.config import Settings


class StructuredAIUnavailable(RuntimeError):
    pass


def selected_ai_provider(settings: Settings) -> str:
    configured = settings.ai_provider.strip().casefold()
    if configured == "auto":
        if settings.gemini_api_key:
            return "gemini"
        if settings.openai_api_key:
            return "openai"
        return "none"
    if configured not in {"gemini", "openai"}:
        raise StructuredAIUnavailable(
            "AI_PROVIDER must be auto, gemini, or openai"
        )
    return configured


def ai_is_configured(settings: Settings) -> bool:
    provider = selected_ai_provider(settings)
    return (
        provider == "gemini" and bool(settings.gemini_api_key)
    ) or (
        provider == "openai" and bool(settings.openai_api_key)
    )


def generate_structured[StructuredResult: BaseModel](
    settings: Settings,
    response_type: type[StructuredResult],
    system_prompt: str,
    user_prompt: str,
) -> StructuredResult:
    provider = selected_ai_provider(settings)
    if provider == "gemini":
        return _generate_with_gemini(
            settings,
            response_type,
            system_prompt,
            user_prompt,
        )
    if provider == "openai":
        return _generate_with_openai(
            settings,
            response_type,
            system_prompt,
            user_prompt,
        )
    raise StructuredAIUnavailable(
        "No AI key is configured. Add a fresh Gemini or OpenAI Platform key locally."
    )


def _generate_with_openai[StructuredResult: BaseModel](
    settings: Settings,
    response_type: type[StructuredResult],
    system_prompt: str,
    user_prompt: str,
) -> StructuredResult:
    if not settings.openai_api_key:
        raise StructuredAIUnavailable(
            "AI_PROVIDER is openai but OPENAI_API_KEY is not configured."
        )
    try:
        response = OpenAI(api_key=settings.openai_api_key).responses.parse(
            model=settings.openai_model,
            reasoning={"effort": "low"},
            input=[
                {"role": "developer", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            text_format=response_type,
        )
    except OpenAIError as exc:
        raise StructuredAIUnavailable(
            "OpenAI rejected the request. Verify that the local key is an active "
            "OpenAI Platform API key with API billing and model access."
        ) from exc
    if response.output_parsed is None:
        raise StructuredAIUnavailable("OpenAI did not return valid structured output.")
    return response.output_parsed


def _generate_with_gemini[StructuredResult: BaseModel](
    settings: Settings,
    response_type: type[StructuredResult],
    system_prompt: str,
    user_prompt: str,
) -> StructuredResult:
    if not settings.gemini_api_key:
        raise StructuredAIUnavailable(
            "AI_PROVIDER is gemini but GEMINI_API_KEY is not configured."
        )
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": response_type.model_json_schema(),
        },
    }
    try:
        response = httpx.post(
            (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{settings.gemini_model}:generateContent"
            ),
            headers={"x-goog-api-key": settings.gemini_api_key},
            json=body,
            timeout=httpx.Timeout(60, connect=15),
        )
        response.raise_for_status()
        payload = response.json()
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        return response_type.model_validate_json(text)
    except (
        httpx.HTTPError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        ValidationError,
    ) as exc:
        raise StructuredAIUnavailable(
            "Gemini rejected the request or returned invalid structured output. "
            "Verify the local key and model access."
        ) from exc
