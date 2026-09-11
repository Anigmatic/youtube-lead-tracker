import threading
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


def test_leads_endpoint_works_across_real_threads(tmp_path):
    app = create_app(str(tmp_path / "thread_test.db"))
    client = app.test_client()
    results = []
    errors = []

    def worker():
        try:
            resp = client.get("/api/leads")
            results.append(resp.status_code)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert results == [200, 200, 200, 200]
