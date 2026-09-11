import os

from flask import Flask, jsonify

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def create_app(db_path: str) -> Flask:
    app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")

    @app.route("/api/leads", methods=["GET"])
    def list_leads_route():
        return jsonify([])

    return app
