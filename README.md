# Spotify to YouTube Playlist Migrator

This script automates the process of replicating your Spotify playlists on your YouTube account using the YouTube Data API v3.

It reads CSV files exported from your Spotify account (containing "Track Name" and "Artist Name(s)") and intelligently searches YouTube to find the corresponding "official audio" for each track, then adds it to a newly created YouTube playlist.

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

### 2. Install Dependencies
```bash
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
2. Add the path to your folder containing the Spotify CSVs:
   ```env
   SPOTIFY_CSV_FOLDER=/path/to/your/spotify/csvs
   ```
   **Note:** Ensure your CSV files have the columns exactly named: `Track Name` and `Artist Name(s)`.

## Usage

Run the script:

```bash
python spotify_to_youtube.py
```

### First Run (Authentication)
The first time you run the script, it will open a browser window asking you to log into your Google/YouTube account and grant the application permissions.
Once granted, it will save a `token.json` file locally so you don't have to log in every time.

### Subsequent Runs
If the script hits the 10,000 unit daily quota limit, it will log a warning and exit.
Wait until the next day (when your quota resets), and simply run `python spotify_to_youtube.py` again. It will automatically read `state.json` and resume the migration seamlessly.

## Output Files
- **`state.json`**: Tracks the internal state and quota usage. Do not edit this manually unless you want to reset the script's progress.
- **`token.json`**: Your cached OAuth 2.0 credentials. Keep this file secure.
- **`unmatched_tracks.csv`**: A list of any songs that could not be found on YouTube, allowing you to manually add them later if desired.