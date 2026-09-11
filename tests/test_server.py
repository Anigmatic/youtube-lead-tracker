from app.server import create_app


def test_create_app_returns_flask_app(tmp_path):
    db_path = str(tmp_path / "test_leads.db")
    app = create_app(db_path)
    assert app is not None
    client = app.test_client()
    resp = client.get("/api/leads")
    assert resp.status_code == 200
    assert resp.get_json() == []
