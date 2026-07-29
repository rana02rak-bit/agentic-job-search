from app.core.config import Settings
from app.schemas import CompanySuggestion, SuggestionBatch
from app.services.connectsafely import ConnectSafelyAccount, DiscoveredContact
from app.services.message_generator import GeneratedOutreach
from tests.test_api import client


def test_recruiter_shortlist_and_outreach_lifecycle(monkeypatch) -> None:
    company = client.post(
        "/api/companies",
        json={"name": "Outreach Test Company", "priority": "HIGH"},
    ).json()
    job = client.post(
        "/api/jobs",
        json={
            "company_id": company["id"],
            "title": "Senior Product Manager, AI",
            "location": "Bangalore",
            "url": "https://example.com/jobs/outreach-test-pm",
            "source": "TEST",
        },
    ).json()
    recruiter_response = client.post(
        "/api/recruiters",
        json={
            "company_id": company["id"],
            "name": "Priya Sharma",
            "linkedin_url": "https://www.linkedin.com/in/priya-outreach-test",
            "designation": "Talent Partner",
            "activity": "Posted about hiring product managers this week",
            "mutuals": 2,
        },
    )
    assert recruiter_response.status_code == 201
    recruiter = recruiter_response.json()
    assert recruiter["reply_probability"] >= 70
    assert recruiter["is_shortlisted"] is False

    shortlist_response = client.post(
        f"/api/recruiters/{recruiter['id']}/shortlist",
        json={"job_id": job["id"]},
    )
    assert shortlist_response.status_code == 200
    assert shortlist_response.json()["is_shortlisted"] is True
    assert shortlist_response.json()["shortlisted_job_id"] == job["id"]

    resume = (
        "Rahul led AI agent products at Ola Electric and transformed procurement-to-payment "
        "operations. He delivered measurable cost reduction, worked with Founder's Office teams, "
        "and previously built product and strategy experience across Nykaa, OYO, Paytm and Sleek."
    )
    profile_response = client.put(
        "/api/outreach/profile",
        json={
            "name": "Rahul Ranjan",
            "resume_text": resume,
            "positioning": "AI Product and Founder's Office roles",
        },
    )
    assert profile_response.status_code == 200

    monkeypatch.setattr(
        "app.api.outreach.generate_outreach_message",
        lambda *_args: GeneratedOutreach(
            subject="Senior PM, AI at Outreach Test Company",
            body=(
                "Hi Priya, I noticed your team is hiring a Senior Product Manager for AI. "
                "At Ola Electric, I have led AI-agent and procurement transformation work with "
                "measurable cost impact. I would value a brief conversation about what the team "
                "needs most from this role and whether my background could be relevant."
            ),
            rationale="Uses the specific job, recruiter role, and Rahul's relevant evidence.",
        ),
    )
    message_response = client.post(
        "/api/outreach/messages",
        json={"recruiter_id": recruiter["id"], "job_id": job["id"]},
    )
    assert message_response.status_code == 201
    message = message_response.json()
    assert message["status"] == "DRAFT"
    assert message["subject"] == "Senior PM, AI at Outreach Test Company"
    assert message["recruiter"]["name"] == "Priya Sharma"

    settings = Settings(connectsafely_api_key="test-connectsafely-key")
    monkeypatch.setattr("app.api.outreach.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.api.outreach.get_account_status",
        lambda *_args: ConnectSafelyAccount(
            connected=True,
            name="Rahul",
            account_id="account-test",
        ),
    )
    monkeypatch.setattr(
        "app.api.outreach.send_linkedin_message",
        lambda *_args: ("message-123", "conversation-123"),
    )

    approve_response = client.post(f"/api/outreach/messages/{message['id']}/approve")
    assert approve_response.status_code == 200
    assert approve_response.json()["message"]["status"] == "APPROVED"
    assert approve_response.json()["automatic_send_available"] is True

    sent_response = client.post(f"/api/outreach/messages/{message['id']}/send")
    assert sent_response.status_code == 200
    assert sent_response.json()["status"] == "SENT"
    assert sent_response.json()["provider_message_id"] == "message-123"

    replied_response = client.post(f"/api/outreach/messages/{message['id']}/mark-replied")
    assert replied_response.status_code == 200
    assert replied_response.json()["status"] == "REPLIED"

    stats = client.get("/api/dashboard/stats").json()
    assert stats["messages_sent"] >= 1
    assert stats["replies"] >= 1


def test_recruiter_requires_linkedin_profile_url() -> None:
    companies = client.get("/api/companies").json()
    response = client.post(
        "/api/recruiters",
        json={
            "company_id": companies[0]["id"],
            "name": "Invalid Profile",
            "linkedin_url": "https://example.com/person",
        },
    )
    assert response.status_code == 422


def test_connectsafely_discovers_and_shortlists_people(monkeypatch) -> None:
    company = client.post(
        "/api/companies",
        json={"name": "People Discovery Company", "priority": "HIGH"},
    ).json()
    job = client.post(
        "/api/jobs",
        json={
            "company_id": company["id"],
            "title": "Product Manager",
            "location": "Bangalore",
            "url": "https://example.com/jobs/people-discovery-pm",
            "source": "TEST",
        },
    ).json()
    monkeypatch.setattr(
        "app.api.recruiters.discover_contacts",
        lambda *_args: [
            DiscoveredContact(
                external_id="urn:li:profile:test-person",
                name="Asha Rao",
                linkedin_url="https://www.linkedin.com/in/asha-discovery-test",
                designation="Talent Partner",
                activity="Discovered in test",
                mutuals=1,
            )
        ],
    )
    response = client.post(
        "/api/recruiters/discover",
        json={"company_id": company["id"], "job_id": job["id"], "limit": 5},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["stored"] == 1
    assert result["people"][0]["source"] == "CONNECTSAFELY"
    assert result["people"][0]["is_shortlisted"] is True


def test_ai_discovery_can_auto_pick_high_scoring_firms(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.discovery.generate_company_suggestions",
        lambda *_args: SuggestionBatch(
            suggestions=[
                CompanySuggestion(
                    name="Auto Pick AI Company",
                    website="https://autopick.example",
                    industry="AI Consumer",
                    location="Bangalore",
                    funding_score=9,
                    hiring_score=8,
                    ai_score=10,
                    location_score=10,
                    role_match_score=9,
                    reason=(
                        "Strong AI, location and role fit; funding and hiring need verification."
                    ),
                )
            ]
        ),
    )

    response = client.post(
        "/api/discovery/suggest",
        json={"count": 1, "auto_shortlist": True, "minimum_score": 35},
    )
    assert response.status_code == 200
    selected = response.json()[0]
    assert selected["is_watchlisted"] is True
    assert selected["priority"] == "HIGH"
    assert selected["total_score"] == 46
