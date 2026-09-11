from unittest.mock import patch

import requests

from app.channel_resolver import resolve_channel, ChannelData
from app.youtube_api import YouTubeAPIError

_ABOUT = {
    "name": "Test Channel",
    "channel_id": "UCtest123",
    "channel_url": "https://www.youtube.com/channel/UCtest123",
    "subscriber_count_text": "12.3K subscribers",
    "description": "A test channel.\n\ncontact@testchannel.com",
}
_VIDEOS = [
    {"video_id": "v1", "title": "V1", "view_count_text": "4.1K views", "published_text": "2 days ago"},
    {"video_id": "v2", "title": "V2", "view_count_text": "1.5K views", "published_text": "1 week ago"},
]

_CONFIG = {"youtube_api_key": ""}


def _patch_scrape(about=None, videos=None):
    return patch(
        "app.channel_resolver.scrape_channel",
        return_value={
            "about": about if about is not None else _ABOUT,
            "videos": videos if videos is not None else _VIDEOS,
        },
    )


def test_resolve_channel_uses_scrape_data_when_no_api_key():
    with _patch_scrape():
        result = resolve_channel("@testchannel", _CONFIG)
    assert isinstance(result, ChannelData)
    assert result.error is None
    assert result.name == "Test Channel"
    assert result.subscriber_count == 12_300
    assert result.subscriber_count_display == "12.3K"
    assert result.avg_views_min == 1_500
    assert result.avg_views_max == 4_100
    assert result.avg_views_display == "1.5K-4.1K"
    assert result.contact_info == "contact@testchannel.com"
    assert result.latest_upload_age_days == 2
    assert result.data_source == "scrape"


def test_resolve_channel_uses_api_data_when_key_configured_and_call_succeeds():
    config = {"youtube_api_key": "fake-key"}
    with _patch_scrape(), \
         patch("app.channel_resolver.get_channel_stats", return_value={"subscriber_count": 12_345}), \
         patch("app.channel_resolver.get_recent_video_views", return_value=[9000, 3000]):
        result = resolve_channel("@testchannel", config)
    assert result.subscriber_count == 12_345
    assert result.avg_views_min == 3000
    assert result.avg_views_max == 9000
    assert result.data_source == "api"


def test_resolve_channel_falls_back_to_scrape_data_when_api_call_fails():
    config = {"youtube_api_key": "fake-key"}
    with _patch_scrape(), \
         patch("app.channel_resolver.get_channel_stats", side_effect=YouTubeAPIError("quota exceeded")):
        result = resolve_channel("@testchannel", config)
    assert result.subscriber_count == 12_300
    assert result.data_source == "scrape"


def test_resolve_channel_returns_error_result_when_scrape_fails():
    with patch("app.channel_resolver.scrape_channel", side_effect=ValueError("Empty channel input")):
        result = resolve_channel("", _CONFIG)
    assert result.error == "Empty channel input"


def test_resolve_channel_handles_no_videos_found():
    with _patch_scrape(videos=[]):
        result = resolve_channel("@testchannel", _CONFIG)
    assert result.avg_views_display == "N/A"
    assert result.latest_upload_age_days == 10_000


def test_resolve_channel_falls_back_to_scrape_data_when_api_raises_youtube_api_error():
    config = {"youtube_api_key": "fake-key"}
    with _patch_scrape(), \
         patch("app.channel_resolver.get_channel_stats", side_effect=YouTubeAPIError("quota exceeded")):
        result = resolve_channel("@testchannel", config)
    assert result.error is None
    assert result.data_source == "scrape"
    assert result.subscriber_count == 12_300


def test_resolve_channel_falls_back_to_scrape_data_when_api_raises_connection_error():
    config = {"youtube_api_key": "fake-key"}
    with _patch_scrape(), \
         patch("app.channel_resolver.get_channel_stats", side_effect=requests.ConnectionError("boom")):
        result = resolve_channel("@testchannel", config)
    assert result.error is None
    assert result.data_source == "scrape"
    assert result.subscriber_count == 12_300


def test_resolve_channel_returns_partial_true_when_videos_scrape_is_partial():
    about = dict(_ABOUT)
    with patch(
        "app.channel_resolver.scrape_channel",
        return_value={"about": about, "videos": [], "partial": True},
    ):
        result = resolve_channel("@testchannel", _CONFIG)
    assert result.error is None
    assert result.name == "Test Channel"
    assert result.subscriber_count == 12_300
    assert result.partial is True
