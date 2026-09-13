from pathlib import Path

import pytest

from covercollector import api, collect, download
from covercollector import __main__ as cli


ISSUE_URL = "https://www.comics.org/issue/1246059/cover/4/"


def test_accepts_raw_issue_id_and_destination(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path,
) -> None:
    destination = tmp_path / "cover.jpg"

    def fake_collect_cover(
        source: str | int,
        output_path: Path,
        *,
        overwrite: bool,
        timeout: float,
        max_bytes: int,
    ) -> Path:
        assert source == 1246059
        assert output_path == destination
        assert overwrite is False
        assert timeout == 30.0
        assert max_bytes == download.DEFAULT_MAX_BYTES
        return destination

    monkeypatch.setattr(collect, "collect_cover", fake_collect_cover)

    assert cli.main(["1246059", str(destination)]) == 0
    assert capsys.readouterr().out == f"{destination}\n"


def test_accepts_url_and_options(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    destination = tmp_path / "cover.jpg"

    def fake_collect_cover(
        source: str | int,
        output_path: Path,
        *,
        overwrite: bool,
        timeout: float,
        max_bytes: int,
    ) -> Path:
        assert source == 1246059
        assert output_path == destination
        assert overwrite is True
        assert timeout == 12.5
        assert max_bytes == 1_000_000
        return destination

    monkeypatch.setattr(collect, "collect_cover", fake_collect_cover)

    assert cli.main(
        [
            ISSUE_URL,
            str(destination),
            "--overwrite",
            "--timeout",
            "12.5",
            "--max-bytes",
            "1000000",
        ]
    ) == 0


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["1246059"],
        ["not-an-issue", "cover.jpg"],
        ["1246059", "cover.jpg", "--timeout", "0"],
        ["1246059", "cover.jpg", "--timeout", "nan"],
        ["1246059", "cover.jpg", "--timeout", "inf"],
        ["1246059", "cover.jpg", "--max-bytes", "-1"],
    ],
)
def test_rejects_invalid_arguments(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(arguments)

    assert raised.value.code == 2


@pytest.mark.parametrize(
    "error",
    [
        api.InvalidIssueReferenceError("bad issue"),
        api.GcdApiError("API unavailable"),
        download.InvalidImageUrlError("bad image URL"),
        download.ImageDownloadError("download failed"),
        FileExistsError("destination exists"),
    ],
)
def test_reports_operational_errors_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
) -> None:
    def fail(*args: object, **kwargs: object) -> Path:
        raise error

    monkeypatch.setattr(collect, "collect_cover", fail)

    assert cli.main(["1246059", "cover.jpg"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"covercollector: error: {error}\n"
