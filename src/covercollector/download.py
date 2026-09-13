"""Safely download cover images returned by the GCD API."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from covercollector.api import USER_AGENT


DEFAULT_MAX_BYTES = 25 * 1024 * 1024
CHUNK_SIZE = 64 * 1024


class InvalidImageUrlError(ValueError):
    """Raised when a URL is not a supported GCD cover-image URL."""


class ImageDownloadError(RuntimeError):
    """Raised when a cover image cannot be downloaded safely."""


class ImageTooLargeError(ImageDownloadError):
    """Raised when a cover image exceeds the configured size limit."""


class InvalidImageResponseError(ImageDownloadError):
    """Raised when a response does not contain a usable image."""


def _validate_image_url(image_url: str) -> None:
    parts = urlsplit(image_url)
    hostname = parts.hostname or ""
    try:
        port = parts.port
    except ValueError as error:
        raise InvalidImageUrlError("invalid image URL port") from error

    if (
        parts.scheme != "https"
        or not (hostname == "comics.org" or hostname.endswith(".comics.org"))
        or parts.username is not None
        or parts.password is not None
        or port is not None
        or "/img/gcd/covers_by_id/" not in parts.path
    ):
        raise InvalidImageUrlError("expected an HTTPS GCD cover-image URL")


def _content_length(headers: object) -> int | None:
    value = headers.get("Content-Length")
    if value is None:
        return None
    try:
        length = int(value)
    except (TypeError, ValueError) as error:
        raise InvalidImageResponseError("invalid image Content-Length") from error
    if length < 0:
        raise InvalidImageResponseError("invalid image Content-Length")
    return length


def download_image(
    image_url: str,
    destination: str | Path,
    *,
    overwrite: bool = False,
    timeout: float = 30.0,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Path:
    """Stream a GCD cover image to *destination* and return its path."""
    _validate_image_url(image_url)
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")

    destination = Path(destination)
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)

    request = Request(
        image_url,
        headers={
            "Accept": "image/*",
            "User-Agent": USER_AGENT,
        },
    )
    temporary_path: Path | None = None

    try:
        try:
            response_context = urlopen(request, timeout=timeout)
        except HTTPError as error:
            raise ImageDownloadError(
                f"image server returned HTTP {error.code}"
            ) from error
        except URLError as error:
            raise ImageDownloadError(
                f"could not reach the image server: {error.reason}"
            ) from error
        except TimeoutError as error:
            raise ImageDownloadError("image request timed out") from error

        with response_context as response:
            try:
                _validate_image_url(response.geturl())
            except InvalidImageUrlError as error:
                raise ImageDownloadError(
                    "image request redirected outside GCD cover storage"
                ) from error

            content_type = (response.headers.get("Content-Type") or "").partition(";")[0]
            if not content_type.strip().lower().startswith("image/"):
                raise InvalidImageResponseError(
                    f"expected an image response, received {content_type or 'no content type'}"
                )

            declared_length = _content_length(response.headers)
            if declared_length is not None and declared_length > max_bytes:
                raise ImageTooLargeError(
                    f"image exceeds the {max_bytes}-byte size limit"
                )

            descriptor, temporary_name = tempfile.mkstemp(
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".part",
            )
            temporary_path = Path(temporary_name)
            bytes_written = 0
            with os.fdopen(descriptor, "wb") as output:
                while True:
                    try:
                        chunk = response.read(CHUNK_SIZE)
                    except URLError as error:
                        raise ImageDownloadError(
                            f"image download failed: {error.reason}"
                        ) from error
                    except TimeoutError as error:
                        raise ImageDownloadError("image download timed out") from error
                    if not chunk:
                        break
                    bytes_written += len(chunk)
                    if bytes_written > max_bytes:
                        raise ImageTooLargeError(
                            f"image exceeds the {max_bytes}-byte size limit"
                        )
                    output.write(chunk)

        if bytes_written == 0:
            raise InvalidImageResponseError("image response was empty")

        if overwrite:
            os.replace(temporary_path, destination)
        else:
            os.link(temporary_path, destination)
            temporary_path.unlink()
        temporary_path = None
        return destination
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
