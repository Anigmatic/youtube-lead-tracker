"""Production entrypoint for hosting this app on a live URL (Render, Fly.io,
etc.), separate from main.py which is for the local/desktop exe experience
(random free port, opens your browser, expects to run on your own machine).

Run with: waitress-serve --host=0.0.0.0 --port=$PORT wsgi:app
"""
import os

from app.server import create_app

DB_PATH = os.environ.get(
    "LEADS_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.db"),
)
app = create_app(DB_PATH)
