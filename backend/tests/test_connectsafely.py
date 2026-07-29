import httpx

from app.core.config import Settings
from app.models import Company, Job
from app.services.connectsafely import (
    discover_contacts,
    get_account_status,
    send_linkedin_message,
)


def response(payload: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json=payload,
        request=httpx.Request("GET", "https://api.connectsafely.ai/test"),
    )


def test_account_status_parses_connected_account(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.connectsafely.httpx.request",
        lambda *_args, **_kwargs: response(
            {
                "data": {
                    "id": "acc-1",
                    "firstName": "Rahul",
                    "lastName": "Ranjan",
                    "status": "AVAILABLE",
                    "enabled": True,
                    "hasTokens": True,
                }
            }
        ),
    )
    account = get_account_status(Settings(connectsafely_api_key="test-key"))
    assert account.connected is True
    assert account.name == "Rahul Ranjan"
    assert account.account_id == "acc-1"


def test_account_status_rejects_expired_linkedin_tokens(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.connectsafely.httpx.request",
        lambda *_args, **_kwargs: response(
            {
                "id": "acc-1",
                "status": "AVAILABLE",
                "enabled": True,
                "hasTokens": False,
            }
        ),
    )
    account = get_account_status(Settings(connectsafely_api_key="test-key"))
    assert account.connected is False


def test_people_search_maps_linkedin_results(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.connectsafely.httpx.request",
        lambda *_args, **_kwargs: response(
            {
                "data": {
                    "elements": [
                        {
                            "firstName": "Asha",
                            "lastName": "Rao",
                            "publicIdentifier": "asha-rao",
                            "headline": "Talent Partner at Acme",
                            "mutualConnectionsCount": 2,
                        }
                    ]
                }
            }
        ),
    )
    contacts = discover_contacts(
        Settings(connectsafely_api_key="test-key"),
        Company(name="Acme"),
        Job(title="Product Manager", location="Bangalore", url="https://example.com/job"),
        5,
    )
    assert len(contacts) == 1
    assert contacts[0].name == "Asha Rao"
    assert contacts[0].linkedin_url == "https://www.linkedin.com/in/asha-rao"
    assert contacts[0].mutuals == 2


def test_send_uses_current_conversations_endpoint(monkeypatch) -> None:
    captured: dict = {}

    def fake_request(method: str, url: str, **kwargs) -> httpx.Response:
        captured.update(method=method, url=url, json=kwargs["json"])
        return response(
            {
                "data": {
                    "messageId": "message-1",
                    "conversationUrn": "urn:li:conversation:1",
                }
            }
        )

    monkeypatch.setattr("app.services.connectsafely.httpx.request", fake_request)
    message_id, conversation_id = send_linkedin_message(
        Settings(connectsafely_api_key="test-key"),
        "https://www.linkedin.com/in/asha-rao",
        "Hello Asha",
        "Product role",
    )
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/linkedin/conversations/send")
    assert captured["json"]["recipientProfileId"] == "asha-rao"
    assert message_id == "message-1"
    assert conversation_id == "urn:li:conversation:1"
