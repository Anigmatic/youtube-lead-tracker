#!/bin/bash
# Build a native standalone binary for the current OS (run this ON a Mac to
# get a Mac binary, or on Linux to get a Linux binary - PyInstaller cannot
# cross-compile, so build.bat/build.sh must each run on their own OS).
set -e

cd "$(dirname "$0")"

python3 -m venv .build-venv
".build-venv/bin/pip" install --quiet --upgrade pip
".build-venv/bin/pip" install --quiet -r requirements-dev.txt
".build-venv/bin/pyinstaller" build.spec --noconfirm

echo "Build complete: dist/YouTubeLeadTracker"
