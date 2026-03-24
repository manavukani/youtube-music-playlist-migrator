# YouTube Playlist Migrator

Automate the process of replicating your Spotify (or other) playlists to your YouTube account using the YouTube Data API v3.

It reads *CSV files* exported from your source account (containing "Track Name" and "Artist Name(s)") and intelligently searches YouTube to find the corresponding "official audio" for each track, then adds it to a newly created YouTube playlist.

## Features

- **Automated YouTube Playlists:** Creates private YouTube playlists named after each CSV file.
- **Intelligent Search:** Searches for `{Track Name} {Artist Name(s)} official audio` to avoid live versions or fan covers.
- **Quota Management (Critical):** The YouTube API has a strict 10,000 unit daily limit. This script calculates costs and gracefully pauses execution before exceeding the limit, preventing `403 Quota Exceeded` errors.
- **State Resumption:** If the script pauses due to quota limits or manual interruption, it saves its state to `state.json`. You can re-run it the next day, and it will pick up *exactly* where it left off (down to the specific row in the CSV) without duplicating playlists or songs.
- **Graceful Error Handling:** If a track cannot be found on YouTube, it logs the details to `unmatched_tracks.csv` and continues.

## Setup Instructions

### 1. Prerequisites
- Python 3.7+ installed.
- A Google Cloud Platform (GCP) account.

### 2. Install Dependencies (Using venv is recommended)
```bash
python -m venv myvenv
myvenv\Scripts\activate
pip install -r requirements.txt
```

### 3. Get YouTube API Credentials
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project.
3. Navigate to **APIs & Services** > **Library**, search for "YouTube Data API v3", and enable it for your project.
4. Go to **APIs & Services** > **Credentials**.
5. Click **Create Credentials** > **OAuth client ID**.
6. Set the Application type to **Desktop app** and give it a name.
7. Click **Create**.
8. Download the JSON file for your new credentials and rename it to `client_secrets.json`.
9. Place `client_secrets.json` in the root directory of this project.

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

### First Run (Authentication)
The first time you run the script, it will open a browser window asking you to log into your Google/YouTube account and grant the application permissions.
Once granted, it will save a `token.json` file locally so you don't have to log in every time.

### Subsequent Runs
If the script hits the 10,000 unit daily quota limit, it will log a warning and exit.
Wait until the next day (when your quota resets), and simply run `python playlist_migrator.py` again. It will automatically read `state.json` and resume the migration seamlessly.

## Output Files
- **`state.json`**: Tracks the internal state and quota usage. Do not edit this manually unless you want to reset the script's progress.
- **`token.json`**: Your cached OAuth 2.0 credentials. Keep this file secure.
- **`unmatched_tracks.csv`**: A list of any songs that could not be found on YouTube, allowing you to manually add them later if desired.


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