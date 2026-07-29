from typing import Any
from urllib.parse import quote

import httpx

from app.services.ats.base import (
    AtsFetchError,
    AtsJob,
    as_mapping,
    clean_text,
    fetch_json,
    parse_datetime,
)


def parse_greenhouse_jobs(payload: object) -> list[AtsJob]:
    root = as_mapping(payload)
    raw_jobs = root.get("jobs")
    if not isinstance(raw_jobs, list):
        return []

    jobs: list[AtsJob] = []
    for raw in raw_jobs:
        item = as_mapping(raw)
        location = as_mapping(item.get("location"))
        external_id = str(item.get("id") or "")
        title = clean_text(item.get("title"))
        url = clean_text(item.get("absolute_url"))
        if not external_id or not title or not url:
            continue
        jobs.append(
            AtsJob(
                external_id=external_id,
                title=title,
                location=clean_text(location.get("name"), "Location not specified"),
                url=url,
                posted_at=parse_datetime(item.get("updated_at")),
            )
        )
    return jobs


def fetch_greenhouse_jobs(slug: str, client: httpx.Client | None = None) -> list[AtsJob]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{quote(slug, safe='')}/jobs"
    payload: Any = fetch_json(url, client)
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise AtsFetchError("Greenhouse returned an unexpected response")
    return parse_greenhouse_jobs(payload)
