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


def test_delete_lead_removes_row(conn):
    lead_id = db.upsert_lead(conn, {"channel_url": "https://www.youtube.com/@deleteme", "name": "Delete Me"})
    db.upsert_lead(conn, {"channel_url": "https://www.youtube.com/@keepme", "name": "Keep Me"})
    db.delete_lead(conn, lead_id)
    leads = db.list_leads(conn)
    assert len(leads) == 1
    assert leads[0]["name"] == "Keep Me"


def test_delete_lead_is_a_no_op_for_a_nonexistent_id(conn):
    db.upsert_lead(conn, {"channel_url": "https://www.youtube.com/@keepme", "name": "Keep Me"})
    db.delete_lead(conn, 999999)
    leads = db.list_leads(conn)
    assert len(leads) == 1


def test_get_settings_returns_defaults_when_unset(conn):
    settings = db.get_settings(conn)
    assert settings["youtube_api_key"] == ""
    assert settings["niche_keywords"] == []
    assert "New" in settings["status_options"]


def test_upsert_lead_stores_links_column(conn):
    db.upsert_lead(conn, {
        "channel_url": "https://www.youtube.com/@z",
        "name": "Z",
        "links": "site.com, twitter.com/z, patreon.com/z",
    })
    leads = db.list_leads(conn)
    assert leads[0]["links"] == "site.com, twitter.com/z, patreon.com/z"


def test_init_db_adds_links_column_to_pre_existing_leads_table(tmp_path):
    db_path = str(tmp_path / "legacy.db")
    legacy_conn = db.get_connection(db_path)
    legacy_conn.execute("""
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL DEFAULT '',
            channel_url TEXT NOT NULL UNIQUE
        )
    """)
    legacy_conn.execute(
        "INSERT INTO leads (date, channel_url) VALUES ('2026-01-01', 'https://www.youtube.com/@legacy')"
    )
    legacy_conn.commit()
    legacy_conn.close()

    upgraded_conn = db.get_connection(db_path)
    db.init_db(upgraded_conn)
    leads = db.list_leads(upgraded_conn)
    assert leads[0]["links"] == ""
    upgraded_conn.close()


def test_save_settings_merges_into_existing(conn):
    db.save_settings(conn, {"niche_keywords": ["ai", "smma"]})
    db.save_settings(conn, {"youtube_api_key": "abc123"})
    settings = db.get_settings(conn)
    assert settings["niche_keywords"] == ["ai", "smma"]
    assert settings["youtube_api_key"] == "abc123"
