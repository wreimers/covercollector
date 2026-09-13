"""Command-line interface for covercollector."""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Sequence
from pathlib import Path

from covercollector import api, collect, download


def _issue_id(value: str) -> int:
    try:
        return api.issue_id_from_reference(value)
    except api.InvalidIssueReferenceError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _positive_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return number


def _positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def build_parser() -> argparse.ArgumentParser:
    """Build and return the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="covercollector",
        description="Download the primary cover for a Grand Comics Database issue.",
    )
    parser.add_argument(
        "source",
        type=_issue_id,
        help="a numeric GCD issue ID or an HTTPS comics.org issue URL",
    )
    parser.add_argument("destination", type=Path, help="destination image pathname")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace the destination if it already exists",
    )
    parser.add_argument(
        "--timeout",
        type=_positive_float,
        default=30.0,
        metavar="SECONDS",
        help="timeout for each network request (default: 30)",
    )
    parser.add_argument(
        "--max-bytes",
        type=_positive_int,
        default=download.DEFAULT_MAX_BYTES,
        metavar="BYTES",
        help=f"maximum accepted image size (default: {download.DEFAULT_MAX_BYTES})",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command and return its process exit status."""
    args = build_parser().parse_args(argv)
    try:
        destination = collect.collect_cover(
            args.source,
            args.destination,
            overwrite=args.overwrite,
            timeout=args.timeout,
            max_bytes=args.max_bytes,
        )
    except (
        api.InvalidIssueReferenceError,
        api.GcdApiError,
        download.InvalidImageUrlError,
        download.ImageDownloadError,
        OSError,
    ) as error:
        print(f"covercollector: error: {error}", file=sys.stderr)
        return 1

    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
