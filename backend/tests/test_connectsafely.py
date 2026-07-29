import httpx
import pytest

from app.core.config import Settings
from app.models import Company, Job
from app.services import connectsafely
from app.services.connectsafely import (
    ConnectSafelyUnavailable,
    discover_contacts,
    get_account_status,
    send_linkedin_message,
)


@pytest.fixture(autouse=True)
def clear_connectsafely_caches() -> None:
    connectsafely._ACCOUNT_STATUS_CACHE.clear()
    connectsafely._ACCOUNT_STATUS_ERROR_CACHE.clear()
    connectsafely._LINKEDIN_COMPANY_ID_CACHE.clear()


def response(payload: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json=payload,
        request=httpx.Request("GET", "https://api.connectsafely.ai/test"),
    )


def test_response_reader_returns_complete_json_without_waiting_for_socket_close() -> None:
    class ResponseThatKeepsConnectionOpen:
        calls = 0

        def read(self, _size: int) -> bytes:
            raise AssertionError("read1 should be preferred")

        def read1(self, _size: int) -> bytes:
            self.calls += 1
            if self.calls == 1:
                return b'{"success": true, "people": []}'
            raise TimeoutError("server kept the connection open")

    provider_response = ResponseThatKeepsConnectionOpen()

    content = connectsafely._read_json_response(provider_response)

    assert content == b'{"success": true, "people": []}'
    assert provider_response.calls == 1


def test_account_status_parses_connected_account(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.connectsafely._transport_request",
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
        "app.services.connectsafely._transport_request",
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
    captured: dict = {"urls": []}

    def fake_request(_method: str, url: str, **kwargs) -> httpx.Response:
        captured["urls"].append(url)
        captured["body"] = kwargs["json"]
        if url.endswith("/linkedin/search/companies"):
            return response(
                {
                    "success": True,
                    "companies": [{"companyId": "12345", "name": "Acme"}],
                }
            )
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
        "app.services.connectsafely._transport_request",
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
    assert captured["body"]["filters"]["currentCompanyIds"] == ["12345"]
    assert "title" not in captured["body"]["filters"]
    assert "locationId" not in captured["body"]["filters"]
    assert captured["urls"][0].endswith("/linkedin/search/companies")
    assert captured["urls"][1].endswith("/linkedin/search/people")


def test_people_search_uses_v2_when_v1_is_empty(monkeypatch) -> None:
    captured_urls: list[str] = []

    def fake_request(_method: str, url: str, **_kwargs) -> httpx.Response:
        captured_urls.append(url)
        if url.endswith("/linkedin/search/companies"):
            return response(
                {
                    "success": True,
                    "companies": [{"companyId": "67890", "name": "Fallback Inc"}],
                }
            )
        if url.endswith("/linkedin/search/people/v2"):
            return response(
                {
                    "success": True,
                    "people": [
                        {
                            "firstName": "Ravi",
                            "lastName": "Shah",
                            "profileId": "ravi-shah",
                            "headline": "Head of Product at Fallback Inc",
                        }
                    ],
                }
            )
        return response({"success": True, "people": []})

    monkeypatch.setattr("app.services.connectsafely._transport_request", fake_request)

    contacts = discover_contacts(
        Settings(connectsafely_api_key="test-key"),
        Company(name="Fallback Inc"),
        None,
        5,
    )

    assert len(contacts) == 1
    assert contacts[0].linkedin_url == "https://www.linkedin.com/in/ravi-shah"
    assert captured_urls[-1].endswith("/linkedin/search/people/v2")


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

    monkeypatch.setattr("app.services.connectsafely._transport_request", fake_request)
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
    def fail_request(*_args, **_kwargs) -> httpx.Response:
        raise ConnectionError(
            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"
        )

    monkeypatch.setattr("app.services.connectsafely._transport_request", fail_request)

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


def test_account_status_times_out_quickly_without_retry(monkeypatch) -> None:
    calls = 0

    def timeout_request(*_args, **_kwargs) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise TimeoutError("provider slow")

    monkeypatch.setattr("app.services.connectsafely._transport_request", timeout_request)

    with pytest.raises(ConnectSafelyUnavailable):
        get_account_status(Settings(connectsafely_api_key="test-key"))
    with pytest.raises(ConnectSafelyUnavailable):
        get_account_status(Settings(connectsafely_api_key="test-key"))

    assert calls == 1


def test_account_status_cache_avoids_duplicate_provider_calls(monkeypatch) -> None:
    calls = 0

    def account_request(*_args, **_kwargs) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response(
            {
                "id": "acc-1",
                "status": "AVAILABLE",
                "enabled": True,
                "hasTokens": True,
            }
        )

    monkeypatch.setattr("app.services.connectsafely._transport_request", account_request)
    settings = Settings(connectsafely_api_key="test-key")

    first = get_account_status(settings)
    second = get_account_status(settings)

    assert calls == 1
    assert first == second


def test_send_does_not_retry_read_timeout(monkeypatch) -> None:
    calls = 0

    def timeout_request(*_args, **_kwargs) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise TimeoutError("provider slow")

    monkeypatch.setattr("app.services.connectsafely._transport_request", timeout_request)

    with pytest.raises(ConnectSafelyUnavailable):
        send_linkedin_message(
            Settings(connectsafely_api_key="test-key"),
            "https://www.linkedin.com/in/asha-rao",
            "Hello Asha",
        )

    assert calls == 1
