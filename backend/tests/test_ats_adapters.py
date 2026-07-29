import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.discovery_worker import seconds_until_next_run
from app.services.ats.ashby import parse_ashby_jobs
from app.services.ats.greenhouse import parse_greenhouse_jobs
from app.services.ats.lever import parse_lever_jobs
from app.services.job_matching import is_target_job

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


def test_greenhouse_parser_normalizes_jobs() -> None:
    jobs = parse_greenhouse_jobs(load_fixture("greenhouse_jobs.json"))

    assert len(jobs) == 2
    assert jobs[0].external_id == "101"
    assert jobs[0].location == "Bengaluru, India"
    assert jobs[0].posted_at is not None


def test_lever_parser_normalizes_jobs() -> None:
    jobs = parse_lever_jobs(load_fixture("lever_jobs.json"))

    assert len(jobs) == 2
    assert jobs[0].external_id == "lever-201"
    assert jobs[0].title == "Chief of Staff"
    assert jobs[0].posted_at is not None


def test_ashby_parser_skips_unlisted_jobs_and_uses_url_as_id() -> None:
    jobs = parse_ashby_jobs(load_fixture("ashby_jobs.json"))

    assert len(jobs) == 2
    assert jobs[0].external_id == jobs[0].url
    assert jobs[0].title == "Product Manager, Growth"


def test_target_job_filter_matches_rahuls_roles_and_locations() -> None:
    assert is_target_job("Senior Product Manager, AI", "Bengaluru, India")
    assert is_target_job("Chief of Staff", "Mumbai")
    assert is_target_job("Strategy Lead", "Remote - India")
    assert not is_target_job("Product Designer", "Bangalore")
    assert not is_target_job("Product Manager", "New York")


def test_daily_worker_schedules_next_eight_am_ist() -> None:
    now = datetime(2026, 7, 29, 9, 30, tzinfo=ZoneInfo("Asia/Kolkata"))

    assert seconds_until_next_run(now, 8) == 22.5 * 60 * 60
