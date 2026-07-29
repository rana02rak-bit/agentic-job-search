import httpx

from app.models import AtsProvider
from app.services.ats.ashby import fetch_ashby_jobs
from app.services.ats.base import AtsJob
from app.services.ats.greenhouse import fetch_greenhouse_jobs
from app.services.ats.lever import fetch_lever_jobs


def fetch_jobs(
    provider: AtsProvider,
    slug: str,
    client: httpx.Client | None = None,
) -> list[AtsJob]:
    adapters = {
        AtsProvider.GREENHOUSE: fetch_greenhouse_jobs,
        AtsProvider.LEVER: fetch_lever_jobs,
        AtsProvider.ASHBY: fetch_ashby_jobs,
    }
    return adapters[provider](slug, client)
