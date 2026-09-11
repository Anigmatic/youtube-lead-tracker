from unittest.mock import patch, MagicMock

import pytest

from app.youtube_api import get_channel_stats, get_recent_video_views, YouTubeAPIError


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    return resp


def test_get_channel_stats_returns_subscriber_count():
    payload = {"items": [{"statistics": {"subscriberCount": "21200000"}}]}
    with patch("app.youtube_api.requests.get", return_value=_mock_response(payload)):
        result = get_channel_stats("fake-key", "UCtest")
    assert result == {"subscriber_count": 21_200_000}


def test_get_channel_stats_defaults_to_zero_when_subscriber_count_hidden():
    payload = {"items": [{"statistics": {"hiddenSubscriberCount": True}}]}
    with patch("app.youtube_api.requests.get", return_value=_mock_response(payload)):
        result = get_channel_stats("fake-key", "UCtest")
    assert result == {"subscriber_count": 0}


def test_get_channel_stats_raises_when_channel_not_found():
    with patch("app.youtube_api.requests.get", return_value=_mock_response({"items": []})):
        with pytest.raises(YouTubeAPIError):
            get_channel_stats("fake-key", "UCmissing")


def test_get_channel_stats_raises_on_api_error_payload():
    payload = {"error": {"message": "API key invalid"}}
    with patch("app.youtube_api.requests.get", return_value=_mock_response(payload)):
        with pytest.raises(YouTubeAPIError, match="API key invalid"):
            get_channel_stats("bad-key", "UCtest")


def test_get_recent_video_views_chains_playlist_and_video_lookups():
    channels_payload = {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUtest"}}}]}
    playlist_payload = {"items": [
        {"contentDetails": {"videoId": "vid001"}},
        {"contentDetails": {"videoId": "vid002"}},
    ]}
    videos_payload = {"items": [
        {"statistics": {"viewCount": "4100"}},
        {"statistics": {"viewCount": "1500"}},
    ]}

    responses = [
        _mock_response(channels_payload),
        _mock_response(playlist_payload),
        _mock_response(videos_payload),
    ]
    with patch("app.youtube_api.requests.get", side_effect=responses):
        views = get_recent_video_views("fake-key", "UCtest")
    assert views == [4100, 1500]


def test_get_recent_video_views_returns_empty_list_when_no_uploads():
    channels_payload = {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUtest"}}}]}
    playlist_payload = {"items": []}
    with patch("app.youtube_api.requests.get", side_effect=[_mock_response(channels_payload), _mock_response(playlist_payload)]):
        views = get_recent_video_views("fake-key", "UCtest")
    assert views == []
