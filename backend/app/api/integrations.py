from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas import IntegrationStatus
from app.services.connectsafely import (
    ConnectSafelyUnavailable,
    get_account_status,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/status", response_model=IntegrationStatus)
def integration_status() -> IntegrationStatus:
    settings = get_settings()
    configured = bool(settings.connectsafely_api_key)
    connected = False
    account_name = None
    if configured:
        try:
            account = get_account_status(settings)
            connected = account.connected
            account_name = account.name
        except ConnectSafelyUnavailable:
            connected = False

    missing: list[str] = []
    if not settings.gemini_api_key:
        missing.append("GEMINI_API_KEY")
    if not configured:
        missing.append("CONNECTSAFELY_API_KEY")
    elif not connected:
        missing.append("Connect LinkedIn in ConnectSafely")
    return IntegrationStatus(
        gemini_configured=bool(settings.gemini_api_key),
        connectsafely_configured=configured,
        connectsafely_account_connected=connected,
        connectsafely_account_name=account_name,
        ready_for_contact_discovery=configured and connected,
        ready_for_linkedin_sending=configured and connected,
        missing=missing,
    )
