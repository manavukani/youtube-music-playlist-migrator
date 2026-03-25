# Playlist Migrator

A tool to migrate Spotify (or other) playlists from CSV exports to YouTube Music using `ytmusicapi`. Supports a full CLI and a Streamlit web UI with a job queue for managing transfers.

---

## Features

- **CSV → YouTube Music**: Reads CSV exports (containing `Track Name` and `Artist Name(s)`) and migrates them as playlists to your YTMusic account
- **Intelligent Track Matching**: Three search algorithms — exact, extended, and approximate — with fallback to video search
- **Job Queue UI**: Submit individual playlist transfers via the web UI; jobs run sequentially in the background so you can queue multiple without doing them one-by-one or all-at-once
- **State Resumption**: Progress is saved to `state.json` after every track — if the process is interrupted, re-running picks up exactly where it left off
- **Mismatch & Error Tracking**: Failed lookups, duplicates, and suspicious matches are logged to `unmatched_tracks.csv` for manual review
- **Dry Run Mode**: Test any transfer without writing changes to YTMusic

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/manavukani/yt-playlist-from-csv.git
cd yt-playlist-from-csv
```

### 2. Create a virtual environment and install dependencies

**Windows:**
```bash
python -m venv myvenv
myvenv\Scripts\activate
pip install -r requirements.txt
```

**Linux / Mac:**
```bash
python3 -m venv myvenv
source myvenv/bin/activate
pip install -r requirements.txt
```

---

## Authentication (via Request Headers)

1. Open YouTube Music in **Chrome/Firefox** and make sure you're logged in
2. Press `F12` to open DevTools → go to the **Network** tab → filter by `/browse`
3. Click any request → right-click → **Copy > Copy as cURL**
4. Paste the copied content into `request_headers.txt` in the project root
5. Run:

```bash
python -m playlistmigrator generate-creds
```

This generates `creds.json` from your session headers. You can also specify custom paths:

```bash
python -m playlistmigrator generate-creds --input my_headers.txt --output my_creds.json
```

Alternatively, you could also use the *Advanced Setup via request headers* in the Streamlit UI.

> ⚠️ **Security warning**: `request_headers.txt` and `creds.json` contain your session tokens. Never commit these files to Git. They are already listed in `.gitignore`.

---

## Preparing Your CSV Files

Each CSV file represents one playlist. Place all CSVs in a folder (eg `./mycsv/`). 

> Set folder path for `CSV_FOLDER` in `.env`

Required columns (exact names):
- `Track Name`
- `Artist Name(s)`

Optional column:
- `Album Name`

The playlist name in YTMusic will be taken from the CSV filename (without extension).

### How to export your Spotify playlists as CSV

**Via the Spotify Web API (for developers):**
Use the [Get Playlist Items](https://developer.spotify.com/documentation/web-api/reference/get-playlist) endpoint or the [Spotipy](https://spotipy.readthedocs.io) Python library to fetch tracks and write them to CSV.

**No-code options:**
- [Exportify](https://exportify.net) — log in with Spotify, select playlists, export as CSV
- [Soundiiz / TuneMyMusic](https://soundiiz.com) — connect Spotify and export as CSV/TXT/JSON
- [Spotify Scraper Chrome Extension](https://chromewebstore.google.com/detail/spotify-scraper-export-pl/khgafgeeamiogcfgjknmjomangdamhmn) — scrape playlists directly from the browser

---

## Using the CLI
 
All commands follow the pattern:
 
```bash
python -m playlistmigrator [command] <arguments>
```
 
### `generate-creds`
Generate `creds.json` from a request headers file (supports raw headers or pasted cURL commands).
```bash
python -m playlistmigrator generate-creds
```
 
### `load-csv`
Convert a folder of CSV files into `playlists.json` (required before any transfer).
```bash
python -m playlistmigrator load-csv --csv-dir ./csvs --output playlists.json
```
 
| Argument | Default | Description |
|---|---|---|
| `--csv-dir` | CSV_FOLDER (in `.env`) | Path to the folder containing your CSV files |
| `--output` | `playlists.json` | Output file path |
 
### `list-playlists`
Show all source playlists from `playlists.json` and all playlists in your YTMusic library side by side.
```bash
python -m playlistmigrator list-playlists
```
 
### `copy-playlist`
Copy a single source playlist to YTMusic.
```bash
python -m playlistmigrator copy-playlist <playlist_id> [options]
```
 
| Argument | Default | Description |
|---|---|---|
| `playlist_id` | *(required)* | ID from `playlists.json` (the CSV filename, e.g. `my_playlist.csv`) |
| `--yt-id` | auto-create | Target YTMusic playlist ID, or `+Playlist Name` to look up by name |
| `--dry-run` | off | Preview the transfer without making any changes |
| `--track-sleep` | `0.1` | Seconds to wait between tracks (increase if hitting rate limits) |
| `--algo` | `0` | Search algorithm: `0`=exact, `1`=extended, `2`=approximate |
| `--privacy` | `PRIVATE` | Playlist privacy: `PRIVATE`, `PUBLIC`, or `UNLISTED` |
 
**Examples:**
```bash
# Copy to a new auto-created playlist
python -m playlistmigrator copy-playlist my_playlist.csv
 
# Copy into an existing YTMusic playlist by ID
python -m playlistmigrator copy-playlist my_playlist.csv --yt-id PLxxxxxxxxxxxxxx
 
# Dry run with approximate matching
python -m playlistmigrator copy-playlist my_playlist.csv --dry-run --algo 2
```
 
### `copy-all`
Copy every playlist in `playlists.json` to YTMusic, skipping any already completed.
```bash
python -m playlistmigrator copy-all [options]
```
 
Accepts the same options as `copy-playlist` (except `playlist_id` and `--yt-id`).
 
### `status`
Show the current contents of `state.json` — what's completed, what's in progress, and the current row.
```bash
python -m playlistmigrator status
```
 
### `reset`
Delete `state.json` to start fresh. Does not affect anything already written to YTMusic.
```bash
python -m playlistmigrator reset
```
 
---
 
## Search Algorithms
 
| Algo | Flag | Behaviour | Best for |
|---|---|---|---|
| Exact | `--algo 0` | Searches by album+artist first, falls back to first song result | Fast, works well for popular music |
| Extended | `--algo 1` | Requires title, artist, and album all to match exactly | High accuracy, may miss more tracks |
| Approximate | `--algo 2` | Fuzzy title/artist matching, falls back to video search | Obscure tracks, non-English titles, remixes |
 
---
 
## Using the UI
 
The Streamlit UI provides a browser-based interface for all CLI features, plus a job queue for managing multiple transfers.
 
### Start the UI
 
```bash
streamlit run ui/app.py
```
 
### UI Pages
 
**🔐 Auth** — Check credential status, run OAuth setup, or generate credentials from request headers.
 
**📂 Load CSV** — Select a CSV folder, preview detected playlists and track counts, then convert to `playlists.json`.
 
**📋 Playlists** — Browse and search your source playlists (from `playlists.json`) and your YTMusic library side by side. Inspect the full track list of any playlist.
 
**🎵 Transfer Queue** — The core UI feature:
- Select a source playlist and a target YTMusic playlist (or auto-create)
- Configure algorithm, dry run, privacy, and track sleep
- Hit **Add to Queue and Execute** — if a transfer is already running, the job is queued and starts automatically when the current one finishes
- Live progress bar, track counter, and scrolling log for the running job
- Cancel pending jobs or clear finished ones at any time
 
**🔧 Status & Diagnostics** — View raw `state.json`, see the per-playlist results history (tracks added / errors / duplicates), browse or download `unmatched_tracks.csv`, and reset state.
 
---
 
## Important Files
 
| File | Purpose |
|---|---|
| `creds.json` | YTMusic OAuth credentials — keep secure, **do not commit** |
| `request_headers.txt` | Raw session headers for header-based auth — keep secure, **do not commit** |
| `playlists.json` | Converted playlist data generated by `load-csv` |
| `state.json` | Migration progress — tracks current playlist, current row, completed playlists, and per-run results |
| `unmatched_tracks.csv` | All failed lookups, duplicates, and suspicious matches with timestamps |
 
---
 
## Troubleshooting
 
**`ERROR: No file 'creds.json' exists`** — Run `python -m playlistmigrator generate-creds` (header-based). See the Authentication section above.
 
**`File playlists.json not found`** — Run `python -m playlistmigrator load-csv --csv-dir ./csvs` first.
 
**Many unmatched tracks** — Try a higher algorithm: `--algo 1` or `--algo 2`. Approximate mode (`2`) also searches videos, which helps for obscure or non-English tracks.
 
**Transfer interrupted mid-run** — Just re-run the same command or re-add the playlist to the UI queue. `state.json` tracks progress down to the individual track row and the run will resume automatically.
 
**UI queue lost after restarting Streamlit** — The queue lives in browser session memory. Completed transfers are permanently recorded in `state.json`, so no work is lost — you just need to re-add any unfinished jobs to the queue.