import requests

API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeAPIError(Exception):
    pass


def _get(path: str, params: dict) -> dict:
    resp = requests.get(f"{API_BASE}/{path}", params=params, timeout=10)
    data = resp.json()
    if "error" in data:
        raise YouTubeAPIError(data["error"].get("message", "Unknown YouTube API error"))
    return data


def get_channel_stats(api_key: str, channel_id: str) -> dict:
    data = _get("channels", {"part": "statistics", "id": channel_id, "key": api_key})
    items = data.get("items", [])
    if not items:
        raise YouTubeAPIError(f"No channel found for id {channel_id}")
    return {"subscriber_count": int(items[0]["statistics"]["subscriberCount"])}


def _get_uploads_playlist_id(api_key: str, channel_id: str) -> str:
    data = _get("channels", {"part": "contentDetails", "id": channel_id, "key": api_key})
    items = data.get("items", [])
    if not items:
        raise YouTubeAPIError(f"No channel found for id {channel_id}")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def get_recent_video_views(api_key: str, channel_id: str, max_videos: int = 10) -> list:
    uploads_playlist_id = _get_uploads_playlist_id(api_key, channel_id)
    playlist_data = _get("playlistItems", {
        "part": "contentDetails",
        "playlistId": uploads_playlist_id,
        "maxResults": max_videos,
        "key": api_key,
    })
    video_ids = [item["contentDetails"]["videoId"] for item in playlist_data.get("items", [])]
    if not video_ids:
        return []
    videos_data = _get("videos", {"part": "statistics", "id": ",".join(video_ids), "key": api_key})
    return [int(item["statistics"].get("viewCount", 0)) for item in videos_data.get("items", [])]
