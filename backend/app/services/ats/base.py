from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx


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
    active_client = client or httpx.Client(
        timeout=httpx.Timeout(20.0),
        headers={"User-Agent": "RahulGPT-Job-Discovery/0.2"},
        follow_redirects=True,
    )
    try:
        response = active_client.get(url, headers={"Accept": "application/json"})
        response.raise_for_status()
        return response.json()
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
