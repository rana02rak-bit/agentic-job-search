import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.db import SessionLocal, create_tables
from app.services.ats.runner import run_ats_discovery

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def seconds_until_next_run(now: datetime, run_hour: int) -> float:
    next_run = now.replace(hour=run_hour, minute=0, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return (next_run - now).total_seconds()


def run_once() -> None:
    with SessionLocal() as db:
        run = run_ats_discovery(db)
        logger.info(
            "ATS discovery run %s finished: status=%s companies=%s new_jobs=%s",
            run.id,
            run.status,
            run.companies_checked,
            run.jobs_found,
        )


def main() -> None:
    settings = get_settings()
    timezone = ZoneInfo(settings.discovery_timezone)
    create_tables()
    run_once()
    while True:
        now = datetime.now(timezone)
        delay = seconds_until_next_run(now, settings.discovery_run_hour)
        logger.info(
            "Next ATS discovery at %02d:00 %s",
            settings.discovery_run_hour,
            settings.discovery_timezone,
        )
        time.sleep(delay)
        run_once()


if __name__ == "__main__":
    main()
