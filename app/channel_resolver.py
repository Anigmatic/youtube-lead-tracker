from dataclasses import dataclass, field

import requests

from .counts import format_count, parse_count
from .scraper import ScrapeError, extract_contact_info, guess_language, parse_relative_age_days, scrape_channel
from .youtube_api import YouTubeAPIError, get_channel_stats, get_recent_video_views


@dataclass
class ChannelData:
    name: str = ""
    channel_url: str = ""
    description: str = ""
    subscriber_count: int = 0
    subscriber_count_display: str = ""
    avg_views_min: int = 0
    avg_views_max: int = 0
    avg_views_display: str = "N/A"
    contact_info: str = "No clear contact"
    links: list = field(default_factory=list)
    language: str = "Unknown"
    latest_upload_age_days: int = 10_000
    data_source: str = "scrape"
    partial: bool = False
    error: str = None


def resolve_channel(input_str: str, config: dict) -> ChannelData:
    try:
        scraped = scrape_channel(input_str)
    except (ScrapeError, ValueError, requests.RequestException) as e:
        return ChannelData(error=str(e))

    about = scraped["about"]
    videos = scraped["videos"]

    try:
        subscriber_count = parse_count(about["subscriber_count_text"]) if about["subscriber_count_text"] else 0
    except ValueError:
        subscriber_count = 0

    scraped_views = []
    for v in videos:
        if v.get("view_count_text"):
            try:
                scraped_views.append(parse_count(v["view_count_text"]))
            except ValueError:
                pass
    ages = [parse_relative_age_days(v["published_text"]) for v in videos if v.get("published_text")]
    latest_upload_age_days = min(ages) if ages else 10_000

    views_for_avg = scraped_views
    data_source = "scrape"

    api_key = config.get("youtube_api_key")
    if api_key and about.get("channel_id"):
        try:
            stats = get_channel_stats(api_key, about["channel_id"])
            subscriber_count = stats["subscriber_count"]
            api_views = get_recent_video_views(api_key, about["channel_id"])
            if api_views:
                views_for_avg = api_views
            data_source = "api"
        except (YouTubeAPIError, requests.RequestException):
            pass

    if views_for_avg:
        avg_min, avg_max = min(views_for_avg), max(views_for_avg)
        avg_display = f"{format_count(avg_min)}-{format_count(avg_max)}"
    else:
        avg_min = avg_max = 0
        avg_display = "N/A"

    return ChannelData(
        name=about["name"],
        channel_url=about["channel_url"],
        description=about["description"],
        subscriber_count=subscriber_count,
        subscriber_count_display=format_count(subscriber_count),
        avg_views_min=avg_min,
        avg_views_max=avg_max,
        avg_views_display=avg_display,
        contact_info=extract_contact_info(about["description"], about.get("links")),
        links=about.get("links") or [],
        language=guess_language(about["description"]),
        latest_upload_age_days=latest_upload_age_days,
        data_source=data_source,
        partial=scraped.get("partial", False),
    )
