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


def parse_ashby_jobs(payload: object) -> list[AtsJob]:
    root = as_mapping(payload)
    raw_jobs = root.get("jobs")
    if not isinstance(raw_jobs, list):
        return []

    jobs: list[AtsJob] = []
    for raw in raw_jobs:
        item = as_mapping(raw)
        if item.get("isListed") is False:
            continue
        url = clean_text(item.get("jobUrl")) or clean_text(item.get("applyUrl"))
        title = clean_text(item.get("title"))
        external_id = clean_text(item.get("id")) or url
        if not external_id or not title or not url:
            continue
        jobs.append(
            AtsJob(
                external_id=external_id,
                title=title,
                location=clean_text(item.get("location"), "Location not specified"),
                url=url,
                posted_at=parse_datetime(item.get("publishedAt")),
            )
        )
    return jobs


def fetch_ashby_jobs(slug: str, client: httpx.Client | None = None) -> list[AtsJob]:
    url = (
        "https://api.ashbyhq.com/posting-api/job-board/"
        f"{quote(slug, safe='')}?includeCompensation=false"
    )
    payload: Any = fetch_json(url, client)
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise AtsFetchError("Ashby returned an unexpected response")
    return parse_ashby_jobs(payload)
