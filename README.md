# YouTube Lead Tracker

Given a YouTube channel (URL, `@handle`, or a bulk-pasted list of many), this
app automatically populates a lead-tracking row equivalent to a manual
"Ultimate Lead Tracker" spreadsheet: date, language, channel name/link,
subscriber count, average views per video, contact info, and a fit
assessment — so outbound lead research doesn't require manually opening each
channel. It ships as a single standalone Windows application (one `.exe`, no
install, no terminal) so it can be handed to someone else and just work. On
macOS, `run_mac.command` gives the same "hand it to someone else" experience
without a Windows binary (see below).

## Running in development

```
pip install -r requirements-dev.txt
pytest
python main.py
```

`pytest` runs the full test suite. `python main.py` starts the dev server on
a free local port and opens it in your default browser.

## Building the standalone exe

```
build.bat
```

The packaged app is written to `dist\YouTubeLeadTracker.exe`.

## Running on macOS

PyInstaller can't cross-compile — a Mac binary has to be built *on* a Mac.
Two options, from a folder containing this project:

- **One-click run, no build (recommended for most people):** double-click
  `run_mac.command` in Finder. First run creates a local Python environment
  and installs dependencies (a few seconds, one time only); every run after
  that just starts the app and opens your browser to it. Requires Python 3
  (macOS prompts to install it automatically if it's missing, or get it from
  [python.org](https://www.python.org/downloads/)). If Gatekeeper blocks it
  as "from an unidentified developer," right-click the file → Open → Open,
  once.
- **Build a native binary:** run `./build.sh` in Terminal (same idea as
  `build.bat`, just for macOS/Linux). Output goes to
  `dist/YouTubeLeadTracker`.

## API keys (optional)

The app works out of the box with zero configuration: it scrapes channel
pages directly and scores fit with a rule-based heuristic. For more accurate
stats and AI-written fit verdicts, add either of these in the app's Settings
panel:

- A free **YouTube Data API v3** key (Google Cloud Console — no billing
  account needed for the free daily quota) for exact subscriber/view counts.
- A free **Groq** API key (no credit card) for LLM-written fit assessments.

Both are optional; the app falls back to scrape-only data and rule-based
scoring if either is missing or a call fails.

## Where data lives

Leads and settings are stored in a local SQLite file, `leads.db`, created
automatically on first run next to `main.py` in development or next to the
`.exe` in the packaged build.

## Design docs

Built via the plan at
`docs/superpowers/plans/2026-09-11-youtube-lead-tracker.md` and the spec at
`docs/superpowers/specs/2026-09-11-youtube-lead-tracker-design.md` — see
those for the full design rationale.
