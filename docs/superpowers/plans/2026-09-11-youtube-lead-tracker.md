# YouTube Lead Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Windows application that, given a YouTube channel (single or bulk), scrapes/queries public data and fills in a persistent lead-tracker row (subscribers, avg views, contact info, fit assessment).

**Architecture:** Flask backend (served by waitress) + one static HTML/JS frontend page + local SQLite storage, all packaged into a single PyInstaller `.exe`. Channel data comes from scraping YouTube's public pages (parsing the `ytInitialData` JSON embedded in server-rendered HTML — verified against a live channel page during design) always, supplemented by the free YouTube Data API v3 for exact stats when the user configures a key. Fit assessment uses a free LLM API (e.g. Groq) when configured, falling back to a rule-based scorer.

**Tech Stack:** Python 3.11+, Flask, waitress, requests, openpyxl, pytest, PyInstaller.

**Spec:** [docs/superpowers/specs/2026-09-11-youtube-lead-tracker-design.md](../specs/2026-09-11-youtube-lead-tracker-design.md)

## Global Constraints

- No YouTube login/OAuth — public data only.
- No headless browser / Playwright dependency — parse server-rendered `ytInitialData` JSON directly via `requests`, to keep the packaged `.exe` small and reliable (confirmed during design that `https://www.youtube.com/@handle/about` and `/videos` serve this JSON in a `<script>` tag on a plain unauthenticated fetch).
- Every scraped/API value must degrade gracefully — a failure for one channel must not abort a bulk batch.
- No API keys are bundled into the build; each user configures their own (optional) keys in Settings, stored in their local SQLite file.
- Tests must not make real network calls — use fixtures and monkeypatched `requests` calls throughout.

---

## Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `pytest.ini`
- Create: `app/__init__.py`
- Create: `app/server.py`
- Create: `tests/__init__.py`
- Create: `tests/test_server.py`

**Interfaces:**
- Produces: `app.server.create_app(db_path: str) -> flask.Flask` — used by every later task that touches routes, and by `main.py` in Task 15.

- [ ] **Step 1: Create `requirements.txt`**

```
Flask==3.0.3
waitress==3.0.0
requests==2.32.3
openpyxl==3.1.5
```

- [ ] **Step 2: Create `requirements-dev.txt`**

```
-r requirements.txt
pytest==8.3.3
pyinstaller==6.10.0
```

- [ ] **Step 3: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
```

- [ ] **Step 4: Create empty `app/__init__.py` and `tests/__init__.py`**

Both files are empty — their presence makes `app` and `tests` packages so pytest's import-mode inserts the project root (not `tests/`) onto `sys.path`, letting tests do `from app import ...`.

- [ ] **Step 5: Install dependencies**

Run: `pip install -r requirements-dev.txt`

- [ ] **Step 6: Write the failing test for the app factory**

`tests/test_server.py`:

```python
from app.server import create_app


def test_create_app_returns_flask_app(tmp_path):
    db_path = str(tmp_path / "test_leads.db")
    app = create_app(db_path)
    assert app is not None
    client = app.test_client()
    resp = client.get("/api/leads")
    assert resp.status_code == 200
    assert resp.get_json() == []
```

- [ ] **Step 7: Run test to verify it fails**

Run: `pytest tests/test_server.py -v`
Expected: FAIL (`ModuleNotFoundError` or `ImportError` — `create_app` doesn't exist yet)

- [ ] **Step 8: Write minimal `app/server.py`**

```python
import os

from flask import Flask, jsonify

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def create_app(db_path: str) -> Flask:
    app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")

    @app.route("/api/leads", methods=["GET"])
    def list_leads_route():
        return jsonify([])

    return app
```

- [ ] **Step 9: Run test to verify it passes**

Run: `pytest tests/test_server.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add requirements.txt requirements-dev.txt pytest.ini app/__init__.py app/server.py tests/__init__.py tests/test_server.py
git commit -m "chore: scaffold project with minimal Flask app factory"
```

---

## Task 2: Count parsing/formatting helpers

**Files:**
- Create: `app/counts.py`
- Test: `tests/test_counts.py`

**Interfaces:**
- Produces: `parse_count(text: str) -> int`, `format_count(n: int) -> str` — used by `app/scraper.py` (Task 4-7), `app/channel_resolver.py` (Task 9), and `app/fit_scoring.py` (Task 10).

- [ ] **Step 1: Write the failing tests**

`tests/test_counts.py`:

```python
import pytest

from app.counts import parse_count, format_count


@pytest.mark.parametrize("text,expected", [
    ("21.2M subscribers", 21_200_000),
    ("1.5K", 1500),
    ("523", 523),
    ("14M views", 14_000_000),
    ("1,234", 1234),
    ("113", 113),
])
def test_parse_count(text, expected):
    assert parse_count(text) == expected


def test_parse_count_raises_on_unparseable_text():
    with pytest.raises(ValueError):
        parse_count("no digits here")


@pytest.mark.parametrize("n,expected", [
    (523, "523"),
    (5650, "5.65K"),
    (21_200_000, "21.2M"),
    (1_000, "1K"),
    (0, "0"),
])
def test_format_count(n, expected):
    assert format_count(n) == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_counts.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.counts'`)

- [ ] **Step 3: Write `app/counts.py`**

```python
import re

_SUFFIXES = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
_COUNT_RE = re.compile(r"([\d,]*\.?\d+)\s*([KMB]?)", re.IGNORECASE)


def parse_count(text: str) -> int:
    """Parse strings like '21.2M subscribers', '1.5K', '523', '14M views' into an int."""
    match = _COUNT_RE.search(text.strip())
    if not match or not match.group(1):
        raise ValueError(f"Could not parse count from: {text!r}")
    number = float(match.group(1).replace(",", ""))
    multiplier = _SUFFIXES.get(match.group(2).upper(), 1)
    return int(number * multiplier)


def format_count(n: int) -> str:
    """Format an int back into YouTube-style short form, e.g. 5650 -> '5.65K'."""
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        value, suffix = n / 1_000, "K"
    elif n < 1_000_000_000:
        value, suffix = n / 1_000_000, "M"
    else:
        value, suffix = n / 1_000_000_000, "B"
    formatted = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{formatted}{suffix}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_counts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/counts.py tests/test_counts.py
git commit -m "feat: add YouTube-style count parsing/formatting helpers"
```

---

## Task 3: SQLite storage layer

**Files:**
- Create: `app/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `get_connection(db_path: str) -> sqlite3.Connection`, `init_db(conn) -> None`, `upsert_lead(conn, lead: dict) -> int`, `list_leads(conn) -> list[dict]`, `update_lead_fields(conn, lead_id: int, fields: dict) -> None`, `get_settings(conn) -> dict`, `save_settings(conn, settings: dict) -> None` — used by `app/server.py` (Task 13) and `main.py` (Task 15).
- Consumes: nothing from earlier tasks.

- [ ] **Step 1: Write the failing tests**

`tests/test_db.py`:

```python
import pytest

from app import db


@pytest.fixture
def conn(tmp_path):
    connection = db.get_connection(str(tmp_path / "test.db"))
    db.init_db(connection)
    yield connection
    connection.close()


def test_upsert_lead_inserts_new_row(conn):
    lead_id = db.upsert_lead(conn, {
        "channel_url": "https://www.youtube.com/@testchannel",
        "name": "Test Channel",
        "subscriber_count": 1000,
        "subscriber_count_display": "1K",
    })
    assert lead_id is not None
    leads = db.list_leads(conn)
    assert len(leads) == 1
    assert leads[0]["name"] == "Test Channel"
    assert leads[0]["channel_url"] == "https://www.youtube.com/@testchannel"


def test_upsert_lead_updates_existing_row_by_channel_url(conn):
    db.upsert_lead(conn, {"channel_url": "https://www.youtube.com/@x", "name": "Old Name"})
    db.upsert_lead(conn, {"channel_url": "https://www.youtube.com/@x", "name": "New Name"})
    leads = db.list_leads(conn)
    assert len(leads) == 1
    assert leads[0]["name"] == "New Name"


def test_update_lead_fields_only_touches_allowed_fields(conn):
    lead_id = db.upsert_lead(conn, {"channel_url": "https://www.youtube.com/@y", "name": "Y"})
    db.update_lead_fields(conn, lead_id, {"status": "Contacted", "notes": "Sent DM", "name": "Should Not Change"})
    leads = db.list_leads(conn)
    assert leads[0]["status"] == "Contacted"
    assert leads[0]["notes"] == "Sent DM"
    assert leads[0]["name"] == "Y"


def test_get_settings_returns_defaults_when_unset(conn):
    settings = db.get_settings(conn)
    assert settings["youtube_api_key"] == ""
    assert settings["niche_keywords"] == []
    assert "New" in settings["status_options"]


def test_save_settings_merges_into_existing(conn):
    db.save_settings(conn, {"niche_keywords": ["ai", "smma"]})
    db.save_settings(conn, {"youtube_api_key": "abc123"})
    settings = db.get_settings(conn)
    assert settings["niche_keywords"] == ["ai", "smma"]
    assert settings["youtube_api_key"] == "abc123"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.db'`)

- [ ] **Step 3: Write `app/db.py`**

```python
import datetime
import json
import sqlite3

_DEFAULT_SETTINGS = {
    "youtube_api_key": "",
    "llm_provider": "groq",
    "llm_api_key": "",
    "llm_model": "llama-3.1-8b-instant",
    "niche_keywords": [],
    "target_sub_min": 0,
    "target_sub_max": 10_000_000,
    "ideal_lead_description": "",
    "status_options": ["New", "Contacted", "Replied", "Not Interested", "Closed"],
    "outreach_options": ["Email", "YouTube Comment", "Instagram DM", "Other"],
}

_LEAD_COLUMNS = [
    "date", "language", "name", "channel_url",
    "subscriber_count", "subscriber_count_display",
    "avg_views_min", "avg_views_max", "avg_views_display",
    "contact_info", "fit_assessment", "fit_reason",
    "status", "outreach_method", "notes",
]

_UPDATABLE_FIELDS = {"language", "status", "outreach_method", "notes"}


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL DEFAULT '',
            language TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL DEFAULT '',
            channel_url TEXT NOT NULL UNIQUE,
            subscriber_count INTEGER NOT NULL DEFAULT 0,
            subscriber_count_display TEXT NOT NULL DEFAULT '',
            avg_views_min INTEGER NOT NULL DEFAULT 0,
            avg_views_max INTEGER NOT NULL DEFAULT 0,
            avg_views_display TEXT NOT NULL DEFAULT '',
            contact_info TEXT NOT NULL DEFAULT '',
            fit_assessment TEXT NOT NULL DEFAULT '',
            fit_reason TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '',
            outreach_method TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            data TEXT NOT NULL
        )
    """)
    conn.commit()


def upsert_lead(conn: sqlite3.Connection, lead: dict) -> int:
    lead = dict(lead)
    lead.setdefault("date", datetime.date.today().isoformat())
    existing = conn.execute(
        "SELECT id FROM leads WHERE channel_url = ?", (lead["channel_url"],)
    ).fetchone()
    values = [lead.get(col, "") for col in _LEAD_COLUMNS]
    if existing:
        set_clause = ", ".join(f"{col} = ?" for col in _LEAD_COLUMNS)
        conn.execute(f"UPDATE leads SET {set_clause} WHERE id = ?", (*values, existing["id"]))
        lead_id = existing["id"]
    else:
        placeholders = ", ".join("?" for _ in _LEAD_COLUMNS)
        cur = conn.execute(
            f"INSERT INTO leads ({', '.join(_LEAD_COLUMNS)}) VALUES ({placeholders})", values
        )
        lead_id = cur.lastrowid
    conn.commit()
    return lead_id


def list_leads(conn: sqlite3.Connection) -> list:
    rows = conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


def update_lead_fields(conn: sqlite3.Connection, lead_id: int, fields: dict) -> None:
    updates = {k: v for k, v in fields.items() if k in _UPDATABLE_FIELDS}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(f"UPDATE leads SET {set_clause} WHERE id = ?", (*updates.values(), lead_id))
    conn.commit()


def get_settings(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT data FROM settings WHERE id = 1").fetchone()
    merged = dict(_DEFAULT_SETTINGS)
    if row:
        merged.update(json.loads(row["data"]))
    return merged


def save_settings(conn: sqlite3.Connection, settings: dict) -> None:
    merged = get_settings(conn)
    merged.update(settings)
    conn.execute(
        "INSERT INTO settings (id, data) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET data = excluded.data",
        (json.dumps(merged),),
    )
    conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/db.py tests/test_db.py
git commit -m "feat: add SQLite storage layer for leads and settings"
```

---

## Task 4: Channel input normalization and ytInitialData extraction

**Files:**
- Create: `app/scraper.py`
- Test: `tests/test_scraper.py`

**Interfaces:**
- Produces: `normalize_channel_input(input_str: str) -> dict` (keys `about_url`, `videos_url`), `extract_yt_initial_data(html: str) -> dict`, `ScrapeError` exception — used later in this same module (Tasks 5-7) and by `app/channel_resolver.py` (Task 9).

- [ ] **Step 1: Write the failing tests**

`tests/test_scraper.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scraper.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.scraper'`)

- [ ] **Step 3: Write `app/scraper.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scraper.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/scraper.py tests/test_scraper.py
git commit -m "feat: add channel URL normalization and ytInitialData extraction"
```

---

## Task 5: About-page parsing and contact/language extraction

**Files:**
- Modify: `app/scraper.py` (add functions, keep existing ones)
- Test: `tests/test_scraper.py` (add tests)
- Create: `tests/fixtures/about_page.html`

**Interfaces:**
- Consumes: `extract_yt_initial_data` (Task 4)
- Produces: `parse_about_page(data: dict) -> dict` (keys `name`, `channel_id`, `channel_url`, `subscriber_count_text`, `description`), `extract_contact_info(description: str) -> str`, `guess_language(description: str) -> str` — used by `app/channel_resolver.py` (Task 9).

- [ ] **Step 1: Create the fixture**

`tests/fixtures/about_page.html` — a trimmed but structurally faithful copy of what a real `/about` page embeds (verified live against `youtube.com/@mkbhd/about` during design: `metadata.channelMetadataRenderer` holds title/description/externalId, `header.pageHeaderRenderer.content.pageHeaderViewModel.metadata.contentMetadataViewModel.metadataRows` holds the handle row then the subscribers/videos row):

```html
<html><head></head><body><script nonce="x">var ytInitialData = {"metadata":{"channelMetadataRenderer":{"title":"Test Channel","description":"A channel about testing things.\n\ncontact@testchannel.com\n\nBusiness inquiries only.","externalId":"UCtestChannelId123","channelUrl":"http://www.youtube.com/channel/UCtestChannelId123"}},"header":{"pageHeaderRenderer":{"content":{"pageHeaderViewModel":{"metadata":{"contentMetadataViewModel":{"metadataRows":[{"metadataParts":[{"text":{"content":"@testchannel"}}]},{"metadataParts":[{"text":{"content":"12.3K subscribers"}},{"text":{"content":"87 videos"}}]}]}}}}}}};</script></body></html>
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_scraper.py`:

```python
import os

from app.scraper import parse_about_page, extract_contact_info, guess_language

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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_scraper.py -v`
Expected: FAIL (`ImportError: cannot import name 'parse_about_page'`)

- [ ] **Step 4: Add functions to `app/scraper.py`**

Add near the top (after the `ScrapeError` class):

```python
import re

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_URL_RE = re.compile(r"https?://\S+|(?:www\.)?[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}(?:/\S*)?")
```

Append at the end of `app/scraper.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_scraper.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/scraper.py tests/test_scraper.py tests/fixtures/about_page.html
git commit -m "feat: parse channel about-page data and extract contact info/language"
```

---

## Task 6: Videos-page parsing and upload-recency helper

**Files:**
- Modify: `app/scraper.py`
- Test: `tests/test_scraper.py`
- Create: `tests/fixtures/videos_page.html`

**Interfaces:**
- Consumes: `extract_yt_initial_data` (Task 4)
- Produces: `parse_videos_page(data: dict, max_videos: int = 10) -> list[dict]` (each item has `video_id`, `title`, `view_count_text`, `published_text`), `parse_relative_age_days(text: str) -> int` — used by `app/channel_resolver.py` (Task 9).

- [ ] **Step 1: Create the fixture**

`tests/fixtures/videos_page.html` — trimmed but structurally faithful to a real `/videos` page (verified live against `youtube.com/@mkbhd/videos`: the Videos tab is identified by its `tabRenderer.endpoint...webCommandMetadata.url` ending in `/videos`, and each video is a `richItemRenderer.content.lockupViewModel` with `contentId`, a title, and a metadata row whose parts include the view-count text and the relative upload-age text):

```html
<html><head></head><body><script nonce="x">var ytInitialData = {"contents":{"twoColumnBrowseResultsRenderer":{"tabs":[{"tabRenderer":{"title":"Home","endpoint":{"commandMetadata":{"webCommandMetadata":{"url":"/@testchannel/featured"}}},"content":{}}},{"tabRenderer":{"title":"Videos","endpoint":{"commandMetadata":{"webCommandMetadata":{"url":"/@testchannel/videos"}}},"content":{"richGridRenderer":{"contents":[{"richItemRenderer":{"content":{"lockupViewModel":{"contentId":"vid001","metadata":{"lockupMetadataViewModel":{"title":{"content":"First Video"},"metadata":{"contentMetadataViewModel":{"metadataRows":[{"metadataParts":[{"text":{"content":"4.1K views"}},{"text":{"content":"2 days ago"}}]}]}}}}}}}},{"richItemRenderer":{"content":{"lockupViewModel":{"contentId":"vid002","metadata":{"lockupMetadataViewModel":{"title":{"content":"Second Video"},"metadata":{"contentMetadataViewModel":{"metadataRows":[{"metadataParts":[{"text":{"content":"1.5K views"}},{"text":{"content":"1 week ago"}}]}]}}}}}}}},{"richItemRenderer":{"content":{"lockupViewModel":{"contentId":"vid003","metadata":{"lockupMetadataViewModel":{"title":{"content":"Third Video"},"metadata":{"contentMetadataViewModel":{"metadataRows":[{"metadataParts":[{"text":{"content":"2.3K views"}},{"text":{"content":"3 months ago"}}]}]}}}}}}}}]}}}}]}}}};</script></body></html>
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_scraper.py`:

```python
from app.scraper import parse_videos_page, parse_relative_age_days


def test_parse_videos_page_extracts_recent_videos_in_order():
    html = _load_fixture("videos_page.html")
    data = extract_yt_initial_data(html)
    videos = parse_videos_page(data)
    assert len(videos) == 3
    assert videos[0] == {
        "video_id": "vid001",
        "title": "First Video",
        "view_count_text": "4.1K views",
        "published_text": "2 days ago",
    }
    assert videos[1]["view_count_text"] == "1.5K views"
    assert videos[2]["published_text"] == "3 months ago"


def test_parse_videos_page_respects_max_videos():
    html = _load_fixture("videos_page.html")
    data = extract_yt_initial_data(html)
    videos = parse_videos_page(data, max_videos=2)
    assert len(videos) == 2


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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_scraper.py -v`
Expected: FAIL (`ImportError: cannot import name 'parse_videos_page'`)

- [ ] **Step 4: Add functions to `app/scraper.py`**

Append at the end:

```python
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

        view_text, published_text = "", ""
        for part in rows[0].get("metadataParts", []):
            content = part.get("text", {}).get("content", "")
            lc = content.lower()
            if "view" in lc:
                view_text = content
            elif "ago" in lc:
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_scraper.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/scraper.py tests/test_scraper.py tests/fixtures/videos_page.html
git commit -m "feat: parse recent videos and upload recency from videos page"
```

---

## Task 7: HTTP fetch and scrape orchestration

**Files:**
- Modify: `app/scraper.py`
- Test: `tests/test_scraper.py`

**Interfaces:**
- Consumes: `normalize_channel_input`, `extract_yt_initial_data`, `parse_about_page`, `parse_videos_page` (Tasks 4-6)
- Produces: `fetch_html(url: str) -> str`, `scrape_channel(input_str: str, max_videos: int = 10) -> dict` (keys `about`, `videos`) — used by `app/channel_resolver.py` (Task 9).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scraper.py`:

```python
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
    assert len(result["videos"]) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scraper.py -v`
Expected: FAIL (`ImportError: cannot import name 'fetch_html'`)

- [ ] **Step 3: Add functions to `app/scraper.py`**

Add near the top (with the other imports):

```python
import requests

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
```

Append at the end of `app/scraper.py`:

```python
def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


def scrape_channel(input_str: str, max_videos: int = 10) -> dict:
    urls = normalize_channel_input(input_str)
    about = parse_about_page(extract_yt_initial_data(fetch_html(urls["about_url"])))
    videos = parse_videos_page(extract_yt_initial_data(fetch_html(urls["videos_url"])), max_videos=max_videos)
    return {"about": about, "videos": videos}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scraper.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/scraper.py tests/test_scraper.py
git commit -m "feat: fetch channel pages over HTTP and orchestrate scraping"
```

---

## Task 8: YouTube Data API client

**Files:**
- Create: `app/youtube_api.py`
- Test: `tests/test_youtube_api.py`

**Interfaces:**
- Produces: `YouTubeAPIError` exception, `get_channel_stats(api_key: str, channel_id: str) -> dict` (key `subscriber_count`), `get_recent_video_views(api_key: str, channel_id: str, max_videos: int = 10) -> list[int]` — used by `app/channel_resolver.py` (Task 9).

- [ ] **Step 1: Write the failing tests**

`tests/test_youtube_api.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_youtube_api.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.youtube_api'`)

- [ ] **Step 3: Write `app/youtube_api.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_youtube_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/youtube_api.py tests/test_youtube_api.py
git commit -m "feat: add YouTube Data API v3 client for exact channel stats"
```

---

## Task 9: Channel resolver (hybrid API + scrape orchestration)

**Files:**
- Create: `app/channel_resolver.py`
- Test: `tests/test_channel_resolver.py`

**Interfaces:**
- Consumes: `app.scraper.{normalize_channel_input, fetch_html, extract_yt_initial_data, parse_about_page, parse_videos_page, extract_contact_info, guess_language, parse_relative_age_days, ScrapeError}` (Tasks 4-7), `app.youtube_api.{get_channel_stats, get_recent_video_views, YouTubeAPIError}` (Task 8), `app.counts.{parse_count, format_count}` (Task 2)
- Produces: `ChannelData` dataclass (fields: `name`, `channel_url`, `description`, `subscriber_count`, `subscriber_count_display`, `avg_views_min`, `avg_views_max`, `avg_views_display`, `contact_info`, `language`, `latest_upload_age_days`, `data_source`, `error`), `resolve_channel(input_str: str, config: dict) -> ChannelData` — used by `app/server.py` (Task 13).

- [ ] **Step 1: Write the failing tests**

`tests/test_channel_resolver.py`:

```python
from unittest.mock import patch

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
        return_value={"about": about or _ABOUT, "videos": videos or _VIDEOS},
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_channel_resolver.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.channel_resolver'`)

- [ ] **Step 3: Write `app/channel_resolver.py`**

```python
from dataclasses import dataclass

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
    language: str = "Unknown"
    latest_upload_age_days: int = 10_000
    data_source: str = "scrape"
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
        except YouTubeAPIError:
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
        contact_info=extract_contact_info(about["description"]),
        language=guess_language(about["description"]),
        latest_upload_age_days=latest_upload_age_days,
        data_source=data_source,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_channel_resolver.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/channel_resolver.py tests/test_channel_resolver.py
git commit -m "feat: add hybrid API/scrape channel resolver"
```

---

## Task 10: Rule-based fit scorer

**Files:**
- Create: `app/fit_scoring.py`
- Test: `tests/test_fit_scoring.py`

**Interfaces:**
- Consumes: `ChannelData` (Task 9)
- Produces: `score_fit_rule_based(channel: ChannelData, config: dict) -> tuple[str, str]` (level, reason) — used by `app/server.py` (Task 13).

- [ ] **Step 1: Write the failing tests**

`tests/test_fit_scoring.py`:

```python
from app.channel_resolver import ChannelData
from app.fit_scoring import score_fit_rule_based

_CONFIG = {
    "niche_keywords": ["ai", "smma", "growth"],
    "target_sub_min": 1000,
    "target_sub_max": 100_000,
}


def test_high_fit_when_keyword_matches_in_range_and_active():
    channel = ChannelData(
        name="AI Growth Integrator",
        description="Helping SMMA agencies scale with AI.",
        subscriber_count=5650,
        avg_views_max=4100,
        latest_upload_age_days=5,
    )
    level, reason = score_fit_rule_based(channel, _CONFIG)
    assert level == "High"
    assert "niche" in reason.lower()


def test_low_fit_when_no_keyword_out_of_range_and_stale():
    channel = ChannelData(
        name="Random Cooking Channel",
        description="Recipes and cooking tips.",
        subscriber_count=500_000,
        avg_views_max=200,
        latest_upload_age_days=400,
    )
    level, reason = score_fit_rule_based(channel, _CONFIG)
    assert level == "Low"


def test_moderate_fit_when_two_of_three_checks_pass():
    channel = ChannelData(
        name="Growth School",
        description="Learn growth marketing skool.com/growthschool",
        subscriber_count=29_800,
        avg_views_max=7900,
        latest_upload_age_days=400,
    )
    level, reason = score_fit_rule_based(channel, _CONFIG)
    assert level == "Moderate"


def test_scorer_ignores_keyword_check_when_no_keywords_configured():
    channel = ChannelData(
        name="Anything",
        description="No relevant keywords here.",
        subscriber_count=5000,
        avg_views_max=1000,
        latest_upload_age_days=1,
    )
    level, _ = score_fit_rule_based(channel, {"niche_keywords": [], "target_sub_min": 0, "target_sub_max": 10**9})
    assert level == "High"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fit_scoring.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.fit_scoring'`)

- [ ] **Step 3: Write `app/fit_scoring.py`**

```python
def score_fit_rule_based(channel, config: dict) -> tuple:
    keywords = [k.strip().lower() for k in config.get("niche_keywords", []) if k.strip()]
    haystack = f"{channel.name} {channel.description}".lower()

    reasons = []
    score = 0
    max_score = 2

    if keywords:
        max_score = 3
        if any(k in haystack for k in keywords):
            score += 1
            reasons.append("matches niche keywords")
        else:
            reasons.append("no niche keyword match")

    sub_min = config.get("target_sub_min", 0)
    sub_max = config.get("target_sub_max", 10 ** 9)
    if sub_min <= channel.subscriber_count <= sub_max:
        score += 1
        reasons.append("subscriber count in target range")
    else:
        reasons.append("subscriber count outside target range")

    if channel.latest_upload_age_days <= 60:
        score += 1
        reasons.append("active in the last 60 days")
    else:
        reasons.append("no recent uploads in 60+ days")

    ratio = score / max_score if max_score else 0
    if ratio >= 0.99:
        level = "High"
    elif ratio >= 0.5:
        level = "Moderate"
    else:
        level = "Low"

    reason = (", ".join(reasons) + ".")
    reason = reason[0].upper() + reason[1:]
    return level, reason
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fit_scoring.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/fit_scoring.py tests/test_fit_scoring.py
git commit -m "feat: add rule-based fit scorer"
```

---

## Task 11: LLM-based fit scorer (Groq)

**Files:**
- Create: `app/llm_fit.py`
- Test: `tests/test_llm_fit.py`

**Interfaces:**
- Consumes: `ChannelData` (Task 9)
- Produces: `LLMError` exception, `score_fit_llm(channel: ChannelData, config: dict) -> tuple[str, str]` (level, reason) — used by `app/server.py` (Task 13).

- [ ] **Step 1: Write the failing tests**

`tests/test_llm_fit.py`:

```python
from unittest.mock import patch, MagicMock

import pytest

from app.channel_resolver import ChannelData
from app.llm_fit import score_fit_llm, LLMError

_CHANNEL = ChannelData(
    name="AI Growth Integrator",
    description="Helping SMMA agencies scale with AI.",
    subscriber_count=5650,
    avg_views_display="1.5K-4.1K",
    latest_upload_age_days=5,
)
_CONFIG = {
    "llm_api_key": "fake-key",
    "llm_model": "llama-3.1-8b-instant",
    "niche_keywords": ["ai", "smma"],
    "target_sub_min": 1000,
    "target_sub_max": 100_000,
    "ideal_lead_description": "Small AI/SMMA education channels",
}


def _mock_llm_response(content, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = content
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return resp


def test_score_fit_llm_parses_high_fit_response():
    content = "High Fit - Consistent uploads and solid niche in AI/SMMA growth."
    with patch("app.llm_fit.requests.post", return_value=_mock_llm_response(content)):
        level, reason = score_fit_llm(_CHANNEL, _CONFIG)
    assert level == "High"
    assert "consistent uploads" in reason.lower()


def test_score_fit_llm_raises_without_api_key():
    with pytest.raises(LLMError):
        score_fit_llm(_CHANNEL, {**_CONFIG, "llm_api_key": ""})


def test_score_fit_llm_raises_on_non_200_response():
    resp = MagicMock()
    resp.status_code = 401
    resp.text = "unauthorized"
    with patch("app.llm_fit.requests.post", return_value=resp):
        with pytest.raises(LLMError):
            score_fit_llm(_CHANNEL, _CONFIG)


def test_score_fit_llm_raises_when_level_cannot_be_determined():
    with patch("app.llm_fit.requests.post", return_value=_mock_llm_response("I'm not sure about this one.")):
        with pytest.raises(LLMError):
            score_fit_llm(_CHANNEL, _CONFIG)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_llm_fit.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.llm_fit'`)

- [ ] **Step 3: Write `app/llm_fit.py`**

```python
import requests

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class LLMError(Exception):
    pass


def score_fit_llm(channel, config: dict) -> tuple:
    api_key = config.get("llm_api_key")
    if not api_key:
        raise LLMError("No LLM API key configured")
    model = config.get("llm_model") or "llama-3.1-8b-instant"

    try:
        resp = requests.post(
            _GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a lead-qualification assistant for YouTube outreach. "
                            "Respond with exactly one line in the form: "
                            "'<High|Moderate|Low> Fit - <one short reason>'."
                        ),
                    },
                    {"role": "user", "content": _build_prompt(channel, config)},
                ],
                "temperature": 0.2,
                "max_tokens": 60,
            },
            timeout=20,
        )
    except requests.RequestException as e:
        raise LLMError(f"LLM request failed: {e}") from e

    if resp.status_code != 200:
        raise LLMError(f"LLM API returned {resp.status_code}: {resp.text[:200]}")

    try:
        content = resp.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected LLM response shape: {e}") from e

    return _parse_verdict(content)


def _build_prompt(channel, config: dict) -> str:
    return (
        f"Ideal lead criteria: {config.get('ideal_lead_description', 'Not specified')}\n"
        f"Niche keywords: {', '.join(config.get('niche_keywords', []))}\n"
        f"Target subscriber range: {config.get('target_sub_min', 0)}-{config.get('target_sub_max', 'unlimited')}\n\n"
        f"Channel name: {channel.name}\n"
        f"Description: {channel.description[:500]}\n"
        f"Subscribers: {channel.subscriber_count}\n"
        f"Recent video views range: {channel.avg_views_display}\n"
        f"Most recent upload: {channel.latest_upload_age_days} days ago\n"
    )


def _parse_verdict(content: str) -> tuple:
    lower = content.lower()
    if "high" in lower:
        level = "High"
    elif "moderate" in lower:
        level = "Moderate"
    elif "low" in lower:
        level = "Low"
    else:
        raise LLMError(f"Could not determine fit level from LLM response: {content!r}")

    reason = content
    if "-" in content:
        reason = content.split("-", 1)[1].strip()
    elif ":" in content:
        reason = content.split(":", 1)[1].strip()
    return level, reason
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_llm_fit.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/llm_fit.py tests/test_llm_fit.py
git commit -m "feat: add free-LLM-backed fit scorer with structured verdict parsing"
```

---

## Task 12: Export to CSV/XLSX

**Files:**
- Create: `app/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Produces: `export_csv(leads: list[dict], path: str) -> None`, `export_xlsx(leads: list[dict], path: str) -> None` — used by `app/server.py` (Task 13).

- [ ] **Step 1: Write the failing tests**

`tests/test_export.py`:

```python
import csv

import openpyxl

from app.export import export_csv, export_xlsx

_LEADS = [
    {
        "date": "2026-09-11", "language": "English", "name": "Test Channel",
        "channel_url": "https://www.youtube.com/@testchannel",
        "subscriber_count_display": "5.65K", "avg_views_display": "1.5K-4.1K",
        "contact_info": "contact@testchannel.com", "fit_assessment": "High",
        "fit_reason": "Matches niche.", "status": "New", "outreach_method": "Email", "notes": "",
    },
]


def test_export_csv_writes_header_and_rows(tmp_path):
    path = tmp_path / "leads.csv"
    export_csv(_LEADS, str(path))
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0][0] == "Date"
    assert "Test Channel" in rows[1]
    assert "contact@testchannel.com" in rows[1]


def test_export_xlsx_writes_header_and_rows(tmp_path):
    path = tmp_path / "leads.xlsx"
    export_xlsx(_LEADS, str(path))
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    header = [cell.value for cell in ws[1]]
    data_row = [cell.value for cell in ws[2]]
    assert header[0] == "Date"
    assert "Test Channel" in data_row
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_export.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.export'`)

- [ ] **Step 3: Write `app/export.py`**

```python
import csv

import openpyxl

_COLUMNS = [
    ("date", "Date"),
    ("language", "Language"),
    ("name", "Name"),
    ("channel_url", "Channel URL"),
    ("subscriber_count_display", "Subscriber Count"),
    ("avg_views_display", "Avg Views/Video"),
    ("contact_info", "Contact Info"),
    ("fit_assessment", "Fit Assessment"),
    ("fit_reason", "Fit Reason"),
    ("status", "Status"),
    ("outreach_method", "Outreach Method"),
    ("notes", "Notes"),
]


def export_csv(leads: list, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([label for _, label in _COLUMNS])
        for lead in leads:
            writer.writerow([lead.get(key, "") for key, _ in _COLUMNS])


def export_xlsx(leads: list, path: str) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Leads"
    ws.append([label for _, label in _COLUMNS])
    for lead in leads:
        ws.append([lead.get(key, "") for key, _ in _COLUMNS])
    wb.save(path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_export.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/export.py tests/test_export.py
git commit -m "feat: add CSV/XLSX export matching the lead tracker column layout"
```

---

## Task 13: Flask routes (settings, leads, channel submission, export)

**Files:**
- Modify: `app/server.py` (replace the minimal factory from Task 1 with the full set of routes)
- Modify: `tests/test_server.py`

**Interfaces:**
- Consumes: `app.db` (Task 3), `app.channel_resolver.resolve_channel` (Task 9), `app.fit_scoring.score_fit_rule_based` (Task 10), `app.llm_fit.{score_fit_llm, LLMError}` (Task 11), `app.export.{export_csv, export_xlsx}` (Task 12)
- Produces: `create_app(db_path: str) -> Flask` with routes `GET/POST /api/settings`, `GET /api/leads`, `PATCH /api/leads/<id>`, `POST /api/channels`, `GET /api/export`, `GET /` — used by `main.py` (Task 15).

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_server.py` entirely:

```python
from unittest.mock import patch

import pytest

from app.channel_resolver import ChannelData
from app.server import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / "test.db"))
    return app.test_client()


def test_list_leads_starts_empty(client):
    resp = client.get("/api/leads")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_get_settings_returns_defaults(client):
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    assert resp.get_json()["youtube_api_key"] == ""


def test_post_settings_persists_changes(client):
    resp = client.post("/api/settings", json={"niche_keywords": ["ai", "smma"]})
    assert resp.status_code == 200
    assert resp.get_json()["niche_keywords"] == ["ai", "smma"]
    resp2 = client.get("/api/settings")
    assert resp2.get_json()["niche_keywords"] == ["ai", "smma"]


def test_submit_channels_resolves_and_scores_and_stores(client):
    channel = ChannelData(
        name="AI Growth Integrator",
        channel_url="https://www.youtube.com/@aigrowth",
        description="AI SMMA growth content.",
        subscriber_count=5650,
        subscriber_count_display="5.65K",
        avg_views_min=1500,
        avg_views_max=4100,
        avg_views_display="1.5K-4.1K",
        contact_info="aigrowthintegrator.com/yt",
        language="English",
        latest_upload_age_days=5,
    )
    with patch("app.server.resolve_channel", return_value=channel), \
         patch("app.server.score_fit_llm", side_effect=Exception("no key")):
        resp = client.post("/api/channels", json={"inputs": ["@aigrowth"]})
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body) == 1
    assert body[0]["name"] == "AI Growth Integrator"
    assert body[0]["fit_assessment"] in {"High", "Moderate", "Low"}

    leads = client.get("/api/leads").get_json()
    assert len(leads) == 1


def test_submit_channels_records_error_row_when_resolution_fails(client):
    error_channel = ChannelData(error="Could not locate ytInitialData in page")
    with patch("app.server.resolve_channel", return_value=error_channel):
        resp = client.post("/api/channels", json={"inputs": ["@badhandle"]})
    body = resp.get_json()
    assert len(body) == 1
    assert "Could not resolve channel" in body[0]["fit_reason"]


def test_patch_lead_updates_editable_fields(client):
    channel = ChannelData(name="X", channel_url="https://www.youtube.com/@x")
    with patch("app.server.resolve_channel", return_value=channel), \
         patch("app.server.score_fit_llm", side_effect=Exception("no key")):
        client.post("/api/channels", json={"inputs": ["@x"]})
    lead_id = client.get("/api/leads").get_json()[0]["id"]

    resp = client.patch(f"/api/leads/{lead_id}", json={"status": "Contacted", "notes": "Sent DM"})
    assert resp.status_code == 200

    leads = client.get("/api/leads").get_json()
    assert leads[0]["status"] == "Contacted"
    assert leads[0]["notes"] == "Sent DM"


def test_export_route_returns_downloadable_file(client):
    channel = ChannelData(name="X", channel_url="https://www.youtube.com/@x")
    with patch("app.server.resolve_channel", return_value=channel), \
         patch("app.server.score_fit_llm", side_effect=Exception("no key")):
        client.post("/api/channels", json={"inputs": ["@x"]})

    resp = client.get("/api/export?format=csv")
    assert resp.status_code == 200
    assert resp.headers["Content-Disposition"].startswith("attachment")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_server.py -v`
Expected: FAIL (routes/imports referenced in the tests don't exist yet)

- [ ] **Step 3: Rewrite `app/server.py`**

```python
import os
import tempfile

from flask import Flask, jsonify, request, send_file

from . import db
from .channel_resolver import resolve_channel
from .export import export_csv, export_xlsx
from .fit_scoring import score_fit_rule_based
from .llm_fit import score_fit_llm

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def create_app(db_path: str) -> Flask:
    app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")
    conn = db.get_connection(db_path)
    db.init_db(conn)

    @app.route("/")
    def index():
        return app.send_static_file("index.html")

    @app.route("/api/settings", methods=["GET"])
    def get_settings_route():
        return jsonify(db.get_settings(conn))

    @app.route("/api/settings", methods=["POST"])
    def save_settings_route():
        db.save_settings(conn, request.get_json(force=True) or {})
        return jsonify(db.get_settings(conn))

    @app.route("/api/leads", methods=["GET"])
    def list_leads_route():
        return jsonify(db.list_leads(conn))

    @app.route("/api/leads/<int:lead_id>", methods=["PATCH"])
    def update_lead_route(lead_id):
        db.update_lead_fields(conn, lead_id, request.get_json(force=True) or {})
        return jsonify({"ok": True})

    @app.route("/api/channels", methods=["POST"])
    def submit_channels_route():
        body = request.get_json(force=True) or {}
        inputs = [s.strip() for s in body.get("inputs", []) if s.strip()]
        config = db.get_settings(conn)
        results = []
        for raw_input in inputs:
            channel = resolve_channel(raw_input, config)
            if channel.error:
                lead = {
                    "channel_url": raw_input,
                    "name": raw_input,
                    "fit_reason": f"Could not resolve channel: {channel.error}",
                }
            else:
                try:
                    level, reason = score_fit_llm(channel, config)
                except Exception:
                    level, reason = score_fit_rule_based(channel, config)
                lead = {
                    "language": channel.language,
                    "name": channel.name,
                    "channel_url": channel.channel_url,
                    "subscriber_count": channel.subscriber_count,
                    "subscriber_count_display": channel.subscriber_count_display,
                    "avg_views_min": channel.avg_views_min,
                    "avg_views_max": channel.avg_views_max,
                    "avg_views_display": channel.avg_views_display,
                    "contact_info": channel.contact_info,
                    "fit_assessment": level,
                    "fit_reason": reason,
                }
            lead_id = db.upsert_lead(conn, lead)
            row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
            results.append(dict(row))
        return jsonify(results)

    @app.route("/api/export")
    def export_route():
        fmt = request.args.get("format", "xlsx")
        leads = db.list_leads(conn)
        suffix = ".xlsx" if fmt == "xlsx" else ".csv"
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        if fmt == "xlsx":
            export_xlsx(leads, path)
        else:
            export_csv(leads, path)
        return send_file(path, as_attachment=True, download_name=f"leads{suffix}")

    return app
```

Note: `score_fit_llm` is caught with a broad `except Exception` here (rather than only `LLMError`) so that if no LLM key is configured at all, the call's internal `LLMError("No LLM API key configured")` still falls through to the rule-based scorer — this is intentional per the spec's "fully usable with zero API keys" requirement, and matches how the test mocks a generic `Exception` to simulate "no key".

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_server.py -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: All tests across every module PASS

- [ ] **Step 6: Commit**

```bash
git add app/server.py tests/test_server.py
git commit -m "feat: wire up Flask routes for settings, leads, channel submission, and export"
```

---

## Task 14: Frontend UI

**Files:**
- Create: `app/static/index.html`
- Create: `app/static/app.js`
- Create: `app/static/style.css`

**Interfaces:**
- Consumes: the JSON API from Task 13 (`GET/POST /api/settings`, `GET /api/leads`, `PATCH /api/leads/<id>`, `POST /api/channels`, `GET /api/export`)

This task has no automated tests — it's verified manually in Step 5.

- [ ] **Step 1: Create `app/static/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>YouTube Lead Tracker</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header>
    <h1>YouTube Lead Tracker</h1>
    <button id="settingsBtn">Settings</button>
    <button id="exportBtn">Export</button>
  </header>

  <section id="inputPanel">
    <textarea id="channelInput" placeholder="Paste one channel URL/handle per line (or a single one)"></textarea>
    <button id="submitBtn">Add Channel(s)</button>
    <span id="statusMsg"></span>
  </section>

  <table id="leadsTable">
    <thead>
      <tr>
        <th>Date</th><th>Language</th><th>Name</th><th>Subscribers</th>
        <th>Avg Views/Video</th><th>Contact Info</th><th>Fit Assessment</th>
        <th>Status</th><th>Outreach Method</th><th>Notes</th>
      </tr>
    </thead>
    <tbody id="leadsBody"></tbody>
  </table>

  <dialog id="settingsDialog">
    <form id="settingsForm">
      <label>YouTube Data API key (optional) <input type="text" name="youtube_api_key"></label>
      <label>LLM API key (optional, e.g. Groq) <input type="text" name="llm_api_key"></label>
      <label>LLM model <input type="text" name="llm_model"></label>
      <label>Niche keywords (comma-separated) <input type="text" name="niche_keywords"></label>
      <label>Target subscriber min <input type="number" name="target_sub_min"></label>
      <label>Target subscriber max <input type="number" name="target_sub_max"></label>
      <label>Ideal lead description <textarea name="ideal_lead_description"></textarea></label>
      <button type="submit">Save</button>
      <button type="button" id="closeSettingsBtn">Close</button>
    </form>
  </dialog>

  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create `app/static/style.css`**

```css
body { font-family: system-ui, sans-serif; margin: 1.5rem; }
header { display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem; }
header h1 { font-size: 1.25rem; margin: 0; flex: 1; }
#inputPanel { display: flex; gap: 0.5rem; align-items: flex-start; margin-bottom: 1rem; }
#channelInput { width: 28rem; height: 4rem; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.85rem; }
th { background: #f4f4f4; }
tr[data-fit="High"] td.fit { background: #d7f5d7; }
tr[data-fit="Moderate"] td.fit { background: #fff2c9; }
tr[data-fit="Low"] td.fit { background: #f8d7d7; }
dialog form { display: flex; flex-direction: column; gap: 0.6rem; min-width: 22rem; }
```

- [ ] **Step 3: Create `app/static/app.js`**

```javascript
const leadsBody = document.getElementById("leadsBody");
const channelInput = document.getElementById("channelInput");
const statusMsg = document.getElementById("statusMsg");
const settingsDialog = document.getElementById("settingsDialog");
const settingsForm = document.getElementById("settingsForm");

const STATUS_OPTIONS = ["New", "Contacted", "Replied", "Not Interested", "Closed"];
const OUTREACH_OPTIONS = ["Email", "YouTube Comment", "Instagram DM", "Other"];

function renderRow(lead) {
  const tr = document.createElement("tr");
  tr.dataset.fit = lead.fit_assessment || "";
  tr.dataset.id = lead.id;

  const nameCell = `<a href="${lead.channel_url}" target="_blank">${lead.name || lead.channel_url}</a>`;
  const fitCell = `${lead.fit_assessment || ""} - ${lead.fit_reason || ""}`;

  tr.innerHTML = `
    <td>${lead.date || ""}</td>
    <td>${lead.language || ""}</td>
    <td>${nameCell}</td>
    <td>${lead.subscriber_count_display || ""}</td>
    <td>${lead.avg_views_display || ""}</td>
    <td>${lead.contact_info || ""}</td>
    <td class="fit">${fitCell}</td>
    <td class="status-cell"></td>
    <td class="outreach-cell"></td>
    <td class="notes-cell"><input type="text" value="${lead.notes || ""}"></td>
  `;

  const statusSelect = document.createElement("select");
  STATUS_OPTIONS.forEach((opt) => {
    const o = document.createElement("option");
    o.value = opt;
    o.textContent = opt;
    if (opt === lead.status) o.selected = true;
    statusSelect.appendChild(o);
  });
  statusSelect.addEventListener("change", () => patchLead(lead.id, { status: statusSelect.value }));
  tr.querySelector(".status-cell").appendChild(statusSelect);

  const outreachSelect = document.createElement("select");
  OUTREACH_OPTIONS.forEach((opt) => {
    const o = document.createElement("option");
    o.value = opt;
    o.textContent = opt;
    if (opt === lead.outreach_method) o.selected = true;
    outreachSelect.appendChild(o);
  });
  outreachSelect.addEventListener("change", () => patchLead(lead.id, { outreach_method: outreachSelect.value }));
  tr.querySelector(".outreach-cell").appendChild(outreachSelect);

  const notesInput = tr.querySelector(".notes-cell input");
  notesInput.addEventListener("change", () => patchLead(lead.id, { notes: notesInput.value }));

  return tr;
}

async function loadLeads() {
  const resp = await fetch("/api/leads");
  const leads = await resp.json();
  leadsBody.innerHTML = "";
  leads.forEach((lead) => leadsBody.appendChild(renderRow(lead)));
}

async function patchLead(id, fields) {
  await fetch(`/api/leads/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
}

document.getElementById("submitBtn").addEventListener("click", async () => {
  const inputs = channelInput.value.split("\n").map((s) => s.trim()).filter(Boolean);
  if (!inputs.length) return;
  statusMsg.textContent = "Processing...";
  const resp = await fetch("/api/channels", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inputs }),
  });
  if (resp.ok) {
    channelInput.value = "";
    statusMsg.textContent = "Done.";
    await loadLeads();
  } else {
    statusMsg.textContent = "Error processing channels.";
  }
});

document.getElementById("exportBtn").addEventListener("click", () => {
  window.location.href = "/api/export?format=xlsx";
});

document.getElementById("settingsBtn").addEventListener("click", async () => {
  const resp = await fetch("/api/settings");
  const settings = await resp.json();
  for (const [key, value] of Object.entries(settings)) {
    const field = settingsForm.elements[key];
    if (!field) continue;
    field.value = Array.isArray(value) ? value.join(", ") : value;
  }
  settingsDialog.showModal();
});

document.getElementById("closeSettingsBtn").addEventListener("click", () => settingsDialog.close());

settingsForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const formData = new FormData(settingsForm);
  const payload = Object.fromEntries(formData.entries());
  payload.niche_keywords = payload.niche_keywords.split(",").map((s) => s.trim()).filter(Boolean);
  payload.target_sub_min = Number(payload.target_sub_min) || 0;
  payload.target_sub_max = Number(payload.target_sub_max) || 10000000;
  await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  settingsDialog.close();
});

loadLeads();
```

- [ ] **Step 4: Manual smoke test — run the dev server**

Run: `python -c "from app.server import create_app; create_app('smoke_test.db').run(port=5000)"`

- [ ] **Step 5: Manual smoke test — exercise the UI**

Open `http://127.0.0.1:5000` in a browser. Confirm: the page loads with an empty table, pasting a channel handle and clicking "Add Channel(s)" shows a status message and (network permitting) a new row, editing Status/Outreach/Notes persists after a page refresh, "Export" downloads a file, and "Settings" opens/saves correctly. Stop the server (Ctrl+C) and delete `smoke_test.db` afterward.

- [ ] **Step 6: Commit**

```bash
git add app/static/index.html app/static/app.js app/static/style.css
git commit -m "feat: add frontend UI for input, results table, settings, and export"
```

---

## Task 15: Application entry point

**Files:**
- Create: `main.py`

**Interfaces:**
- Consumes: `app.server.create_app` (Task 13)

This task has no automated tests (it starts a real server/thread/browser) — it's verified manually in Step 3.

- [ ] **Step 1: Create `main.py`**

```python
import os
import socket
import sys
import threading
import time
import webbrowser

from waitress import serve

from app.server import create_app


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_data_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def main():
    db_path = os.path.join(get_data_dir(), "leads.db")
    app = create_app(db_path)
    port = get_free_port()
    url = f"http://127.0.0.1:{port}"

    def open_browser():
        time.sleep(1.0)
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()
    print(f"YouTube Lead Tracker running at {url}")
    serve(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Manual smoke test**

Run: `python main.py`
Expected: console prints the URL, default browser opens automatically to the app, the leads table loads (empty on first run), and `leads.db` is created next to `main.py`. Stop with Ctrl+C, delete the generated `leads.db`.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add application entry point (port selection, browser launch, waitress server)"
```

---

## Task 16: Packaging into a standalone .exe

**Files:**
- Create: `build.spec`
- Create: `build.bat`

**Interfaces:**
- Consumes: `main.py` (Task 15), `app/static/*` (Task 14)

This task has no automated tests — packaging is verified manually in Step 4.

- [ ] **Step 1: Create `build.spec`**

```python
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('app/static', 'app/static')],
    hiddenimports=['waitress'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='YouTubeLeadTracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    onefile=True,
)
```

- [ ] **Step 2: Create `build.bat`**

```bat
@echo off
pip install -r requirements-dev.txt
pyinstaller build.spec --noconfirm
echo Build complete: dist\YouTubeLeadTracker.exe
```

- [ ] **Step 3: Run the build**

Run: `build.bat`
Expected: `dist\YouTubeLeadTracker.exe` is created without errors.

- [ ] **Step 4: Manual verification on a clean environment**

Copy `dist\YouTubeLeadTracker.exe` to a folder with no Python installed (or a fresh VM/user account). Double-click it. Expected: a console window appears, the default browser opens automatically to the app, and the UI is fully functional (add a channel, edit a row, export). Confirm `leads.db` is created next to the `.exe`.

- [ ] **Step 5: Commit**

```bash
git add build.spec build.bat
git commit -m "chore: add PyInstaller packaging for standalone distribution"
```
