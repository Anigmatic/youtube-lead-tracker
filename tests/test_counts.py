import pytest

from app.counts import parse_count, format_count


@pytest.mark.parametrize("text,expected", [
    ("21.2M subscribers", 21_200_000),
    ("1.5K", 1500),
    ("523", 523),
    ("14M views", 14_000_000),
    ("1,234", 1234),
    ("113", 113),
])
def test_parse_count(text, expected):
    assert parse_count(text) == expected


def test_parse_count_raises_on_unparseable_text():
    with pytest.raises(ValueError):
        parse_count("no digits here")


@pytest.mark.parametrize("n,expected", [
    (523, "523"),
    (5650, "5.65K"),
    (21_200_000, "21.2M"),
    (1_000, "1K"),
    (0, "0"),
])
def test_format_count(n, expected):
    assert format_count(n) == expected
