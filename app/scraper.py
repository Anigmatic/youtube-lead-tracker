import json
import re


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
    }


def extract_contact_info(description: str) -> str:
    email_match = _EMAIL_RE.search(description)
    if email_match:
        return email_match.group(0)
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
