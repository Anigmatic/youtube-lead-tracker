import pytest
import os

from app.scraper import normalize_channel_input, extract_yt_initial_data, ScrapeError, parse_about_page, extract_contact_info, guess_language


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


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), encoding="utf-8") as f:
        return f.read()


def test_parse_about_page_extracts_core_fields():
    html = _load_fixture("about_page.html")
    data = extract_yt_initial_data(html)
    about = parse_about_page(data)
    assert about["name"] == "Test Channel"
    assert about["channel_id"] == "UCtestChannelId123"
    assert about["channel_url"] == "http://www.youtube.com/channel/UCtestChannelId123"
    assert about["subscriber_count_text"] == "12.3K subscribers"
    assert "contact@testchannel.com" in about["description"]


def test_parse_about_page_raises_on_missing_metadata():
    with pytest.raises(ScrapeError):
        parse_about_page({"metadata": {}})


def test_extract_contact_info_finds_email():
    assert extract_contact_info("Reach me at hello@example.com for business.") == "hello@example.com"


def test_extract_contact_info_falls_back_to_url_when_no_email():
    description = "Check out my site!\nwww.mysite.com/contact\nThanks for watching."
    assert extract_contact_info(description) == "www.mysite.com/contact"


def test_extract_contact_info_ignores_youtube_links_and_returns_default():
    description = "Subscribe here: youtube.com/@testchannel\nNo other links."
    assert extract_contact_info(description) == "No clear contact"


def test_guess_language_defaults_to_english_for_ascii_text():
    assert guess_language("This is a normal English description about tech.") == "English"


def test_guess_language_returns_unknown_for_non_ascii_text():
    assert guess_language("これは日本語の説明です") == "Unknown"
