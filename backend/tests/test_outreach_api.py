from app.core.config import Settings
from app.schemas import CompanySuggestion, SuggestionBatch
from app.services.connectsafely import (
    ConnectSafelyAccount,
    ConnectSafelyDeliveryUnconfirmed,
    ConnectSafelyUnavailable,
    DiscoveredContact,
)
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


def test_unconfirmed_send_is_locked_then_verified_without_resending(
    monkeypatch,
) -> None:
    company = client.post(
        "/api/companies",
        json={"name": "Delivery Verification Company", "priority": "HIGH"},
    ).json()
    person = client.post(
        "/api/recruiters",
        json={
            "company_id": company["id"],
            "name": "Delivery Check Recruiter",
            "linkedin_url": "https://www.linkedin.com/in/delivery-check-recruiter",
            "designation": "Talent Partner",
        },
    ).json()
    client.post(f"/api/recruiters/{person['id']}/shortlist", json={})
    client.put(
        "/api/outreach/profile",
        json={
            "name": "Rahul Ranjan",
            "resume_text": (
                "Rahul has led AI product and procurement transformation work at Ola Electric "
                "with measurable cost reduction and Founder's Office exposure. His prior work "
                "spans product and strategy roles across major consumer internet companies."
            ),
            "positioning": "AI Product and Strategy",
        },
    )
    monkeypatch.setattr(
        "app.api.outreach.generate_outreach_message",
        lambda *_args: GeneratedOutreach(
            subject="AI product conversation",
            body=(
                "Hi, I am exploring AI product opportunities and would value a brief "
                "conversation about the team and where my Ola Electric experience may fit."
            ),
            rationale="Company-specific outreach without inventing a live role.",
        ),
    )
    draft = client.post(
        "/api/outreach/messages",
        json={"recruiter_id": person["id"]},
    ).json()
    settings = Settings(
        connectsafely_api_key="test-connectsafely-key",
        connectsafely_account_id="account-test",
    )
    monkeypatch.setattr("app.api.outreach.get_settings", lambda: settings)
    client.post(f"/api/outreach/messages/{draft['id']}/approve")
    monkeypatch.setattr(
        "app.api.outreach.send_linkedin_message",
        lambda *_args: (_ for _ in ()).throw(
            ConnectSafelyDeliveryUnconfirmed("urn:li:conversation:pending")
        ),
    )

    pending_response = client.post(f"/api/outreach/messages/{draft['id']}/send")

    assert pending_response.status_code == 200
    pending = pending_response.json()
    assert pending["status"] == "SENDING"
    assert pending["provider_thread_id"] == "urn:li:conversation:pending"
    assert "locked against resending" in pending["delivery_error"]

    monkeypatch.setattr(
        "app.api.outreach.verify_linkedin_message",
        lambda *_args, **_kwargs: (
            True,
            "urn:li:message:confirmed",
            "urn:li:conversation:pending",
        ),
    )
    verified_response = client.post(f"/api/outreach/messages/{draft['id']}/verify")

    assert verified_response.status_code == 200
    verified = verified_response.json()
    assert verified["status"] == "SENT"
    assert verified["provider_message_id"] == "urn:li:message:confirmed"
    assert verified["delivery_error"] is None


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


def test_configured_linkedin_account_does_not_call_provider_during_dashboard_load(
    monkeypatch,
) -> None:
    settings = Settings(
        connectsafely_api_key="test-connectsafely-key",
        connectsafely_account_id="account-test",
        gemini_api_key="test-gemini-key",
    )
    monkeypatch.setattr("app.api.integrations.get_settings", lambda: settings)

    def unexpected_status_call(*_args) -> ConnectSafelyAccount:
        raise AssertionError("Dashboard loading must not call ConnectSafely account status")

    monkeypatch.setattr(
        "app.api.integrations.get_account_status",
        unexpected_status_call,
    )

    response = client.get("/api/integrations/status")

    assert response.status_code == 200
    result = response.json()
    assert result["connectsafely_account_connected"] is True
    assert result["connectsafely_error"] is None
    assert result["ready_for_contact_discovery"] is True
    assert result["ready_for_linkedin_sending"] is True


def test_contact_discovery_reuses_saved_people_during_provider_outage(
    monkeypatch,
) -> None:
    company = client.post(
        "/api/companies",
        json={"name": "Saved People Company", "priority": "HIGH"},
    ).json()
    saved_person = client.post(
        "/api/recruiters",
        json={
            "company_id": company["id"],
            "name": "Saved Recruiter",
            "linkedin_url": "https://www.linkedin.com/in/saved-recruiter-test",
            "designation": "Talent Partner",
        },
    ).json()
    monkeypatch.setattr(
        "app.api.recruiters.discover_contacts",
        lambda *_args: (_ for _ in ()).throw(
            ConnectSafelyUnavailable("Provider timed out")
        ),
    )

    response = client.post(
        "/api/recruiters/discover",
        json={"company_id": company["id"], "limit": 5},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["used_saved_people"] is True
    assert result["people"][0]["id"] == saved_person["id"]
    assert "Showing 1 people already saved" in result["warning"]


def test_contact_discovery_reuses_saved_people_when_provider_returns_zero(
    monkeypatch,
) -> None:
    company = client.post(
        "/api/companies",
        json={"name": "Empty Search Company", "priority": "HIGH"},
    ).json()
    saved_person = client.post(
        "/api/recruiters",
        json={
            "company_id": company["id"],
            "name": "Existing Talent Partner",
            "linkedin_url": "https://www.linkedin.com/in/existing-talent-partner-test",
            "designation": "Talent Partner",
        },
    ).json()
    monkeypatch.setattr(
        "app.api.recruiters.discover_contacts",
        lambda *_args: [],
    )

    response = client.post(
        "/api/recruiters/discover",
        json={"company_id": company["id"], "limit": 5},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["used_saved_people"] is True
    assert result["people"][0]["id"] == saved_person["id"]
    assert "No new LinkedIn matches returned" in result["warning"]


def test_generates_company_outreach_without_job_choice(monkeypatch) -> None:
    company = client.post(
        "/api/companies",
        json={"name": "Jobless Outreach Company", "priority": "HIGH"},
    ).json()
    person = client.post(
        "/api/recruiters",
        json={
            "company_id": company["id"],
            "name": "Company Recruiter",
            "linkedin_url": "https://www.linkedin.com/in/company-recruiter-test",
            "designation": "Recruiter",
        },
    ).json()
    shortlist_response = client.post(
        f"/api/recruiters/{person['id']}/shortlist",
        json={},
    )
    assert shortlist_response.status_code == 200
    profile_response = client.put(
        "/api/outreach/profile",
        json={
            "name": "Rahul Ranjan",
            "resume_text": (
                "Rahul has led AI product and procurement transformation work at Ola Electric "
                "with measurable cost reduction and Founder's Office exposure. His earlier "
                "experience includes product and strategy work across consumer internet firms."
            ),
            "positioning": "AI Product, Strategy and Founder's Office roles",
        },
    )
    assert profile_response.status_code == 200
    monkeypatch.setattr(
        "app.api.outreach.generate_outreach_message",
        lambda *_args: GeneratedOutreach(
            subject="Product and AI opportunities",
            body=(
                "Hi, I am exploring product and AI opportunities at Jobless Outreach Company. "
                "My recent work includes AI agents and procurement transformation at Ola "
                "Electric. I would value a brief conversation or your direction to the right "
                "person on the team."
            ),
            rationale="Uses company and candidate evidence without inventing a live role.",
        ),
    )

    response = client.post(
        "/api/outreach/messages",
        json={"recruiter_id": person["id"]},
    )

    assert response.status_code == 201
    result = response.json()
    assert result["job_id"] is None
    assert result["job"] is None
    assert result["recruiter"]["id"] == person["id"]


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
