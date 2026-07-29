from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app

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
    assert len(list_response.json()) == 1

