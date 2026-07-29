import ssl
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import get_settings


class AtsFetchError(RuntimeError):
    """Raised when a configured ATS board cannot be read."""


@dataclass(frozen=True, slots=True)
class AtsJob:
    external_id: str
    title: str
    location: str
    url: str
    posted_at: datetime | None = None


def fetch_json(url: str, client: httpx.Client | None = None) -> Any:
    owns_client = client is None
    ssl_context = ssl.create_default_context()
    ca_bundle = get_settings().ats_ca_bundle
    if ca_bundle:
        try:
            ssl_context.load_verify_locations(cafile=ca_bundle)
        except (OSError, ssl.SSLError) as exc:
            raise AtsFetchError(f"ATS_CA_BUNDLE could not be loaded: {exc}") from exc
    active_client = client or httpx.Client(
        timeout=httpx.Timeout(20.0),
        headers={"User-Agent": "RahulGPT-Job-Discovery/0.2"},
        follow_redirects=True,
        verify=ssl_context,
    )
    try:
        response = active_client.get(url, headers={"Accept": "application/json"})
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError as exc:
        if "CERTIFICATE_VERIFY_FAILED" in str(exc):
            raise AtsFetchError(
                "TLS certificate verification failed. Rebuild the backend to install current "
                "root certificates; on a company network, add its root CA with ATS_CA_BUNDLE."
            ) from exc
        raise AtsFetchError(f"Could not read ATS board: {exc}") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise AtsFetchError(f"Could not read ATS board: {exc}") from exc
    finally:
        if owns_client:
            active_client.close()


def as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def parse_datetime(value: object) -> datetime | None:
    if isinstance(value, int | float):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, tz=UTC)
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def clean_text(value: object, fallback: str = "") -> str:
    if not isinstance(value, str):
        return fallback
    return " ".join(value.split()) or fallback
