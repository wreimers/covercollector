"""Coordinate GCD cover lookup and download."""

from __future__ import annotations

from pathlib import Path

from covercollector import api, download


def collect_cover(
    issue: str | int,
    destination: str | Path,
    *,
    overwrite: bool = False,
    timeout: float = 30.0,
    max_bytes: int = download.DEFAULT_MAX_BYTES,
) -> Path:
    """Look up an issue's primary cover and download it to *destination*.

    ``issue`` may be a positive numeric issue ID or a supported comics.org
    issue URL. The timeout applies independently to the API and image requests.
    """
    image_url = api.get_cover_image_url(issue, timeout=timeout)
    return download.download_image(
        image_url,
        destination,
        overwrite=overwrite,
        timeout=timeout,
        max_bytes=max_bytes,
    )
