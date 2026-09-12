import importlib


def test_wsgi_app_is_a_working_flask_app(tmp_path, monkeypatch):
    # LEADS_DB_PATH forces wsgi.py to use an isolated tmp file instead of the
    # real project-root leads.db a developer may be using with `python
    # main.py` - this test must never touch that file.
    monkeypatch.setenv("LEADS_DB_PATH", str(tmp_path / "test_leads.db"))
    import wsgi
    importlib.reload(wsgi)

    client = wsgi.app.test_client()
    resp = client.get("/api/leads")
    assert resp.status_code == 200
    assert resp.get_json() == []
