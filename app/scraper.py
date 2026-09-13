import json
import re

import requests

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


class ScrapeError(Exception):
    pass


_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_URL_RE = re.compile(r"https?://\S+|(?:www\.)?[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}(?:/\S*)?")

_TAB_SUFFIXES = ("/about", "/videos", "/featured", "/streams", "/shorts", "/community", "/playlists")


def normalize_channel_input(input_str: str) -> dict:
    s = input_str.strip()
    if not s:
        raise ValueError("Empty channel input")

    if s.startswith("http://") or s.startswith("https://"):
        base = s.split("?")[0].rstrip("/")
    elif s.startswith("youtube.com/") or s.startswith("www.youtube.com/"):
        base = f"https://{s.split('?')[0].rstrip('/')}"
    elif s.startswith("@"):
        base = f"https://www.youtube.com/{s}"
    else:
        base = f"https://www.youtube.com/@{s}"

    for suffix in _TAB_SUFFIXES:
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break

    return {"about_url": f"{base}/about", "videos_url": f"{base}/videos"}


def extract_yt_initial_data(html: str) -> dict:
    marker = "var ytInitialData ="
    idx = html.find(marker)
    if idx == -1:
        marker = 'window["ytInitialData"] ='
        idx = html.find(marker)
    if idx == -1:
        raise ScrapeError("Could not locate ytInitialData in page")

    start = html.find("{", idx)
    if start == -1:
        raise ScrapeError("Could not locate start of ytInitialData JSON")

    depth = 0
    in_string = False
    escape = False
    end = -1
    for i in range(start, len(html)):
        ch = html[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if end == -1:
        raise ScrapeError("Could not find end of ytInitialData JSON")

    try:
        return json.loads(html[start:end])
    except json.JSONDecodeError as e:
        raise ScrapeError(f"Invalid ytInitialData JSON: {e}") from e


def parse_about_page(data: dict) -> dict:
    try:
        cmr = data["metadata"]["channelMetadataRenderer"]
    except KeyError as e:
        raise ScrapeError(f"Unexpected about-page structure: missing {e}") from e

    channel_id = cmr.get("externalId", "")
    subscriber_count_text = ""
    try:
        header = data["header"]["pageHeaderRenderer"]
        rows = header["content"]["pageHeaderViewModel"]["metadata"]["contentMetadataViewModel"]["metadataRows"]
        for row in rows:
            for part in row.get("metadataParts", []):
                content = part.get("text", {}).get("content", "")
                if "subscriber" in content.lower():
                    subscriber_count_text = content
                    break
            if subscriber_count_text:
                break
    except (KeyError, IndexError):
        pass

    return {
        "name": cmr.get("title", ""),
        "channel_id": channel_id,
        "channel_url": cmr.get("channelUrl") or f"https://www.youtube.com/channel/{channel_id}",
        "subscriber_count_text": subscriber_count_text,
        "description": cmr.get("description", ""),
        "links": _extract_about_links(data) or _extract_description_links(cmr.get("description", "")),
    }


def _extract_about_links(data: dict) -> list:
    """Find the About panel's structured external links (website/social),
    shown as the "Links" section in YouTube's About popup. These live in a
    separate part of the page data from the description text, so a channel
    can have real, curated contact links even when its description contains
    no email or URL at all."""
    found = []

    def walk(obj):
        if found:
            return
        if isinstance(obj, dict):
            about_vm = obj.get("aboutChannelViewModel")
            if isinstance(about_vm, dict) and about_vm.get("links"):
                found.append(about_vm["links"])
                return
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    if not found:
        return []

    contents = []
    for item in found[0]:
        vm = item.get("channelExternalLinkViewModel", {})
        content = vm.get("link", {}).get("content", "")
        if content:
            contents.append(content)
    return contents


def _extract_description_links(description: str) -> list:
    """Fallback for channels with no structured "Links" panel: pull every
    email and non-YouTube URL out of the free-text description, in the
    order they appear. Some channels (e.g. a business + a personal email)
    list more than one contact point in the description with nothing in
    the structured Links section at all — extract_contact_info only ever
    picks the single best guess for Contact Info, so this is what feeds
    the full Links column for those channels."""
    found = []
    for email in _EMAIL_RE.findall(description):
        if email not in found:
            found.append(email)
    for line in description.splitlines():
        line = line.strip()
        if not line or "youtube.com" in line.lower() or _EMAIL_RE.search(line):
            continue
        url_match = _URL_RE.search(line)
        if url_match and url_match.group(0) not in found:
            found.append(url_match.group(0))
    return found


def extract_contact_info(description: str, links: list = None) -> str:
    email_match = _EMAIL_RE.search(description)
    if email_match:
        return email_match.group(0)
    if links:
        return links[0]
    for line in description.splitlines():
        line = line.strip()
        if not line or "youtube.com" in line.lower():
            continue
        url_match = _URL_RE.search(line)
        if url_match:
            return url_match.group(0)
    return "No clear contact"


def guess_language(description: str) -> str:
    letters = [c for c in description if c.isalpha()]
    if not letters:
        return "Unknown"
    ascii_letters = [c for c in letters if c.isascii()]
    return "English" if len(ascii_letters) / len(letters) > 0.85 else "Unknown"


_AGE_UNIT_DAYS = {
    "second": 0, "minute": 0, "hour": 0,
    "day": 1, "week": 7, "month": 30, "year": 365,
}
_AGE_RE = re.compile(r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago", re.IGNORECASE)


def _find_videos_tab_contents(data: dict) -> list:
    try:
        tabs = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]
    except KeyError as e:
        raise ScrapeError(f"Unexpected videos-page structure: missing {e}") from e
    for tab in tabs:
        renderer = tab.get("tabRenderer")
        if not renderer:
            continue
        url = renderer.get("endpoint", {}).get("commandMetadata", {}).get("webCommandMetadata", {}).get("url", "")
        if url.endswith("/videos"):
            return renderer.get("content", {}).get("richGridRenderer", {}).get("contents", [])
    raise ScrapeError("Could not find Videos tab in page data")


def parse_videos_page(data: dict, max_videos: int = 10) -> list:
    items = _find_videos_tab_contents(data)
    videos = []
    for item in items:
        rich = item.get("richItemRenderer")
        if not rich:
            continue
        try:
            lockup = rich["content"]["lockupViewModel"]
            meta = lockup["metadata"]["lockupMetadataViewModel"]
            rows = meta["metadata"]["contentMetadataViewModel"]["metadataRows"]
        except (KeyError, IndexError):
            continue

        # Some channels prepend an extra metadata row (e.g. a podcast/series
        # co-branding label) before the real views/upload-age row, so the
        # views/"ago" text isn't reliably in metadataRows[0] - scan every
        # row rather than assuming position. Verified live against
        # @shaardulogy, whose "* | Master Vani Kabir" collab label pushed
        # the real "47K views" / "8 days ago" row to metadataRows[1].
        view_text, published_text = "", ""
        for row in rows:
            for part in row.get("metadataParts", []):
                content = part.get("text", {}).get("content", "")
                lc = content.lower()
                if "view" in lc and not view_text:
                    view_text = content
                elif "ago" in lc and not published_text:
                    published_text = content

        videos.append({
            "video_id": lockup.get("contentId", ""),
            "title": meta.get("title", {}).get("content", ""),
            "view_count_text": view_text,
            "published_text": published_text,
        })
        if len(videos) >= max_videos:
            break
    return videos


def parse_relative_age_days(text: str) -> int:
    match = _AGE_RE.search(text)
    if not match:
        return 10_000
    count, unit = match.groups()
    return int(count) * _AGE_UNIT_DAYS[unit.lower()]


def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


def scrape_channel(input_str: str, max_videos: int = 10) -> dict:
    urls = normalize_channel_input(input_str)
    about = parse_about_page(extract_yt_initial_data(fetch_html(urls["about_url"])))
    try:
        videos = parse_videos_page(extract_yt_initial_data(fetch_html(urls["videos_url"])), max_videos=max_videos)
    except ScrapeError:
        return {"about": about, "videos": [], "partial": True}
    return {"about": about, "videos": videos}
