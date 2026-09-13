import pytest
import os

from app.scraper import normalize_channel_input, extract_yt_initial_data, ScrapeError, parse_about_page, extract_contact_info, guess_language, parse_videos_page, parse_relative_age_days


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


def test_parse_about_page_extracts_structured_links_section():
    html = _load_fixture("about_page_with_links.html")
    data = extract_yt_initial_data(html)
    about = parse_about_page(data)
    assert about["links"] == ["testchannel.com", "twitter.com/testchannel"]
    assert about["name"] == "Test Channel"
    assert about["subscriber_count_text"] == "5.65K subscribers"


def test_parse_about_page_falls_back_to_description_links_when_no_links_panel():
    html = _load_fixture("about_page.html")
    data = extract_yt_initial_data(html)
    about = parse_about_page(data)
    # about_page.html has no structured Links panel, but its description
    # contains "contact@testchannel.com" - that should end up in links too.
    assert about["links"] == ["contact@testchannel.com"]


def test_extract_contact_info_finds_email():
    assert extract_contact_info("Reach me at hello@example.com for business.") == "hello@example.com"


def test_extract_contact_info_falls_back_to_url_when_no_email():
    description = "Check out my site!\nwww.mysite.com/contact\nThanks for watching."
    assert extract_contact_info(description) == "www.mysite.com/contact"


def test_extract_contact_info_ignores_youtube_links_and_returns_default():
    description = "Subscribe here: youtube.com/@testchannel\nNo other links."
    assert extract_contact_info(description) == "No clear contact"


def test_extract_contact_info_uses_structured_links_when_description_has_none():
    description = "We make videos about testing things. No contact info here."
    links = ["testchannel.com", "twitter.com/testchannel"]
    assert extract_contact_info(description, links) == "testchannel.com"


def test_parse_about_page_captures_multiple_emails_from_description_into_links():
    data = {
        "metadata": {
            "channelMetadataRenderer": {
                "title": "Anabolic Stick",
                "description": (
                    "Helping you navigate the treacherous world of fitness and bodybuilding.\n\n\n"
                    "Business email: anabolicstick@blackbulb.com\n"
                    "Personal email: anabolicstick@gmail.com\n"
                ),
                "externalId": "UCanabolic123",
                "channelUrl": "http://www.youtube.com/channel/UCanabolic123",
            }
        }
    }
    about = parse_about_page(data)
    assert about["links"] == ["anabolicstick@blackbulb.com", "anabolicstick@gmail.com"]


def test_extract_contact_info_prefers_email_over_structured_links():
    description = "Reach me at hello@example.com for business."
    links = ["testchannel.com"]
    assert extract_contact_info(description, links) == "hello@example.com"


def test_guess_language_defaults_to_english_for_ascii_text():
    assert guess_language("This is a normal English description about tech.") == "English"


def test_guess_language_returns_unknown_for_non_ascii_text():
    assert guess_language("これは日本語の説明です") == "Unknown"


def test_parse_videos_page_extracts_recent_videos_in_order():
    html = _load_fixture("videos_page.html")
    data = extract_yt_initial_data(html)
    videos = parse_videos_page(data)
    assert len(videos) == 4
    assert videos[0] == {
        "video_id": "vid001",
        "title": "First Video",
        "view_count_text": "4.1K views",
        "published_text": "2 days ago",
    }
    assert videos[1]["view_count_text"] == "1.5K views"
    assert videos[2]["published_text"] == "3 months ago"


def test_parse_videos_page_finds_views_and_age_behind_an_extra_metadata_row():
    # Verified live against @shaardulogy: some videos carry an extra
    # "collab/series" label as metadataRows[0], pushing the real
    # views/upload-age row to metadataRows[1]. Only scanning rows[0] (the
    # original bug) silently dropped these videos' stats to "", which fed
    # a wrong "no recent uploads in 60+ days" fit verdict even though the
    # channel had uploaded days ago.
    html = _load_fixture("videos_page.html")
    data = extract_yt_initial_data(html)
    videos = parse_videos_page(data)
    fourth = videos[3]
    assert fourth["video_id"] == "vid004"
    assert fourth["view_count_text"] == "47K views"
    assert fourth["published_text"] == "8 days ago"


def test_parse_videos_page_respects_max_videos():
    html = _load_fixture("videos_page.html")
    data = extract_yt_initial_data(html)
    videos = parse_videos_page(data, max_videos=2)
    assert len(videos) == 2


def test_parse_videos_page_max_videos_default_still_covers_all_fixture_videos():
    html = _load_fixture("videos_page.html")
    data = extract_yt_initial_data(html)
    videos = parse_videos_page(data, max_videos=10)
    assert len(videos) == 4


def test_parse_videos_page_raises_when_videos_tab_missing():
    with pytest.raises(ScrapeError):
        parse_videos_page({"contents": {"twoColumnBrowseResultsRenderer": {"tabs": []}}})


@pytest.mark.parametrize("text,expected_days", [
    ("2 days ago", 2),
    ("1 week ago", 7),
    ("3 months ago", 90),
    ("1 year ago", 365),
    ("5 hours ago", 0),
])
def test_parse_relative_age_days(text, expected_days):
    assert parse_relative_age_days(text) == expected_days


def test_parse_relative_age_days_returns_large_number_when_unparseable():
    assert parse_relative_age_days("Premiered") >= 9999


from unittest.mock import patch, MagicMock

from app.scraper import fetch_html, scrape_channel


def test_fetch_html_returns_response_text():
    fake_response = MagicMock()
    fake_response.text = "<html>ok</html>"
    fake_response.raise_for_status = MagicMock()
    with patch("app.scraper.requests.get", return_value=fake_response) as mock_get:
        result = fetch_html("https://www.youtube.com/@testchannel/about")
    assert result == "<html>ok</html>"
    assert mock_get.call_args.kwargs["headers"]["User-Agent"]


def test_scrape_channel_combines_about_and_videos():
    about_html = _load_fixture("about_page.html")
    videos_html = _load_fixture("videos_page.html")

    def fake_fetch(url):
        return about_html if url.endswith("/about") else videos_html

    with patch("app.scraper.fetch_html", side_effect=fake_fetch):
        result = scrape_channel("@testchannel")

    assert result["about"]["name"] == "Test Channel"
    assert len(result["videos"]) == 4


def test_scrape_channel_returns_partial_when_videos_tab_fails_to_parse():
    about_html = _load_fixture("about_page.html")
    no_videos_marker_html = "<html><body>no ytInitialData here</body></html>"

    def fake_fetch(url):
        return about_html if url.endswith("/about") else no_videos_marker_html

    with patch("app.scraper.fetch_html", side_effect=fake_fetch):
        result = scrape_channel("@testchannel")

    assert result["about"]["name"] == "Test Channel"
    assert result["videos"] == []
    assert result["partial"] is True
