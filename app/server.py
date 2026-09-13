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
        config = db.get_settings(conn)
        leads = db.list_leads(conn, config.get("target_sub_min", 0), config.get("target_sub_max", 10 ** 9))
        return jsonify(leads)

    @app.route("/api/leads/<int:lead_id>", methods=["PATCH"])
    def update_lead_route(lead_id):
        conn = get_conn()
        db.update_lead_fields(conn, lead_id, request.get_json(force=True) or {})
        return jsonify({"ok": True})

    @app.route("/api/leads/<int:lead_id>", methods=["DELETE"])
    def delete_lead_route(lead_id):
        conn = get_conn()
        db.delete_lead(conn, lead_id)
        return jsonify({"ok": True})

    @app.route("/api/leads", methods=["DELETE"])
    def clear_leads_route():
        conn = get_conn()
        db.clear_leads(conn)
        return jsonify({"ok": True})

    @app.route("/api/channels", methods=["POST"])
    def submit_channels_route():
        conn = get_conn()
        body = request.get_json(force=True) or {}
        inputs = [s.strip() for s in body.get("inputs", []) if s.strip()]
        config = db.get_settings(conn)
        sub_min = config.get("target_sub_min", 0)
        sub_max = config.get("target_sub_max", 10 ** 9)
        results = []
        skipped = []
        for raw_input in inputs:
            try:
                channel = resolve_channel(raw_input, config)
                if channel.error:
                    lead = {
                        "channel_url": raw_input,
                        "name": raw_input,
                        "fit_reason": f"Could not resolve channel: {channel.error}",
                    }
                elif not (sub_min <= channel.subscriber_count <= sub_max):
                    skipped.append({
                        "channel_url": channel.channel_url,
                        "name": channel.name,
                        "subscriber_count": channel.subscriber_count,
                        "subscriber_count_display": channel.subscriber_count_display,
                        "reason": f"{channel.subscriber_count_display} subscribers is outside your configured "
                                  f"target range ({sub_min}-{sub_max}).",
                    })
                    continue
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
                        "links": ", ".join(channel.links),
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
        return jsonify({"leads": results, "skipped": skipped})

    @app.route("/api/export")
    def export_route():
        conn = get_conn()
        config = db.get_settings(conn)
        fmt = request.args.get("format", "xlsx")
        leads = db.list_leads(conn, config.get("target_sub_min", 0), config.get("target_sub_max", 10 ** 9))
        suffix = ".xlsx" if fmt == "xlsx" else ".csv"
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        if fmt == "xlsx":
            export_xlsx(leads, path)
        else:
            export_csv(leads, path)
        return send_file(path, as_attachment=True, download_name=f"leads{suffix}")

    return app
