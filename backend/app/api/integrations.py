from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas import IntegrationStatus
from app.services.connectsafely import (
    ConnectSafelyUnavailable,
    get_account_status,
)
from app.services.structured_ai import (
    StructuredAIUnavailable,
    ai_is_configured,
    selected_ai_provider,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/status", response_model=IntegrationStatus)
def integration_status() -> IntegrationStatus:
    settings = get_settings()
    try:
        ai_provider = selected_ai_provider(settings)
        ai_configured = ai_is_configured(settings)
    except StructuredAIUnavailable:
        ai_provider = settings.ai_provider
        ai_configured = False
    configured = bool(settings.connectsafely_api_key)
    targeted_account = bool(settings.connectsafely_account_id)
    connected = False
    account_name = None
    connectsafely_error = None
    if configured:
        try:
            account = get_account_status(settings)
            connected = account.connected
            account_name = account.name
        except ConnectSafelyUnavailable as exc:
            connected = False
            connectsafely_error = str(exc)

    missing: list[str] = []
    if not ai_configured:
        missing.append(
            "GEMINI_API_KEY or OPENAI_API_KEY"
            if settings.ai_provider.casefold() == "auto"
            else f"{settings.ai_provider.upper()} API key"
        )
    if not configured:
        missing.append("CONNECTSAFELY_API_KEY")
    elif not connected and not targeted_account:
        missing.append("Connect LinkedIn in ConnectSafely")
    return IntegrationStatus(
        ai_provider=ai_provider,
        ai_configured=ai_configured,
        gemini_configured=bool(settings.gemini_api_key),
        openai_configured=bool(settings.openai_api_key),
        connectsafely_configured=configured,
        connectsafely_account_connected=connected,
        connectsafely_account_name=account_name,
        connectsafely_error=connectsafely_error,
        ready_for_contact_discovery=configured and (connected or targeted_account),
        ready_for_linkedin_sending=configured and (connected or targeted_account),
        missing=missing,
    )
