from openai import OpenAI

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
    if not settings.openai_api_key:
        raise DiscoveryUnavailableError(
            "OPENAI_API_KEY is not configured. Manual watchlist features remain available."
        )

    client = OpenAI(api_key=settings.openai_api_key)
    existing = ", ".join(existing_company_names) if existing_company_names else "None"
    response = client.responses.parse(
        model=settings.openai_model,
        reasoning={"effort": "low"},
        input=[
            {
                "role": "developer",
                "content": (
                    "Suggest Indian or India-hiring companies that fit the candidate profile. "
                    "Return candidates for further verification, not claims of live vacancies. "
                    "Do not repeat an existing company. Score each dimension from 0 to 10. "
                    "Keep reasons factual, concise, and explicit about anything needing "
                    "verification."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{TARGET_PROFILE}\n"
                    f"Existing companies to exclude: {existing}\n"
                    f"Return exactly {count} suggestions."
                ),
            },
        ],
        text_format=SuggestionBatch,
    )
    if response.output_parsed is None:
        raise DiscoveryUnavailableError("The model did not return structured suggestions.")
    return response.output_parsed
