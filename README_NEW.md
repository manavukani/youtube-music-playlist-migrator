# Playlist Migrator

A command-line tool to migrate Spotify (or other) playlists from CSV to YouTube Music using `ytmusicapi`.

# Installation

#### 1. Clone the repo and generate Virtual Env:

To Clone:

```bash
git clone https://github.com/manavukani/yt-playlist-from-csv.git
cd yt-playlist-from-csv
```

On Windows:

```bash
python -m venv myvenv
myvenv\Scripts\activate
pip install -r requirements.txt
```

On Linux or Mac:

```bash
python3 -m venv myvenv
source myvenv/bin/activate
pip install -r requirements.txt
```

#### 2. Generate Auth From Headers

To use the YouTube Music API, you need to generate valid credentials. Follow these steps:

1. **Log in to YouTube Music**: Open YouTube Music in Firefox and ensure you are logged in.
2. **Open the Inspection Tool**: Press `F12` or right-click and select _Inspect_ to open the browser's inspection tool.
3. **Access the Network Tab**: Navigate to the Network tab and filter by `/browse`.
4. **Select a Request**: Click one of the requests under the filtered results.
5. **Copy Headers**: Right-click, choose _Copy > Copy as cURL_
6. **Paste into `request_headers.txt`**: Open the `request_headers.txt` file located in the main directory of this project and paste the copied content into it.

> CAUTION: This involves using your active session headers. These headers contain your "Master Key" (Cookies and Auth tokens). DO NOT commit request_headers.txt or auth.json to GitHub.

Run the script: `python playlistmigrator\creds_generator.py`

---

## Next Steps

Once your credentials are set up, use the CLI commands below to migrate your playlists. The tables document every available command and function.

### CLI Commands (`cli.py`)

These are the entry-point commands you run directly.

| Command | CLI Usage | Description | Key Options |
|---------|-----------|-------------|-------------|
| `auth` | `playlist-auth` | Runs `ytmusicapi` OAuth setup to generate `auth.json` | None |
| `load_csv` | `playlist-load-csv --csv-dir <dir>` | Converts all `.csv` files in a directory into `playlists.json` | `--csv-dir` (required), `--output` (default `playlists.json`) |
| `list_playlists` | `playlist-list` | Lists all source playlists from `playlists.json` and your YTMusic library playlists | None |
| `copy_playlist` | `playlist-copy <playlist_id>` | Copies a single playlist (by its ID from `playlists.json`) to YTMusic | `--yt-id`, `--dry-run`, `--track-sleep`, `--algo` (0/1/2), `--privacy` |
| `copy_all` | `playlist-copy-all` | Copies **all** playlists from `playlists.json` to YTMusic, resuming from state | `--dry-run`, `--track-sleep`, `--algo` (0/1/2), `--privacy` |
| `status` | `playlist-status` | Prints the current migration state from `state.json` | None |
| `reset` | `playlist-reset` | Deletes `state.json` so you can start a fresh migration | None |

### Typical Workflow

```
1. playlist-auth              # One-time OAuth setup
2. playlist-load-csv --csv-dir ./my_csvs   # Convert CSVs to JSON
3. playlist-list              # Verify loaded playlists
4. playlist-copy-all          # Migrate everything (or use playlist-copy for one)
5. playlist-status            # Check progress / resume if interrupted
6. playlist-reset             # Clear state when done or to re-run
```

### Backend Functions (`backend.py`)

Core logic for searching, matching, and copying tracks.

| Function | Signature | Description |
|----------|-----------|-------------|
| `csv_to_json` | `csv_to_json(csv_dir, output_file="playlists.json")` | Reads all `.csv` files from `csv_dir`, maps columns (`Track Name`, `Artist Name(s)`, `Album Name`), and writes `playlists.json`. |
| `load_playlists_json` | `load_playlists_json(filename="playlists.json", encoding="utf-8")` | Loads and returns the parsed `playlists.json` file. Raises `FileNotFoundError` if missing. |
| `iter_spotify_playlist` | `iter_spotify_playlist(src_pl_id, spotify_playlist_file, spotify_encoding, reverse_playlist)` | Yields `SongInfo(title, artist, album)` tuples for every track in the specified playlist. |
| `lookup_song` | `lookup_song(yt, track_name, artist_name, album_name, yt_search_algo, details)` | Searches YTMusic for a matching track. First tries album lookup, then falls back to song/video search depending on `yt_search_algo` (0=exact, 1=extended, 2=approximate). |
| `get_playlist_id_by_name` | `get_playlist_id_by_name(yt, title)` | Scans your YTMusic library for a playlist matching `title` and returns its ID (or `None`). |
| `_ytmusic_create_playlist` | `_ytmusic_create_playlist(yt, title, description, privacy_status)` | Creates a new YTMusic playlist with exponential-backoff retries (up to 10 attempts). |
| `write_unmatched_track` | `write_unmatched_track(playlist_name, track_name, artist_name, reason)` | Appends a failed track lookup to `unmatched_tracks.csv` for later review. |
| `copier` | `copier(src_tracks, dst_pl_id, dry_run, track_sleep, yt_search_algo, *, yt, csv_file_id, playlist_name)` | Main copy loop — looks up each source track, adds it to the YTMusic playlist, saves progress to `state.json` after every track so it can resume on interruption. |
| `copy_playlist` | `copy_playlist(spotify_playlist_id, ytmusic_playlist_id, ..., yt)` | Orchestrates copying a single playlist: resolves or creates the destination playlist, then delegates to `copier`. |
| `copy_all_playlists` | `copy_all_playlists(track_sleep, dry_run, ..., yt)` | Iterates every playlist in `playlists.json`, skips already-completed ones (via state), creates destination playlists as needed, and copies each. |

### State Management (`state.py`)

Tracks migration progress so interrupted runs can resume.

| Class / Method | Signature | Description |
|----------------|-----------|-------------|
| `StateManager` | `StateManager(state_file="state.json")` | Loads (or initializes) migration state from disk. Default keys: `current_csv`, `current_row`, `completed_csvs`, `playlist_mapping`. |
| `StateManager.load` | `load()` | Reads `state.json` from disk; returns default state dict if the file doesn't exist. |
| `StateManager.save` | `save()` | Writes the current in-memory state to `state.json`. |
| `StateManager.get` | `get(key, default=None)` | Returns the value for `key`, or `default` if not set. |
| `StateManager.set` | `set(key, value)` | Updates `key` in the in-memory state (call `save()` to persist). |
| `RateLimiter` | `RateLimiter(track_sleep=0.1)` | Simple sleep-based rate limiter to avoid hitting YouTube API rate limits. |
| `RateLimiter.apply_sleep` | `apply_sleep()` | Sleeps for `track_sleep` seconds (skipped if ≤ 0). |
| `RateLimiter.reset` | `reset()` | No-op placeholder kept for forward compatibility. |

### Search Algorithm Reference

The `--algo` flag controls how tracks are matched on YTMusic:

| Value | Name | Behavior |
|-------|------|----------|
| `0` | Exact | Searches album first, then returns the first song result. Fast but may mis-match on ambiguous titles. |
| `1` | Extended | Searches album first, then iterates all song results requiring an exact match on title + artist + album. Raises an error if nothing matches. |
| `2` | Approximate | Tries fuzzy matching (strips brackets, partial title match). Falls back to video search if no song match is found. Best for obscure or non-standard releases. |
