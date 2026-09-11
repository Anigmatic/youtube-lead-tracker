# YouTube Lead Tracker — Design Spec

Date: 2026-09-11
Status: Approved for implementation

## Purpose

Given a YouTube channel (URL, `@handle`, or bulk-pasted list of many), automatically
populate a lead-tracking row equivalent to the user's existing "Ultimate Lead Tracker"
spreadsheet: date, language, channel name/link, subscriber count, average views per
video, contact info, and a fit assessment — so outbound lead research doesn't require
manually opening each channel.

Delivered as a single standalone Windows application (one `.exe`, no install, no
terminal) so it can be handed to someone else and just work.

## Non-goals

- Not a full CRM — Status/Outreach Method/Notes are simple editable fields, not
  workflow automation.
- Not a mass-scraping tool — designed for the pace of manual lead research (tens to
  low hundreds of channels per session), not bulk harvesting.
- No YouTube login/OAuth — only public data.

## Architecture

- **Backend:** Python, Flask app served by `waitress` (a production WSGI server that
  packages reliably under PyInstaller, unlike `uvicorn`/asyncio servers).
- **Frontend:** one self-contained HTML/JS page served by the backend — input panel,
  results table, settings panel. No separate frontend build step/framework.
- **Storage:** local SQLite database file (`leads.db`) created next to the executable
  on first run. Every scrape appends/updates rows; the tracker persists across runs.
- **Launch:** the `.exe` starts the Flask server on `localhost:<port>` (auto-picks a
  free port) and opens the user's default browser to it via Python's `webbrowser`
  module. Closing the window/console stops the server.
- **Packaging:** `PyInstaller --onefile`, built on Windows, producing a single
  `.exe` artifact for distribution.

## Data sources (hybrid: YouTube Data API + scraping)

The YouTube Data API v3 is free (Google Cloud API key, no billing account required
for the free daily quota of 10,000 units/day — comfortably enough for this tool's
scale) and is far more reliable than scraping for numeric stats. It does **not**
expose a channel's public/business contact email, so scraping is still needed for
contact info.

**Resolution order per channel:**

1. **If a YouTube Data API key is configured** (Settings panel, optional):
   - `channels.list` (`part=snippet,statistics`) resolves the handle/URL to a
     channel ID and returns exact subscriber count, channel description, and
     thumbnail.
   - `search.list` or `playlistItems.list` (channel's uploads playlist) fetches the
     ~10 most recent video IDs; `videos.list` (`part=statistics`) returns their view
     counts.
   - Quota cost is low (~5-10 units per channel), so the default 10,000/day quota
     covers roughly 1,000+ channel look-ups/day.
2. **Always (regardless of API key):** fetch the channel's public "About" page HTML
   and parse the `ytInitialData` JSON block YouTube server-renders into it (no
   headless browser needed) to extract:
   - Contact info: regex-scan the description and any listed external links for an
     email address or business/booking link. If nothing found, record
     "No clear contact".
   - Fallback subscriber count / description / recent video stats, used **only**
     when no API key is configured (or a specific API call fails/quota is
     exhausted) — same shape of data, subscriber count shown as YouTube displays it
     (e.g. "5.65K") rather than an exact number.
3. Requests are paced with a short delay between channels (bulk mode) to stay well
   clear of anything resembling automated abuse.

**Output fields derived per channel:**
- `name` (display name) + `channel_url` (canonical URL, rendered as a link)
- `subscriber_count` (exact if via API, approximate/as-displayed if via scrape)
- `avg_views_range` — min–max of the ~10 most recent videos' view counts (matches
  the existing sheet's "1.5K–4.1K" style; not a flat average)
- `contact_info` — email or best available contact link, or "No clear contact"
- `language` — best-effort guess from description text (simple heuristic), always
  user-editable after the fact

## Fit assessment

Settings panel lets the user configure:
- Niche keywords (e.g. "AI, SMMA, growth")
- Target subscriber range
- Free-text description of the ideal lead

**Primary: free LLM API (optional key).** If configured, sends the scraped
channel data + the user's criteria to a free-tier LLM (Groq recommended — free, no
credit card, fast) and gets back a verdict (`High` / `Moderate` / `Low` Fit) plus a
one-line reason, in the style of the existing sheet
("High Fit – Consistent uploads and solid niche in AI/SMMA growth."). The LLM
provider/model and API key are configurable in Settings so any of the free options
(Groq, OpenRouter, etc.) can be used.

**Fallback: rule-based scorer**, used automatically when no LLM key is configured
or the LLM call fails:
- Niche keyword match in channel name/description
- Upload recency (active within ~60 days = good signal)
- Subscriber count and view/subscriber ratio within the user's configured target
  range

Combines into the same High/Moderate/Low verdict with a short auto-generated reason
string, so the app is fully usable with zero API keys configured.

## Data model

SQLite table `leads`:

| column | notes |
|---|---|
| id | primary key |
| date | date the row was created |
| language | editable dropdown |
| name | display name |
| channel_url | link target |
| subscriber_count | as text (preserves "5.65K" style or exact number) |
| avg_views_range | text, e.g. "1.5K-4.1K" |
| contact_info | text/link |
| fit_assessment | "High" / "Moderate" / "Low" |
| fit_reason | one-line text |
| status | editable dropdown, values configurable in Settings |
| outreach_method | editable dropdown, values configurable in Settings |
| notes | free text |

## UI

- **Input panel:** single text box accepting one channel URL/handle, or multiple
  pasted lines for bulk mode. Submit kicks off processing with a progress indicator
  per channel.
- **Results table:** sortable, matches the column set above. Status, Outreach
  Method, and Notes are editable in place and saved immediately. Duplicate
  channels (same `channel_url`) update the existing row rather than creating a
  new one.
- **Settings panel:** YouTube Data API key (optional), LLM provider + API key
  (optional), niche keywords, target subscriber range, dropdown option lists for
  Status/Outreach Method.
- **Export:** button to export the current table to `.xlsx` (via `openpyxl`) or
  `.csv`, column layout matching the existing spreadsheet so it can be
  opened/imported directly.

## Error handling

- Unresolvable channel (bad URL/handle, deleted channel): row is added with an
  error note in `contact_info`/`fit_reason` rather than failing the whole batch.
- API quota exhausted or API call fails: silently falls back to scraping for that
  channel.
- LLM call fails/times out: falls back to rule-based scoring for that channel.
- Scrape blocked/unexpected page structure: row recorded with available partial
  data and a "could not fully verify" note; batch continues.

## Testing

- Unit tests for the `ytInitialData` parser and the API-response parser against
  saved fixture HTML/JSON (no live network calls in tests).
- Unit tests for the rule-based fit scorer given synthetic channel stats.
- Integration test for the Flask endpoints (submit channel(s), fetch results,
  edit a row, export) against the SQLite layer using an in-memory/temp DB.
- Manual smoke test against a handful of real public channels before packaging.
- Manual verification of the packaged `.exe` on a clean Windows environment
  (no Python installed) before considering the build done.

## Distribution

- Repo tracked in git (initialized as part of this project's scaffolding).
- Build script (`build.bat` or a `PyInstaller` spec file) produces
  `dist/YouTubeLeadTracker.exe`, the single artifact to hand to another person.
- No API keys are bundled into the build — each recipient enters their own
  (optional) YouTube Data API / LLM key in Settings, stored locally in their own
  `leads.db`/config file next to the exe.
