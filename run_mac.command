#!/bin/bash
# YouTube Lead Tracker - one-click launcher for macOS.
#
# Double-click this file in Finder. First run sets up a local, self-contained
# Python environment (one-time, a few seconds); every run after that just
# starts the app and opens your browser to it.
#
# If macOS blocks it as "from an unidentified developer": right-click (or
# Control-click) this file, choose Open, then confirm Open in the dialog
# that appears. You only need to do that once.
set -e

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 was not found on this Mac."
  echo "Install it from https://www.python.org/downloads/, then double-click this file again."
  read -r -p "Press Enter to close this window..."
  exit 1
fi

VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "First run - setting up (this only happens once)..."
  python3 -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install --quiet --upgrade pip
  "$VENV_DIR/bin/pip" install --quiet -r requirements.txt
  echo "Setup complete."
fi

echo "Starting YouTube Lead Tracker..."
"$VENV_DIR/bin/python" main.py
