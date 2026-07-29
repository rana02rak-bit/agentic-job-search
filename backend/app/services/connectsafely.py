import ssl
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import Settings
from app.models import Company, Job


class ConnectSafelyUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class ConnectSafelyAccount:
    connected: bool
    name: str | None
    account_id: str | None


@dataclass(frozen=True)
class DiscoveredContact:
    external_id: str | None
    name: str
    linkedin_url: str
    designation: str | None
    activity: str
    mutuals: int


def _headers(settings: Settings) -> dict[str, str]:
    if not settings.connectsafely_api_key:
        raise ConnectSafelyUnavailable(
            "CONNECTSAFELY_API_KEY is not configured. Add a fresh key locally and restart."
        )
    return {
        "Authorization": f"Bearer {settings.connectsafely_api_key}",
        "Content-Type": "application/json",
    }


def _ssl_context(settings: Settings) -> ssl.SSLContext:
    context = ssl.create_default_context()
    ca_bundle = settings.outbound_ca_bundle or settings.ats_ca_bundle
    if not ca_bundle:
        return context
    try:
        context.load_verify_locations(cafile=ca_bundle)
    except (OSError, ssl.SSLError) as exc:
        raise ConnectSafelyUnavailable(
            "The configured outbound CA bundle could not be loaded. "
            "Check OUTBOUND_CA_BUNDLE and restart the backend."
        ) from exc
    return context


def _connection_error_message(exc: httpx.ConnectError) -> str:
    detail = str(exc).casefold()
    if "certificate_verify_failed" in detail or "certificate verify failed" in detail:
        return (
            "ConnectSafely TLS verification failed. If your company network inspects HTTPS, "
            "save its approved root certificate in backend/certs and set "
            "OUTBOUND_CA_BUNDLE=/app/certs/company-root-ca.pem."
        )
    if (
        "name or service not known" in detail
        or "nodename nor servname" in detail
        or "temporary failure in name resolution" in detail
    ):
        return (
            "ConnectSafely DNS lookup failed inside Docker. Restart Docker Desktop and check "
            "its DNS/network settings."
        )
    if "timed out" in detail or "timeout" in detail:
        return (
            "ConnectSafely connection timed out. Check the company firewall or configure "
            "HTTPS_PROXY for the backend."
        )
    return (
        "Could not establish a network connection to ConnectSafely. "
        "Check Docker networking, firewall, proxy, and corporate CA settings."
    )


def _request(
    settings: Settings,
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    retry_on_read_timeout: bool = False,
) -> dict[str, Any]:
    attempts = 2 if retry_on_read_timeout else 1
    for attempt in range(attempts):
        try:
            response = httpx.request(
                method,
                f"{settings.connectsafely_base_url.rstrip('/')}{path}",
                headers=_headers(settings),
                json=json,
                params=params,
                timeout=httpx.Timeout(connect=15, read=90, write=30, pool=15),
                verify=_ssl_context(settings),
                trust_env=True,
            )
            break
        except httpx.ReadTimeout as exc:
            if attempt + 1 < attempts:
                continue
            if not retry_on_read_timeout:
                raise ConnectSafelyUnavailable(
                    "ConnectSafely did not confirm the response before timeout. "
                    "The request was not retried to prevent a duplicate LinkedIn message; "
                    "check the conversation before trying again."
                ) from exc
            raise ConnectSafelyUnavailable(
                "ConnectSafely did not respond after two read attempts. "
                "The provider is temporarily slow or unavailable."
            ) from exc
        except httpx.ConnectError as exc:
            raise ConnectSafelyUnavailable(_connection_error_message(exc)) from exc
        except httpx.HTTPError as exc:
            raise ConnectSafelyUnavailable(
                f"Could not reach ConnectSafely: {exc.__class__.__name__}"
            ) from exc
    if response.status_code >= 400:
        try:
            payload = response.json()
            detail = payload.get("message") or payload.get("error") or payload.get("detail")
        except (TypeError, ValueError):
            detail = None
        raise ConnectSafelyUnavailable(
            f"ConnectSafely request failed ({response.status_code})"
            + (f": {detail}" if isinstance(detail, str) else "")
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise ConnectSafelyUnavailable("ConnectSafely returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ConnectSafelyUnavailable("ConnectSafely returned an unexpected response")
    return payload


def _payload_data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def get_account_status(settings: Settings) -> ConnectSafelyAccount:
    params = (
        {"accountId": settings.connectsafely_account_id}
        if settings.connectsafely_account_id
        else None
    )
    data = _payload_data(
        _request(
            settings,
            "GET",
            "/linkedin/account/status",
            params=params,
            retry_on_read_timeout=True,
        )
    )
    status = str(
        data.get("status")
        or data.get("connectionStatus")
        or data.get("sessionStatus")
        or ""
    ).casefold()
    explicitly_connected = data.get("connected")
    enabled = data.get("enabled")
    has_tokens = data.get("hasTokens")
    connected_statuses = {
        "available",
        "in_use",
        "warmup",
        "connected",
        "active",
        "ready",
        "ok",
        "healthy",
    }
    if explicitly_connected is not None:
        connected = bool(explicitly_connected)
    else:
        connected = status in connected_statuses
    if enabled is False or has_tokens is False or status == "error":
        connected = False
    elif not status and (data.get("success") is True or (enabled and has_tokens)):
        connected = True
    name = (
        data.get("name")
        or data.get("accountName")
        or data.get("profileName")
        or data.get("publicIdentifier")
    )
    if not name:
        name = " ".join(
            part
            for part in (data.get("firstName"), data.get("lastName"))
            if isinstance(part, str) and part.strip()
        ).strip()
    account_id = data.get("accountId") or data.get("id")
    return ConnectSafelyAccount(
        connected=connected,
        name=str(name) if name else None,
        account_id=str(account_id) if account_id else settings.connectsafely_account_id,
    )


def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[Any] = [
        payload.get("people"),
        payload.get("items"),
        payload.get("results"),
    ]
    data = payload.get("data")
    if isinstance(data, list):
        candidates.append(data)
    elif isinstance(data, dict):
        candidates.extend(
            [
                data.get("people"),
                data.get("items"),
                data.get("results"),
                data.get("elements"),
            ]
        )
    candidates.append(payload.get("elements"))
    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def _first_string(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _profile_slug_from_url(url: str) -> str | None:
    path = urlparse(url).path.strip("/").split("/")
    if len(path) >= 2 and path[0].casefold() == "in":
        return path[1]
    return None


def linkedin_profile_slug(url: str) -> str:
    slug = _profile_slug_from_url(url)
    if not slug:
        raise ConnectSafelyUnavailable("Recipient does not have a valid LinkedIn profile URL")
    return slug


def _linkedin_url(item: dict[str, Any]) -> str | None:
    url = _first_string(
        item,
        "linkedinUrl",
        "linkedin_url",
        "profileUrl",
        "navigationUrl",
        "url",
    )
    if url and "linkedin.com/in/" in url.casefold():
        return url.split("?")[0].rstrip("/")
    slug = _first_string(
        item,
        "publicIdentifier",
        "public_identifier",
        "vanityName",
        "profileId",
    )
    return f"https://www.linkedin.com/in/{slug}" if slug else None


def discover_contacts(
    settings: Settings,
    company: Company,
    job: Job | None,
    limit: int,
) -> list[DiscoveredContact]:
    titles = (
        "Recruiter OR \"Talent Acquisition\" OR \"Talent Partner\" OR "
        "\"Hiring Manager\" OR \"Head of Product\" OR \"VP Product\" OR "
        "\"Chief of Staff\" OR Founder"
    )
    body: dict[str, Any] = {
        "count": limit,
        "start": 0,
        "keywords": titles,
        "filters": {
            "company": company.name,
        },
    }
    if settings.connectsafely_account_id:
        body["accountId"] = settings.connectsafely_account_id
    payload = _request(
        settings,
        "POST",
        "/linkedin/search/people",
        json=body,
        retry_on_read_timeout=True,
    )
    contacts: list[DiscoveredContact] = []
    seen: set[str] = set()
    for item in _items(payload):
        url = _linkedin_url(item)
        if not url or url.casefold() in seen:
            continue
        seen.add(url.casefold())
        name = _first_string(item, "name", "fullName")
        if not name:
            first = _first_string(item, "firstName") or ""
            last = _first_string(item, "lastName") or ""
            name = " ".join(part for part in (first, last) if part).strip()
        contacts.append(
            DiscoveredContact(
                external_id=_first_string(
                    item,
                    "entityUrn",
                    "profileUrn",
                    "publicIdentifier",
                    "trackingId",
                ),
                name=name or "LinkedIn contact",
                linkedin_url=url,
                designation=_first_string(item, "headline", "title", "jobTitle"),
                activity=f"Discovered for {company.name} with ConnectSafely people search.",
                mutuals=int(item.get("mutualConnectionsCount") or item.get("mutuals") or 0),
            )
        )
        if len(contacts) >= limit:
            break
    return contacts


def send_linkedin_message(
    settings: Settings,
    linkedin_url: str,
    message: str,
    subject: str | None = None,
) -> tuple[str | None, str | None]:
    body: dict[str, Any] = {
        "recipientProfileId": linkedin_profile_slug(linkedin_url),
        "message": message,
        "messagingChannel": "auto",
        "attachments": [],
    }
    if settings.connectsafely_account_id:
        body["accountId"] = settings.connectsafely_account_id
    if subject:
        body["subject"] = subject
    data = _payload_data(
        _request(
            settings,
            "POST",
            "/linkedin/conversations/send",
            json=body,
        )
    )
    message_id = data.get("messageId") or data.get("id")
    conversation_id = data.get("conversationUrn") or data.get("conversationId")
    return (
        str(message_id) if message_id else None,
        str(conversation_id) if conversation_id else None,
    )
