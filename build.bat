@echo off
pip install -r requirements-dev.txt
pyinstaller build.spec --noconfirm
echo Build complete: dist\YouTubeLeadTracker.exe
