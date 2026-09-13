"""Extract a cover image URL from a Grand Comics Database cover page."""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


class CoverImageExtractionError(ValueError):
    """Base error raised when a cover image URL cannot be extracted."""


class CoverImageNotFoundError(CoverImageExtractionError):
    """Raised when the page does not contain a GCD cover image."""


class MultipleCoverImagesError(CoverImageExtractionError):
    """Raised when the page contains more than one distinct cover image."""

    def __init__(self, urls: tuple[str, ...]) -> None:
        self.urls = urls
        super().__init__(f"found {len(urls)} distinct cover images")


class _CoverImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sources: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag != "img":
            return

        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        source = attributes.get("src")
        if "cover_img" in classes and source and _is_gcd_cover_path(source):
            self.sources.append(source)

    handle_startendtag = handle_starttag


def _is_gcd_cover_path(source: str) -> bool:
    return "/img/gcd/covers_by_id/" in urlsplit(source).path


def extract_cover_image_url(html: str, page_url: str) -> str:
    """Return the sole GCD cover image URL found in *html*.

    Relative and protocol-relative image sources are resolved against
    ``page_url``. Repeated instances of the same source count as one image.
    """
    parser = _CoverImageParser()
    parser.feed(html)
    parser.close()

    urls = tuple(dict.fromkeys(urljoin(page_url, source) for source in parser.sources))
    if not urls:
        raise CoverImageNotFoundError("no GCD cover image found")
    if len(urls) > 1:
        raise MultipleCoverImagesError(urls)
    return urls[0]
