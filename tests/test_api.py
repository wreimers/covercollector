from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from covercollector import api


ISSUE_URL = "https://www.comics.org/issue/1246059/cover/4/"
COVER_URL = "https://files1.comics.org//img/gcd/covers_by_id/969/w400/969463.jpg"


class FakeResponse(BytesIO):
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


@pytest.mark.parametrize(
    "reference",
    [
        1246059,
        "1246059",
        ISSUE_URL,
        "https://comics.org/issue/1246059/",
    ],
)
def test_extracts_issue_id_from_raw_id_or_url(reference: str | int) -> None:
    assert api.issue_id_from_reference(reference) == 1246059


@pytest.mark.parametrize(
    "reference",
    [
        0,
        -1,
        "0",
        "http://www.comics.org/issue/1246059/cover/4/",
        "https://example.com/issue/1246059/cover/4/",
        "https://www.comics.org:443/issue/1246059/cover/4/",
        "https://www.comics.org/series/82156/",
        "https://www.comics.org/issue/0/cover/4/",
        "https://www.comics.org/issue/1246059/cover/3/",
    ],
)
def test_rejects_unsupported_issue_references(reference: str | int) -> None:
    with pytest.raises(api.InvalidIssueReferenceError):
        api.issue_id_from_reference(reference)


def test_requests_issue_api_and_returns_cover(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: object, *, timeout: float) -> FakeResponse:
        assert request.full_url == "https://www.comics.org/api/issue/1246059/"
        assert request.get_header("Accept") == "application/json"
        assert request.get_header("User-agent") == api.USER_AGENT
        assert timeout == 12.5
        return FakeResponse(f'{{"cover": "{COVER_URL}"}}'.encode())

    monkeypatch.setattr(api, "urlopen", fake_urlopen)

    assert api.get_cover_image_url(ISSUE_URL, timeout=12.5) == COVER_URL


def test_requests_issue_api_using_raw_issue_id(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: object, **kwargs: object) -> FakeResponse:
        assert request.full_url == "https://www.comics.org/api/issue/1246059/"
        return FakeResponse(f'{{"cover": "{COVER_URL}"}}'.encode())

    monkeypatch.setattr(api, "urlopen", fake_urlopen)

    assert api.get_cover_image_url("1246059") == COVER_URL


def test_reports_missing_cover(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "urlopen", lambda *args, **kwargs: FakeResponse(b'{"cover": ""}'))

    with pytest.raises(api.CoverUnavailableError, match="1246059 has no available cover"):
        api.get_cover_image_url(ISSUE_URL)


@pytest.mark.parametrize("body", [b"not json", b"[]"])
def test_reports_invalid_api_response(
    monkeypatch: pytest.MonkeyPatch,
    body: bytes,
) -> None:
    monkeypatch.setattr(api, "urlopen", lambda *args, **kwargs: FakeResponse(body))

    with pytest.raises(api.GcdApiError, match="GCD API"):
        api.get_cover_image_url(ISSUE_URL)


def test_reports_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_http_error(*args: object, **kwargs: object) -> None:
        raise HTTPError("api-url", 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(api, "urlopen", raise_http_error)

    with pytest.raises(api.GcdApiError, match="HTTP 429"):
        api.get_cover_image_url(ISSUE_URL)


def test_reports_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_url_error(*args: object, **kwargs: object) -> None:
        raise URLError("network unavailable")

    monkeypatch.setattr(api, "urlopen", raise_url_error)

    with pytest.raises(api.GcdApiError, match="network unavailable"):
        api.get_cover_image_url(ISSUE_URL)


def test_reports_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_timeout(*args: object, **kwargs: object) -> None:
        raise TimeoutError

    monkeypatch.setattr(api, "urlopen", raise_timeout)

    with pytest.raises(api.GcdApiError, match="timed out for issue 1246059"):
        api.get_cover_image_url(ISSUE_URL)
