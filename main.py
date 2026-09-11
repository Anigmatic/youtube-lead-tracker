import os
import socket
import sys
import threading
import time
import webbrowser

from waitress import serve

from app.server import create_app


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_data_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def main():
    db_path = os.path.join(get_data_dir(), "leads.db")
    app = create_app(db_path)
    port = get_free_port()
    url = f"http://127.0.0.1:{port}"

    def open_browser():
        time.sleep(1.0)
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()
    print(f"YouTube Lead Tracker running at {url}")
    serve(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
