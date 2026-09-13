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
        links=["aigrowthintegrator.com/yt", "twitter.com/aigrowth"],
        language="English",
        latest_upload_age_days=5,
    )
    with patch("app.server.resolve_channel", return_value=channel), \
         patch("app.server.score_fit_llm", side_effect=Exception("no key")):
        resp = client.post("/api/channels", json={"inputs": ["@aigrowth"]})
    assert resp.status_code == 200
    body = resp.get_json()["leads"]
    assert len(body) == 1
    assert body[0]["name"] == "AI Growth Integrator"
    assert body[0]["fit_assessment"] in {"High", "Moderate", "Low"}
    assert body[0]["links"] == "aigrowthintegrator.com/yt, twitter.com/aigrowth"

    leads = client.get("/api/leads").get_json()
    assert len(leads) == 1


def test_submit_channels_records_error_row_when_resolution_fails(client):
    error_channel = ChannelData(error="Could not locate ytInitialData in page")
    with patch("app.server.resolve_channel", return_value=error_channel):
        resp = client.post("/api/channels", json={"inputs": ["@badhandle"]})
    body = resp.get_json()["leads"]
    assert len(body) == 1
    assert "Could not resolve channel" in body[0]["fit_reason"]


def test_submit_channels_continues_batch_when_one_input_raises(client):
    good_channel_1 = ChannelData(name="Good 1", channel_url="https://www.youtube.com/@good1")
    good_channel_2 = ChannelData(name="Good 2", channel_url="https://www.youtube.com/@good2")

    with patch(
        "app.server.resolve_channel",
        side_effect=[good_channel_1, ConnectionError("boom"), good_channel_2],
    ), patch("app.server.score_fit_llm", side_effect=Exception("no key")):
        resp = client.post(
            "/api/channels",
            json={"inputs": ["@good1", "@badone", "@good2"]},
        )

    assert resp.status_code == 200
    body = resp.get_json()["leads"]
    assert len(body) == 3
    assert body[0]["name"] == "Good 1"
    assert "Could not resolve channel:" in body[1]["fit_reason"]
    assert body[2]["name"] == "Good 2"

    leads = client.get("/api/leads").get_json()
    assert len(leads) == 3


def test_submit_channels_skips_channel_outside_subscriber_range(client):
    client.post("/api/settings", json={"target_sub_min": 1000, "target_sub_max": 100000})
    too_big = ChannelData(
        name="Mega Channel", channel_url="https://www.youtube.com/@mega", subscriber_count=8_000_000,
        subscriber_count_display="8M",
    )
    in_range = ChannelData(
        name="Right-Sized Channel", channel_url="https://www.youtube.com/@right", subscriber_count=50_000,
        subscriber_count_display="50K",
    )
    with patch("app.server.resolve_channel", side_effect=[too_big, in_range]), \
         patch("app.server.score_fit_llm", side_effect=Exception("no key")):
        resp = client.post("/api/channels", json={"inputs": ["@mega", "@right"]})

    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["leads"]) == 1
    assert body["leads"][0]["name"] == "Right-Sized Channel"
    assert len(body["skipped"]) == 1
    assert body["skipped"][0]["name"] == "Mega Channel"
    assert "outside your configured target range" in body["skipped"][0]["reason"]

    leads = client.get("/api/leads").get_json()
    assert len(leads) == 1
    assert leads[0]["name"] == "Right-Sized Channel"


def test_submit_channels_does_not_skip_when_range_is_default(client):
    channel = ChannelData(name="X", channel_url="https://www.youtube.com/@x", subscriber_count=8_000_000)
    with patch("app.server.resolve_channel", return_value=channel), \
         patch("app.server.score_fit_llm", side_effect=Exception("no key")):
        resp = client.post("/api/channels", json={"inputs": ["@x"]})

    body = resp.get_json()
    assert len(body["leads"]) == 1
    assert body["skipped"] == []


def test_submit_channels_sets_status_new_for_successfully_resolved_lead(client):
    channel = ChannelData(name="X", channel_url="https://www.youtube.com/@x")
    with patch("app.server.resolve_channel", return_value=channel), \
         patch("app.server.score_fit_llm", side_effect=Exception("no key")):
        resp = client.post("/api/channels", json={"inputs": ["@x"]})
    body = resp.get_json()["leads"]
    assert body[0]["status"] == "New"

    leads = client.get("/api/leads").get_json()
    assert leads[0]["status"] == "New"


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


def test_delete_lead_route_removes_row(client):
    channel = ChannelData(name="X", channel_url="https://www.youtube.com/@x")
    with patch("app.server.resolve_channel", return_value=channel), \
         patch("app.server.score_fit_llm", side_effect=Exception("no key")):
        client.post("/api/channels", json={"inputs": ["@x"]})
    lead_id = client.get("/api/leads").get_json()[0]["id"]

    resp = client.delete(f"/api/leads/{lead_id}")
    assert resp.status_code == 200

    leads = client.get("/api/leads").get_json()
    assert leads == []


def test_delete_lead_route_is_a_no_op_for_a_nonexistent_id(client):
    resp = client.delete("/api/leads/999999")
    assert resp.status_code == 200


def test_clear_leads_route_removes_all_rows(client):
    channel_1 = ChannelData(name="A", channel_url="https://www.youtube.com/@a")
    channel_2 = ChannelData(name="B", channel_url="https://www.youtube.com/@b")
    with patch("app.server.resolve_channel", side_effect=[channel_1, channel_2]), \
         patch("app.server.score_fit_llm", side_effect=Exception("no key")):
        client.post("/api/channels", json={"inputs": ["@a", "@b"]})
    assert len(client.get("/api/leads").get_json()) == 2

    resp = client.delete("/api/leads")
    assert resp.status_code == 200
    assert client.get("/api/leads").get_json() == []


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
