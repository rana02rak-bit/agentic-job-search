from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.services.ats.base import AtsJob

engine = create_engine(
    "sqlite+pysqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base.metadata.create_all(bind=engine)


def override_get_db() -> Generator[Session, None, None]:
    with TestingSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_watchlist_lifecycle_and_dashboard_stats() -> None:
    create_response = client.post(
        "/api/companies",
        json={
            "name": "Sarvam AI",
            "website": "https://www.sarvam.ai",
            "location": "Bangalore",
            "priority": "HIGH",
        },
    )
    assert create_response.status_code == 201
    company = create_response.json()
    assert company["name"] == "Sarvam AI"
    assert company["is_watchlisted"] is True
    assert company["total_score"] == 0

    duplicate_response = client.post(
        "/api/companies",
        json={"name": "sarvam ai", "priority": "HIGH"},
    )
    assert duplicate_response.status_code == 409

    patch_response = client.patch(
        f"/api/companies/{company['id']}",
        json={"priority": "MEDIUM"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["priority"] == "MEDIUM"

    stats_response = client.get("/api/dashboard/stats")
    assert stats_response.status_code == 200
    assert stats_response.json()["watchlisted"] == 1

    delete_response = client.delete(f"/api/companies/{company['id']}")
    assert delete_response.status_code == 204

    readd_response = client.post(
        "/api/companies",
        json={"name": "Sarvam AI", "priority": "HIGH"},
    )
    assert readd_response.status_code == 201
    assert readd_response.json()["is_watchlisted"] is True


def test_job_storage_rejects_duplicate_url() -> None:
    company = client.post(
        "/api/companies",
        json={"name": "Test Company", "priority": "LOW"},
    ).json()
    payload = {
        "company_id": company["id"],
        "title": "Senior Product Manager",
        "location": "Bangalore",
        "url": "https://example.com/jobs/pm-1",
        "source": "TEST",
    }

    first_response = client.post("/api/jobs", json=payload)
    assert first_response.status_code == 201
    assert first_response.json()["company"]["name"] == "Test Company"

    duplicate_response = client.post("/api/jobs", json=payload)
    assert duplicate_response.status_code == 409

    list_response = client.get("/api/jobs?today_only=true")
    assert list_response.status_code == 200
    assert any(job["url"] == payload["url"] for job in list_response.json())


def test_ats_source_sync_is_idempotent(monkeypatch) -> None:
    company = client.post(
        "/api/companies",
        json={"name": "ATS Test Company", "priority": "HIGH"},
    ).json()
    source_response = client.put(
        f"/api/companies/{company['id']}/ats-source",
        json={"provider": "GREENHOUSE", "slug": "ats-test-company"},
    )
    assert source_response.status_code == 200
    assert source_response.json()["provider"] == "GREENHOUSE"

    def fake_fetch(*_args) -> list[AtsJob]:
        return [
            AtsJob(
                external_id="external-pm-1",
                title="Senior Product Manager, AI",
                location="Bangalore, India",
                url="https://boards.greenhouse.io/ats-test-company/jobs/1",
            ),
            AtsJob(
                external_id="external-eng-1",
                title="Software Engineer",
                location="Bangalore, India",
                url="https://boards.greenhouse.io/ats-test-company/jobs/2",
            ),
        ]

    monkeypatch.setattr("app.services.ats.runner.fetch_jobs", fake_fetch)

    first_sync = client.post("/api/discovery/sync")
    assert first_sync.status_code == 200
    first_run = first_sync.json()
    assert first_run["status"] == "COMPLETED"
    assert first_run["jobs_found"] == 1
    assert first_run["source_runs"][0]["jobs_seen"] == 2
    assert first_run["source_runs"][0]["jobs_matched"] == 1

    second_sync = client.post("/api/discovery/sync")
    assert second_sync.status_code == 200
    assert second_sync.json()["jobs_found"] == 0

    runs_response = client.get("/api/discovery/runs?limit=2")
    assert runs_response.status_code == 200
    assert len(runs_response.json()) == 2

    disconnect_response = client.delete(f"/api/companies/{company['id']}/ats-source")
    assert disconnect_response.status_code == 204
    disabled_source = client.get(f"/api/companies/{company['id']}/ats-source").json()
    assert disabled_source["enabled"] is False
