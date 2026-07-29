import hashlib
import json as json_module
import logging
import ssl
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from app.core.config import Settings
from app.models import Company, Job

logger = logging.getLogger(__name__)


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


@dataclass(frozen=True)
class _TransportResponse:
    status_code: int
    content: bytes

    def json(self) -> Any:
        return json_module.loads(self.content)


_LINKEDIN_COMPANY_ID_CACHE: dict[tuple[str, str], str] = {}
_ACCOUNT_STATUS_CACHE: dict[
    tuple[str, str, str],
    tuple[float, ConnectSafelyAccount],
] = {}
_ACCOUNT_STATUS_ERROR_CACHE: dict[tuple[str, str, str], tuple[float, str]] = {}
_ACCOUNT_STATUS_LOCK = Lock()
_ACCOUNT_STATUS_CACHE_TTL_SECONDS = 60
_ACCOUNT_STATUS_STALE_TTL_SECONDS = 300
_ACCOUNT_STATUS_ERROR_TTL_SECONDS = 15
_MAX_RESPONSE_BYTES = 4 * 1024 * 1024


def _headers(settings: Settings) -> dict[str, str]:
    if not settings.connectsafely_api_key:
        raise ConnectSafelyUnavailable(
            "CONNECTSAFELY_API_KEY is not configured. Add a fresh key locally and restart."
        )
    return {
        "Authorization": f"Bearer {settings.connectsafely_api_key}",
        "Accept": "application/json",
        "Connection": "close",
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


def _connection_error_message(exc: ConnectionError) -> str:
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


def _read_json_response(response: Any) -> bytes:
    """Stop once a complete JSON document arrives, even if the server keeps the socket open."""
    content = bytearray()
    read_chunk = getattr(response, "read1", response.read)
    while len(content) < _MAX_RESPONSE_BYTES:
        chunk = read_chunk(min(64 * 1024, _MAX_RESPONSE_BYTES - len(content)))
        if not chunk:
            break
        content.extend(chunk)
        try:
            json_module.loads(content)
        except (UnicodeDecodeError, json_module.JSONDecodeError):
            continue
        return bytes(content)
    return bytes(content)


def _transport_request(
    method: str,
    url: str,
    *,
    settings: Settings,
    headers: dict[str, str],
    json: dict[str, Any] | None,
    params: dict[str, Any] | None,
    timeout: float,
) -> _TransportResponse:
    if params:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode(params)}"
    request = Request(
        url,
        data=json_module.dumps(json).encode("utf-8") if json is not None else None,
        headers=headers,
        method=method,
    )
    opener = build_opener(
        ProxyHandler({}),
        HTTPSHandler(context=_ssl_context(settings)),
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            return _TransportResponse(
                status_code=response.status,
                content=_read_json_response(response),
            )
    except HTTPError as exc:
        return _TransportResponse(
            status_code=exc.code,
            content=_read_json_response(exc),
        )
    except TimeoutError as exc:
        raise TimeoutError(str(exc)) from exc
    except URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise TimeoutError(str(exc.reason)) from exc
        raise ConnectionError(str(exc.reason)) from exc
    except OSError as exc:
        raise ConnectionError(str(exc)) from exc


def _request(
    settings: Settings,
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    retry_on_read_timeout: bool = False,
    prevent_duplicate_on_timeout: bool = False,
    timeout: float = 30,
) -> dict[str, Any]:
    attempts = 2 if retry_on_read_timeout else 1
    for attempt in range(attempts):
        try:
            response = _transport_request(
                method,
                f"{settings.connectsafely_base_url.rstrip('/')}{path}",
                settings=settings,
                headers=_headers(settings),
                json=json,
                params=params,
                timeout=timeout,
            )
            break
        except TimeoutError as exc:
            logger.warning(
                "ConnectSafely timeout method=%s path=%s attempt=%s/%s",
                method,
                path,
                attempt + 1,
                attempts,
            )
            if attempt + 1 < attempts:
                continue
            if prevent_duplicate_on_timeout:
                raise ConnectSafelyUnavailable(
                    "ConnectSafely did not confirm the response before timeout. "
                    "The request was not retried to prevent a duplicate LinkedIn message; "
                    "check the conversation before trying again."
                ) from exc
            if not retry_on_read_timeout:
                raise ConnectSafelyUnavailable(
                    f"ConnectSafely did not respond within {timeout:g} seconds. "
                    "The provider is temporarily slow or unavailable."
                ) from exc
            raise ConnectSafelyUnavailable(
                "ConnectSafely did not respond after two read attempts. "
                "The provider is temporarily slow or unavailable."
            ) from exc
        except ConnectionError as exc:
            raise ConnectSafelyUnavailable(_connection_error_message(exc)) from exc
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


def _account_status_cache_key(settings: Settings) -> tuple[str, str, str]:
    key_fingerprint = hashlib.sha256(
        (settings.connectsafely_api_key or "").encode("utf-8")
    ).hexdigest()
    return (
        settings.connectsafely_base_url.rstrip("/"),
        settings.connectsafely_account_id or "",
        key_fingerprint,
    )


def _fetch_account_status(settings: Settings) -> ConnectSafelyAccount:
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
            timeout=8,
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


def get_account_status(settings: Settings) -> ConnectSafelyAccount:
    cache_key = _account_status_cache_key(settings)
    cached = _ACCOUNT_STATUS_CACHE.get(cache_key)
    now = monotonic()
    if cached and now - cached[0] <= _ACCOUNT_STATUS_CACHE_TTL_SECONDS:
        return cached[1]
    cached_error = _ACCOUNT_STATUS_ERROR_CACHE.get(cache_key)
    if cached_error and now - cached_error[0] <= _ACCOUNT_STATUS_ERROR_TTL_SECONDS:
        raise ConnectSafelyUnavailable(cached_error[1])

    with _ACCOUNT_STATUS_LOCK:
        cached = _ACCOUNT_STATUS_CACHE.get(cache_key)
        now = monotonic()
        if cached and now - cached[0] <= _ACCOUNT_STATUS_CACHE_TTL_SECONDS:
            return cached[1]
        cached_error = _ACCOUNT_STATUS_ERROR_CACHE.get(cache_key)
        if cached_error and now - cached_error[0] <= _ACCOUNT_STATUS_ERROR_TTL_SECONDS:
            raise ConnectSafelyUnavailable(cached_error[1])
        try:
            account = _fetch_account_status(settings)
        except ConnectSafelyUnavailable as exc:
            if cached and now - cached[0] <= _ACCOUNT_STATUS_STALE_TTL_SECONDS:
                logger.warning("Using recently cached ConnectSafely account status")
                return cached[1]
            _ACCOUNT_STATUS_ERROR_CACHE[cache_key] = (monotonic(), str(exc))
            raise
        _ACCOUNT_STATUS_CACHE[cache_key] = (monotonic(), account)
        _ACCOUNT_STATUS_ERROR_CACHE.pop(cache_key, None)
        return account


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


def _company_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    companies = payload.get("companies")
    if isinstance(companies, list):
        return [item for item in companies if isinstance(item, dict)]
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("companies"), list):
        return [item for item in data["companies"] if isinstance(item, dict)]
    return []


def _first_string(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalized_company_name(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _resolve_linkedin_company_id(
    settings: Settings,
    company_name: str,
) -> str | None:
    normalized_name = _normalized_company_name(company_name)
    cache_key = (settings.connectsafely_account_id or "", normalized_name)
    if cache_key in _LINKEDIN_COMPANY_ID_CACHE:
        logger.info("ConnectSafely company ID cache hit company=%s", company_name)
        return _LINKEDIN_COMPANY_ID_CACHE[cache_key]
    body: dict[str, Any] = {
        "keywords": company_name,
        "count": 5,
        "start": 0,
        "filters": {},
    }
    if settings.connectsafely_account_id:
        body["accountId"] = settings.connectsafely_account_id
    logger.info("ConnectSafely company lookup started company=%s", company_name)
    try:
        payload = _request(
            settings,
            "POST",
            "/linkedin/search/companies",
            json=body,
        )
    except ConnectSafelyUnavailable as exc:
        raise ConnectSafelyUnavailable(
            f"LinkedIn company lookup failed for {company_name}: {exc}"
        ) from exc
    companies = _company_items(payload)
    exact_matches = [
        item
        for item in companies
        if any(
            _normalized_company_name(candidate_name) == normalized_name
            for candidate_name in (
                _first_string(item, "name") or "",
                _first_string(item, "universalName") or "",
            )
        )
    ]
    if not exact_matches:
        logger.info(
            "ConnectSafely company lookup returned no exact match company=%s candidates=%s",
            company_name,
            len(companies),
        )
        return None
    company_id = _first_string(exact_matches[0], "companyId", "id", "entityUrn")
    if company_id:
        _LINKEDIN_COMPANY_ID_CACHE[cache_key] = company_id
        logger.info(
            "ConnectSafely company lookup resolved company=%s company_id=%s",
            company_name,
            company_id,
        )
    return company_id


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
    linkedin_company_id = _resolve_linkedin_company_id(settings, company.name)
    filters: dict[str, Any] = (
        {"currentCompanyIds": [linkedin_company_id]}
        if linkedin_company_id
        else {"company": company.name}
    )
    body: dict[str, Any] = {
        "count": limit,
        "start": 0,
        "keywords": titles,
        "filters": filters,
    }
    if settings.connectsafely_account_id:
        body["accountId"] = settings.connectsafely_account_id
    logger.info(
        "ConnectSafely people search started company=%s company_id=%s limit=%s",
        company.name,
        linkedin_company_id or "name-filter",
        limit,
    )
    try:
        payload = _request(
            settings,
            "POST",
            "/linkedin/search/people",
            json=body,
        )
    except ConnectSafelyUnavailable as exc:
        raise ConnectSafelyUnavailable(
            f"LinkedIn people search failed for {company.name}: {exc}"
        ) from exc
    logger.info(
        "ConnectSafely people search completed company=%s results=%s",
        company.name,
        len(_items(payload)),
    )
    if not _items(payload) and linkedin_company_id:
        try:
            logger.info(
                "ConnectSafely people search v2 fallback started company=%s",
                company.name,
            )
            payload = _request(
                settings,
                "POST",
                "/linkedin/search/people/v2",
                json=body,
            )
            logger.info(
                "ConnectSafely people search v2 fallback completed company=%s results=%s",
                company.name,
                len(_items(payload)),
            )
        except ConnectSafelyUnavailable as exc:
            logger.warning(
                "ConnectSafely people search v2 fallback failed company=%s error=%s",
                company.name,
                exc,
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
            prevent_duplicate_on_timeout=True,
        )
    )
    message_id = data.get("messageId") or data.get("id")
    conversation_id = data.get("conversationUrn") or data.get("conversationId")
    return (
        str(message_id) if message_id else None,
        str(conversation_id) if conversation_id else None,
    )
