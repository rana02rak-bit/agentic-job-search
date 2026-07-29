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


def parse_lever_jobs(payload: object) -> list[AtsJob]:
    if not isinstance(payload, list):
        return []

    jobs: list[AtsJob] = []
    for raw in payload:
        item = as_mapping(raw)
        categories = as_mapping(item.get("categories"))
        external_id = clean_text(item.get("id"))
        title = clean_text(item.get("text"))
        url = clean_text(item.get("hostedUrl")) or clean_text(item.get("applyUrl"))
        if not external_id or not title or not url:
            continue
        jobs.append(
            AtsJob(
                external_id=external_id,
                title=title,
                location=clean_text(categories.get("location"), "Location not specified"),
                url=url,
                posted_at=parse_datetime(item.get("createdAt")),
            )
        )
    return jobs


def fetch_lever_jobs(slug: str, client: httpx.Client | None = None) -> list[AtsJob]:
    jobs: list[AtsJob] = []
    encoded_slug = quote(slug, safe="")
    for skip in range(0, 1000, 100):
        url = (
            f"https://api.lever.co/v0/postings/{encoded_slug}"
            f"?mode=json&limit=100&skip={skip}"
        )
        payload: Any = fetch_json(url, client)
        if not isinstance(payload, list):
            raise AtsFetchError("Lever returned an unexpected response")
        page = parse_lever_jobs(payload)
        jobs.extend(page)
        if len(payload) < 100:
            break
    return jobs
