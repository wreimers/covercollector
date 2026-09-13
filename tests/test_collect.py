from pathlib import Path

import pytest

from covercollector import api, collect, download


ISSUE_URL = "https://www.comics.org/issue/1246059/cover/4/"
IMAGE_URL = "https://files1.comics.org//img/gcd/covers_by_id/969/w400/969463.jpg"


def test_collects_cover_from_url(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    destination = tmp_path / "cover.jpg"
    calls: list[tuple[object, ...]] = []

    def fake_get_cover_image_url(issue: str | int, *, timeout: float) -> str:
        calls.append(("lookup", issue, timeout))
        return IMAGE_URL

    def fake_download_image(
        image_url: str,
        output_path: str | Path,
        *,
        overwrite: bool,
        timeout: float,
        max_bytes: int,
    ) -> Path:
        calls.append(
            ("download", image_url, output_path, overwrite, timeout, max_bytes)
        )
        return Path(output_path)

    monkeypatch.setattr(api, "get_cover_image_url", fake_get_cover_image_url)
    monkeypatch.setattr(download, "download_image", fake_download_image)

    result = collect.collect_cover(
        ISSUE_URL,
        destination,
        overwrite=True,
        timeout=12.5,
        max_bytes=1_000_000,
    )

    assert result == destination
    assert calls == [
        ("lookup", ISSUE_URL, 12.5),
        ("download", IMAGE_URL, destination, True, 12.5, 1_000_000),
    ]


def test_collects_cover_from_raw_issue_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    destination = tmp_path / "cover.jpg"

    def fake_get_cover_image_url(issue: str | int, *, timeout: float) -> str:
        assert issue == "1246059"
        return IMAGE_URL

    def fake_download_image(*args: object, **kwargs: object) -> Path:
        return destination

    monkeypatch.setattr(api, "get_cover_image_url", fake_get_cover_image_url)
    monkeypatch.setattr(download, "download_image", fake_download_image)

    assert collect.collect_cover("1246059", destination) == destination


def test_does_not_download_when_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    def fail_lookup(*args: object, **kwargs: object) -> str:
        raise api.CoverUnavailableError("no cover")

    def unexpected_download(*args: object, **kwargs: object) -> Path:
        pytest.fail("download should not run after a lookup failure")

    monkeypatch.setattr(api, "get_cover_image_url", fail_lookup)
    monkeypatch.setattr(download, "download_image", unexpected_download)

    with pytest.raises(api.CoverUnavailableError, match="no cover"):
        collect.collect_cover(1246059, tmp_path / "cover.jpg")


def test_preserves_download_error(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(
        api,
        "get_cover_image_url",
        lambda *args, **kwargs: IMAGE_URL,
    )

    def fail_download(*args: object, **kwargs: object) -> Path:
        raise download.ImageDownloadError("download failed")

    monkeypatch.setattr(download, "download_image", fail_download)

    with pytest.raises(download.ImageDownloadError, match="download failed"):
        collect.collect_cover(1246059, tmp_path / "cover.jpg")
