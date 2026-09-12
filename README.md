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

## Downloads (no build required)

Every tagged release automatically builds and attaches a Windows `.exe` and
a macOS binary via GitHub Actions — grab the one for your OS from the
[Releases page](https://github.com/Anigmatic/youtube-lead-tracker/releases)
instead of building from source.

## Running it as a live URL (for yourself, privately)

This app is a **personal, single-user tool** — one SQLite file holds all
leads and any API keys you configure, with no login. Only deploy it to a
URL you keep private; don't share the link, since anyone with it can see
and edit everything (including your Settings/API keys) with no
authentication in front of it.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Anigmatic/youtube-lead-tracker)

That button uses `render.yaml` in this repo to set itself up. A few things
worth knowing about Render's **free** tier specifically:

- The service sleeps after 15 minutes of inactivity and takes ~30-50s to
  wake back up on your next visit. Normal for a personal tool, not built
  for someone waiting on it live.
- Its disk is **ephemeral** — `leads.db` survives while the same instance
  stays up, but a fresh deploy (e.g. you push a code update) or Render
  recycling the instance wipes it. Export your leads (the Export button)
  before pushing updates if you don't want to lose them. If this matters to
  you, look at Render's paid persistent disks, or Fly.io's free persistent
  volume, instead.
- `wsgi.py` is the entrypoint used here (not `main.py`, which is only for
  the local/desktop exe). It reads `LEADS_DB_PATH` from the environment if
  you want the database to live somewhere other than next to `wsgi.py`
  (e.g. a mounted persistent disk).

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
