from app.core.config import Settings
from app.schemas import SuggestionBatch
from app.services.structured_ai import (
    StructuredAIUnavailable,
    generate_structured,
)

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
    existing = ", ".join(existing_company_names) if existing_company_names else "None"
    try:
        return generate_structured(
            settings,
            SuggestionBatch,
            (
                "Suggest Indian or India-hiring companies that fit the candidate profile. "
                "Return candidates for further verification, not claims of live vacancies. "
                "Do not repeat an existing company. Score each dimension from 0 to 10. "
                "Keep reasons factual, concise, and explicit about anything needing verification."
            ),
            (
                f"{TARGET_PROFILE}\n"
                f"Existing companies to exclude: {existing}\n"
                f"Return exactly {count} suggestions."
            ),
        )
    except StructuredAIUnavailable as exc:
        raise DiscoveryUnavailableError(str(exc)) from exc
