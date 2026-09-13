import pytest

from covercollector.extract import (
    CoverImageNotFoundError,
    MultipleCoverImagesError,
    extract_cover_image_url,
)


PAGE_URL = "https://www.comics.org/issue/1246059/cover/4/"
IMAGE_URL = (
    "https://files1.comics.org//img/gcd/covers_by_id/969/w400/969463.jpg"
    "?-320387762954245711"
)


def test_extracts_the_example_cover_without_selecting_other_images() -> None:
    html = f"""
        <header><img src="/static/img/gcd_logo.png" alt="GCD"></header>
        <main>
          <img src="{IMAGE_URL}" alt="Cover" class="cover_img w-[400px]">
        </main>
    """

    assert extract_cover_image_url(html, PAGE_URL) == IMAGE_URL


def test_resolves_protocol_relative_cover_url_and_decodes_entities() -> None:
    html = """
        <img class="cover_img w-[400px]"
             src="//files1.comics.org/img/gcd/covers_by_id/1/w400/1234.jpg?a=1&amp;b=2">
    """

    assert extract_cover_image_url(html, PAGE_URL) == (
        "https://files1.comics.org/img/gcd/covers_by_id/1/w400/1234.jpg?a=1&b=2"
    )


def test_resolves_relative_cover_url() -> None:
    html = '<img class="cover_img" src="/img/gcd/covers_by_id/1/w400/1234.jpg">'

    assert extract_cover_image_url(html, PAGE_URL) == (
        "https://www.comics.org/img/gcd/covers_by_id/1/w400/1234.jpg"
    )


def test_ignores_placeholder_with_cover_class() -> None:
    html = '<img class="border-2 cover_img" src="/static/img/nocover_large.png">'

    with pytest.raises(CoverImageNotFoundError, match="no GCD cover image found"):
        extract_cover_image_url(html, PAGE_URL)


def test_repeated_same_cover_is_not_ambiguous() -> None:
    html = f'<img class="cover_img" src="{IMAGE_URL}">' * 2

    assert extract_cover_image_url(html, PAGE_URL) == IMAGE_URL


def test_rejects_multiple_distinct_covers() -> None:
    first = "https://files1.comics.org/img/gcd/covers_by_id/1/w400/1001.jpg"
    second = "https://files1.comics.org/img/gcd/covers_by_id/1/w400/1002.jpg"
    html = (
        f'<img class="cover_img" src="{first}">'
        f'<img class="cover_img" src="{second}">'
    )

    with pytest.raises(MultipleCoverImagesError) as raised:
        extract_cover_image_url(html, PAGE_URL)

    assert raised.value.urls == (first, second)
