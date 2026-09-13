from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from covercollector import download


IMAGE_URL = "https://files1.comics.org//img/gcd/covers_by_id/969/w400/969463.jpg"
IMAGE_BYTES = b"\xff\xd8\xffexample jpeg bytes\xff\xd9"


class FakeHeaders(dict[str, str]):
    pass


class FakeResponse(BytesIO):
    def __init__(
        self,
        body: bytes,
        *,
        content_type: str = "image/jpeg",
        final_url: str = IMAGE_URL,
        content_length: int | None = None,
    ) -> None:
        super().__init__(body)
        self.headers = FakeHeaders({"Content-Type": content_type})
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)
        self._final_url = final_url

    def geturl(self) -> str:
        return self._final_url

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class TimeoutDuringReadResponse(FakeResponse):
    def __init__(self) -> None:
        super().__init__(IMAGE_BYTES)
        self._read_count = 0

    def read(self, size: int = -1) -> bytes:
        self._read_count += 1
        if self._read_count > 1:
            raise TimeoutError
        return super().read(size)


def test_downloads_image_atomically(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    destination = tmp_path / "cover.jpg"

    def fake_urlopen(request: object, *, timeout: float) -> FakeResponse:
        assert request.full_url == IMAGE_URL
        assert request.get_header("Accept") == "image/*"
        assert request.get_header("User-agent") == download.USER_AGENT
        assert timeout == 12.5
        return FakeResponse(IMAGE_BYTES, content_length=len(IMAGE_BYTES))

    monkeypatch.setattr(download, "urlopen", fake_urlopen)

    result = download.download_image(IMAGE_URL, destination, timeout=12.5)

    assert result == destination
    assert destination.read_bytes() == IMAGE_BYTES
    assert list(tmp_path.glob("*.part")) == []


def test_refuses_to_overwrite_before_requesting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    destination = tmp_path / "cover.jpg"
    destination.write_bytes(b"existing")

    def unexpected_request(*args: object, **kwargs: object) -> None:
        pytest.fail("network request should not be made")

    monkeypatch.setattr(download, "urlopen", unexpected_request)

    with pytest.raises(FileExistsError):
        download.download_image(IMAGE_URL, destination)

    assert destination.read_bytes() == b"existing"


def test_overwrites_when_requested(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    destination = tmp_path / "cover.jpg"
    destination.write_bytes(b"existing")
    monkeypatch.setattr(
        download,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(IMAGE_BYTES),
    )

    download.download_image(IMAGE_URL, destination, overwrite=True)

    assert destination.read_bytes() == IMAGE_BYTES


@pytest.mark.parametrize(
    "image_url",
    [
        "http://files1.comics.org/img/gcd/covers_by_id/969/w400/969463.jpg",
        "https://example.com/img/gcd/covers_by_id/969/w400/969463.jpg",
        "https://comics.org.example.com/img/gcd/covers_by_id/969/w400/969463.jpg",
        "https://user@files1.comics.org/img/gcd/covers_by_id/969/w400/969463.jpg",
        "https://files1.comics.org:443/img/gcd/covers_by_id/969/w400/969463.jpg",
        "https://files1.comics.org/static/logo.jpg",
    ],
)
def test_rejects_non_gcd_cover_urls(image_url: str, tmp_path) -> None:
    with pytest.raises(download.InvalidImageUrlError):
        download.download_image(image_url, tmp_path / "cover.jpg")


def test_rejects_non_image_response(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(
        download,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(b"challenge", content_type="text/html"),
    )

    with pytest.raises(download.InvalidImageResponseError, match="text/html"):
        download.download_image(IMAGE_URL, tmp_path / "cover.jpg")


def test_rejects_redirect_outside_gcd(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(
        download,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(
            IMAGE_BYTES,
            final_url="https://example.com/cover.jpg",
        ),
    )

    with pytest.raises(download.ImageDownloadError, match="redirected outside"):
        download.download_image(IMAGE_URL, tmp_path / "cover.jpg")


def test_rejects_declared_oversized_image(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        download,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(b"", content_length=11),
    )

    with pytest.raises(download.ImageTooLargeError):
        download.download_image(IMAGE_URL, tmp_path / "cover.jpg", max_bytes=10)


def test_removes_partial_file_when_stream_exceeds_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        download,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(b"12345678901"),
    )
    destination = tmp_path / "cover.jpg"

    with pytest.raises(download.ImageTooLargeError):
        download.download_image(IMAGE_URL, destination, max_bytes=10)

    assert not destination.exists()
    assert list(tmp_path.glob("*.part")) == []


def test_rejects_empty_image(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(
        download,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(b""),
    )

    with pytest.raises(download.InvalidImageResponseError, match="empty"):
        download.download_image(IMAGE_URL, tmp_path / "cover.jpg")


def test_removes_partial_file_after_stream_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        download,
        "urlopen",
        lambda *args, **kwargs: TimeoutDuringReadResponse(),
    )
    destination = tmp_path / "cover.jpg"

    with pytest.raises(download.ImageDownloadError, match="download timed out"):
        download.download_image(IMAGE_URL, destination)

    assert not destination.exists()
    assert list(tmp_path.glob("*.part")) == []


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (HTTPError("image-url", 404, "Not Found", {}, None), "HTTP 404"),
        (URLError("network unavailable"), "network unavailable"),
        (TimeoutError(), "timed out"),
    ],
)
def test_reports_request_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    error: Exception,
    message: str,
) -> None:
    def raise_error(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(download, "urlopen", raise_error)

    with pytest.raises(download.ImageDownloadError, match=message):
        download.download_image(IMAGE_URL, tmp_path / "cover.jpg")
