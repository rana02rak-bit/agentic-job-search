import httpx

from app.core.config import Settings
from app.schemas import SuggestionBatch

TARGET_PROFILE = """
Candidate: Rahul
Preferred locations, in order: Bangalore, Gurgaon, Mumbai, Remote.
Target roles: Product Manager, Senior Product Manager, Associate Product Manager,
Founder's Office, Chief of Staff, Strategy, AI Product, AI Strategy, Growth, Platform PM.
Company priorities: AI-first, B2C, consumer internet, recently funded, actively hiring,
Series A through Series D.
"""


class DiscoveryUnavailableError(RuntimeError):
    pass


def generate_company_suggestions(
    settings: Settings,
    existing_company_names: list[str],
    count: int,
) -> SuggestionBatch:
    if not settings.gemini_api_key:
        raise DiscoveryUnavailableError(
            "GEMINI_API_KEY is not configured. Manual watchlist features remain available."
        )

    existing = ", ".join(existing_company_names) if existing_company_names else "None"
    body = {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "Suggest Indian or India-hiring companies that fit the candidate profile. "
                        "Return candidates for further verification, not claims of live vacancies. "
                        "Do not repeat an existing company. Score each dimension from 0 to 10. "
                        "Keep reasons factual, concise, and explicit about anything needing "
                        "verification."
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            f"{TARGET_PROFILE}\n"
                            f"Existing companies to exclude: {existing}\n"
                            f"Return exactly {count} suggestions."
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": SuggestionBatch.model_json_schema(),
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
        return SuggestionBatch.model_validate_json(text)
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise DiscoveryUnavailableError(
            "Gemini did not return valid structured company suggestions"
        ) from exc
