import json


class ScrapeError(Exception):
    pass


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
