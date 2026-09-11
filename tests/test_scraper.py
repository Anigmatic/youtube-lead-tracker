import pytest

from app.scraper import normalize_channel_input, extract_yt_initial_data, ScrapeError


@pytest.mark.parametrize("input_str,expected_about,expected_videos", [
    ("@mkbhd", "https://www.youtube.com/@mkbhd/about", "https://www.youtube.com/@mkbhd/videos"),
    ("mkbhd", "https://www.youtube.com/@mkbhd/about", "https://www.youtube.com/@mkbhd/videos"),
    (
        "https://www.youtube.com/@mkbhd",
        "https://www.youtube.com/@mkbhd/about",
        "https://www.youtube.com/@mkbhd/videos",
    ),
    (
        "https://www.youtube.com/@mkbhd/videos",
        "https://www.youtube.com/@mkbhd/about",
        "https://www.youtube.com/@mkbhd/videos",
    ),
    (
        "https://www.youtube.com/channel/UCBJycsmduvYEL83R_U4JriQ",
        "https://www.youtube.com/channel/UCBJycsmduvYEL83R_U4JriQ/about",
        "https://www.youtube.com/channel/UCBJycsmduvYEL83R_U4JriQ/videos",
    ),
])
def test_normalize_channel_input(input_str, expected_about, expected_videos):
    result = normalize_channel_input(input_str)
    assert result["about_url"] == expected_about
    assert result["videos_url"] == expected_videos


def test_normalize_channel_input_raises_on_empty_string():
    with pytest.raises(ValueError):
        normalize_channel_input("   ")


def test_extract_yt_initial_data_parses_embedded_json():
    html = '<html><body><script>var ytInitialData = {"a": 1, "b": {"c": "d}e"}};</script></body></html>'
    data = extract_yt_initial_data(html)
    assert data == {"a": 1, "b": {"c": "d}e"}}


def test_extract_yt_initial_data_raises_when_marker_missing():
    with pytest.raises(ScrapeError):
        extract_yt_initial_data("<html><body>no data here</body></html>")
