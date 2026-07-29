import httpx
import pytest

from app.core.config import Settings
from app.models import Company, Job
from app.services.connectsafely import (
    ConnectSafelyUnavailable,
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
    captured: dict = {}

    def fake_request(*_args, **kwargs) -> httpx.Response:
        captured["body"] = kwargs["json"]
        return response(
            {
                "success": True,
                "people": [
                    {
                        "firstName": "Asha",
                        "lastName": "Rao",
                        "publicIdentifier": "asha-rao",
                        "headline": "Talent Partner at Acme",
                        "mutualConnectionsCount": 2,
                    }
                ],
            }
        )

    monkeypatch.setattr(
        "app.services.connectsafely.httpx.request",
        fake_request,
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
    assert "Recruiter" in captured["body"]["keywords"]
    assert captured["body"]["filters"]["company"] == "Acme"
    assert "title" not in captured["body"]["filters"]
    assert "locationId" not in captured["body"]["filters"]


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


def test_connect_error_explains_corporate_tls_fix(monkeypatch) -> None:
    request = httpx.Request("GET", "https://api.connectsafely.ai/linkedin/account/status")

    def fail_request(*_args, **_kwargs) -> httpx.Response:
        raise httpx.ConnectError(
            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed",
            request=request,
        )

    monkeypatch.setattr("app.services.connectsafely.httpx.request", fail_request)

    with pytest.raises(ConnectSafelyUnavailable) as exc_info:
        get_account_status(Settings(connectsafely_api_key="test-key"))

    assert "OUTBOUND_CA_BUNDLE" in str(exc_info.value)
    assert "disable TLS" not in str(exc_info.value)


def test_invalid_outbound_ca_bundle_is_explained() -> None:
    with pytest.raises(ConnectSafelyUnavailable) as exc_info:
        get_account_status(
            Settings(
                connectsafely_api_key="test-key",
                outbound_ca_bundle="/missing/company-root-ca.pem",
            )
        )

    assert "could not be loaded" in str(exc_info.value)


def test_account_status_retries_one_read_timeout(monkeypatch) -> None:
    request = httpx.Request("GET", "https://api.connectsafely.ai/linkedin/account/status")
    calls = 0

    def flaky_request(*_args, **_kwargs) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadTimeout("provider slow", request=request)
        return response(
            {
                "id": "acc-1",
                "status": "AVAILABLE",
                "enabled": True,
                "hasTokens": True,
            }
        )

    monkeypatch.setattr("app.services.connectsafely.httpx.request", flaky_request)

    account = get_account_status(Settings(connectsafely_api_key="test-key"))

    assert calls == 2
    assert account.connected is True


def test_send_does_not_retry_read_timeout(monkeypatch) -> None:
    request = httpx.Request(
        "POST",
        "https://api.connectsafely.ai/linkedin/conversations/send",
    )
    calls = 0

    def timeout_request(*_args, **_kwargs) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("provider slow", request=request)

    monkeypatch.setattr("app.services.connectsafely.httpx.request", timeout_request)

    with pytest.raises(ConnectSafelyUnavailable):
        send_linkedin_message(
            Settings(connectsafely_api_key="test-key"),
            "https://www.linkedin.com/in/asha-rao",
            "Hello Asha",
        )

    assert calls == 1
