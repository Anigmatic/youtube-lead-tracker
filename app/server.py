import os
import tempfile

from flask import Flask, g, jsonify, request, send_file

from . import db
from .channel_resolver import resolve_channel
from .export import export_csv, export_xlsx
from .fit_scoring import score_fit_rule_based
from .llm_fit import score_fit_llm

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def create_app(db_path: str) -> Flask:
    app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")

    startup_conn = db.get_connection(db_path)
    db.init_db(startup_conn)
    startup_conn.close()

    def get_conn():
        if "db_conn" not in g:
            g.db_conn = db.get_connection(db_path)
        return g.db_conn

    @app.teardown_appcontext
    def close_conn(exception=None):
        conn = g.pop("db_conn", None)
        if conn is not None:
            conn.close()

    @app.route("/")
    def index():
        return app.send_static_file("index.html")

    @app.route("/api/settings", methods=["GET"])
    def get_settings_route():
        conn = get_conn()
        return jsonify(db.get_settings(conn))

    @app.route("/api/settings", methods=["POST"])
    def save_settings_route():
        conn = get_conn()
        db.save_settings(conn, request.get_json(force=True) or {})
        return jsonify(db.get_settings(conn))

    @app.route("/api/leads", methods=["GET"])
    def list_leads_route():
        conn = get_conn()
        return jsonify(db.list_leads(conn))

    @app.route("/api/leads/<int:lead_id>", methods=["PATCH"])
    def update_lead_route(lead_id):
        conn = get_conn()
        db.update_lead_fields(conn, lead_id, request.get_json(force=True) or {})
        return jsonify({"ok": True})

    @app.route("/api/channels", methods=["POST"])
    def submit_channels_route():
        conn = get_conn()
        body = request.get_json(force=True) or {}
        inputs = [s.strip() for s in body.get("inputs", []) if s.strip()]
        config = db.get_settings(conn)
        results = []
        for raw_input in inputs:
            try:
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
                    if channel.partial:
                        reason = f"{reason} (could not fully verify recent video stats)"
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
                        "status": "New",
                    }
            except Exception as e:
                lead = {
                    "channel_url": raw_input,
                    "name": raw_input,
                    "fit_reason": f"Could not resolve channel: {e}",
                }
            lead_id = db.upsert_lead(conn, lead)
            row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
            results.append(dict(row))
        return jsonify(results)

    @app.route("/api/export")
    def export_route():
        conn = get_conn()
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
