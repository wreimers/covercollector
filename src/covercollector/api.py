"""Access cover information through the Grand Comics Database API."""

from __future__ import annotations

import json
import re
from json import JSONDecodeError
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


API_ROOT = "https://www.comics.org/api/issue"
USER_AGENT = "covercollector/0.1"

_ISSUE_PATH = re.compile(r"^/issue/([1-9][0-9]*)(?:/cover/[124])?/?$")


class InvalidIssueReferenceError(ValueError):
    """Raised when an input is neither an issue ID nor a supported GCD URL."""


class GcdApiError(RuntimeError):
    """Raised when the GCD API cannot provide a usable response."""


class CoverUnavailableError(GcdApiError):
    """Raised when the issue has no cover URL in the GCD API."""


def issue_id_from_reference(issue: str | int) -> int:
    """Return an issue ID from a positive integer or supported GCD URL."""
    if isinstance(issue, int) and not isinstance(issue, bool):
        if issue > 0:
            return issue
        raise InvalidIssueReferenceError("expected a positive GCD issue ID")
    if not isinstance(issue, str):
        raise InvalidIssueReferenceError("expected a GCD issue ID or URL")
    if issue.isdecimal():
        issue_id = int(issue)
        if issue_id > 0:
            return issue_id
        raise InvalidIssueReferenceError("expected a positive GCD issue ID")

    parts = urlsplit(issue)
    if parts.scheme != "https" or parts.netloc.lower() not in {
        "comics.org",
        "www.comics.org",
    }:
        raise InvalidIssueReferenceError(
            "expected a GCD issue ID or HTTPS comics.org issue URL"
        )

    match = _ISSUE_PATH.fullmatch(parts.path)
    if match is None:
        raise InvalidIssueReferenceError(
            "expected a GCD issue ID or comics.org issue URL"
        )
    return int(match.group(1))


def get_cover_image_url(issue: str | int, *, timeout: float = 30.0) -> str:
    """Return the primary cover URL reported by the GCD issue API."""
    issue_id = issue_id_from_reference(issue)
    api_url = f"{API_ROOT}/{issue_id}/"
    request = Request(
        api_url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
    except HTTPError as error:
        raise GcdApiError(
            f"GCD API returned HTTP {error.code} for issue {issue_id}"
        ) from error
    except URLError as error:
        raise GcdApiError(f"could not reach the GCD API: {error.reason}") from error
    except TimeoutError as error:
        raise GcdApiError(f"GCD API request timed out for issue {issue_id}") from error

    try:
        data = json.loads(body)
    except (JSONDecodeError, UnicodeDecodeError) as error:
        raise GcdApiError("GCD API returned invalid JSON") from error

    if not isinstance(data, dict):
        raise GcdApiError("GCD API response was not a JSON object")

    cover_url = data.get("cover")
    if not isinstance(cover_url, str) or not cover_url.strip():
        raise CoverUnavailableError(f"GCD issue {issue_id} has no available cover")
    return cover_url
