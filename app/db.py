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
    "contact_info", "links", "fit_assessment", "fit_reason",
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
            links TEXT NOT NULL DEFAULT '',
            fit_assessment TEXT NOT NULL DEFAULT '',
            fit_reason TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '',
            outreach_method TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT ''
        )
    """)
    _ensure_column(conn, "leads", "links", "TEXT NOT NULL DEFAULT ''")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            data TEXT NOT NULL
        )
    """)
    conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    """Add a column to an existing table if it's missing, so a leads.db
    created before this column existed still upgrades cleanly."""
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


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
