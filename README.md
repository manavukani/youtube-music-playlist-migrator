# YTMusic Playlist Migrator

Automate the process of replicating your Spotify (or other) playlists to your YouTube Music account using `ytmusicapi`.

It reads *CSV files* exported from your source account (containing "Track Name" and "Artist Name(s)") and intelligently searches YouTube Music to find the corresponding song for each track, then adds it to a newly created YouTube Music playlist.

## Features

- **Automated YouTube Music Playlists:** Creates private YouTube Music playlists named after each CSV file.
- **Intelligent Search:** Searches for `{Track Name} {Artist Name(s)}` in YouTube Music's song catalog.
- **Exponential Backoff:** If YouTube Music's unofficial API rate limits you, it gracefully waits and retries.
- **State Resumption:** If the script fails or encounters manual interruption, it saves its state to `state.json`. You can re-run it later, and it will pick up *exactly* where it left off (down to the specific row in the CSV) without duplicating playlists or songs.
- **Graceful Error Handling:** If a track cannot be found on YouTube Music, it logs the details to `unmatched_tracks.csv` and continues.

## Setup Instructions

### 1. Prerequisites
- Python 3.7+ installed.

### 2. Install Dependencies (Using venv is recommended)
```bash
python -m venv myvenv
source myvenv/bin/activate  # On Windows: myvenv\Scripts\activate
pip install -r requirements.txt
```

### 3. Get YouTube Music Credentials
To use the `ytmusicapi`, you need to generate valid credentials via browser headers:

1. **Log in to YouTube Music**: Open YouTube Music in Firefox/Chrome and ensure you are logged in.
2. **Open the Inspection Tool**: Press `F12` or right-click and select _Inspect_ to open the browser's inspection tool.
3. **Access the Network Tab**: Navigate to the Network tab and filter by `/browse` or `/next`.
4. **Select a Request**: Click one of the requests under the filtered results and locate the _Request Headers_ section.
5. **Copy Headers**: Find the "Cookie" and other request headers, and save them in the format specified by `ytmusicapi`. You can use the `ytmusicapi oauth` command, or write them directly to `headers_auth.json`.

Run this interactive setup script from `ytmusicapi` to create `headers_auth.json`:
```bash
ytmusicapi browser
```
*(Follow the prompts to paste your raw headers and generate the file)*

### 4. Configure Environment Variables
1. Create a `.env` file in the root directory.
2. Add the path to your folder containing the Playlist CSVs:
   ```env
   CSV_FOLDER=/path/to/your/csvs
   ```
   **Note:** Ensure your CSV files have the columns exactly named: `Track Name` and `Artist Name(s)`.

## Usage

Run the script:

```bash
python playlist_migrator.py
```

### Resuming
If the script fails due to an API timeout or internet interruption, simply run `python playlist_migrator.py` again. It will automatically read `state.json` and resume the migration seamlessly.

## Output Files
- **`state.json`**: Tracks the internal state. Do not edit this manually unless you want to reset the script's progress.
- **`headers_auth.json`**: Your authenticated request headers (cookies, etc). Keep this file secure.
- **`unmatched_tracks.csv`**: A list of any songs that could not be found on YouTube Music, allowing you to manually add them later if desired.


## Tips for Creating the CSV of Spotify Playlists

### Easiest no-code options

- **Exportify (free web app)**: Log in with Spotify, select playlists, and export them as CSV files that include track name, artist, album, duration, added date, etc. [exportify](https://exportify.net)
- **Soundiiz / TuneMyMusic**: Connect your Spotify account, pick a playlist, then choose “export as file” (CSV/TXT/JSON/XML, etc.). [soundiiz](https://soundiiz.com/blog/export-download-your-spotify-playlists-to-text-or-csv/)
- **Browser extensions**: Chrome extensions like “Spotify Scraper – Export Playlists & More” can scrape playlist data and download it in various formats without extra setup. [chromewebstore.google](https://chromewebstore.google.com/detail/spotify-scraper-export-pl/khgafgeeamiogcfgjknmjomangdamhmn)

These are great if you just want spreadsheets of your playlists without coding.

### Using the Spotify Web API (for coding)

If you’re comfortable with code, you can get very detailed metadata via the official API:

- Use the **Get Playlist** and **Get Playlist Items** endpoints to fetch tracks and fields you care about (track name, ID, artists, album, popularity, etc.). [developer.spotify](https://developer.spotify.com/documentation/web-api/reference/get-playlist)
- Libraries like **Spotipy** (Python) simplify this; you authenticate, call the playlist endpoint, loop over `tracks.items`, and then write everything to CSV. [stackoverflow](https://stackoverflow.com/questions/50490231/get-artist-names-only-from-spotify-web-apis-get-a-playlists-tracks-endpoint)
- No-code “API wrappers” like Stevesie provide a UI over the same endpoints and output directly to CSV while handling pagination for large playlists. [stevesie](https://stevesie.com/apps/spotify-api)