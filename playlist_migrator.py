import os
import json
import logging
import datetime
import time
import pandas as pd
from dotenv import load_dotenv
from ytmusicapi import YTMusic

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class StateManager:
    def __init__(self, state_file='state.json'):
        self.state_file = state_file
        self.state = self.load()

    def load(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            'last_run_date': None,
            'quota_usage': 0,
            'current_csv': None,
            'current_row': 0,
            'completed_csvs': [],
            'playlist_mapping': {}
        }

    def save(self):
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=4)

    def get(self, key, default=None):
        return self.state.get(key, default)

    def set(self, key, value):
        self.state[key] = value


def authenticate():
    if not os.path.exists('headers_auth.json'):
        logger.error("headers_auth.json not found. Please provide it to authenticate with YTMusic.")
        return None
    try:
        ytmusic = YTMusic("headers_auth.json")
        return ytmusic
    except Exception as e:
        logger.error(f"Failed to authenticate with ytmusicapi: {e}")
        return None

def process_csvs():
    load_dotenv()
    csv_folder = os.getenv('CSV_FOLDER')
    if not csv_folder or not os.path.isdir(csv_folder):
        logger.error("CSV_FOLDER environment variable not set or invalid directory.")
        return

    ytmusic = authenticate()
    if not ytmusic:
        return

    state_manager = StateManager()

    unmatched_file = 'unmatched_tracks.csv'
    if not os.path.exists(unmatched_file):
        pd.DataFrame(columns=['Playlist Name', 'Track Name', 'Artist Name']).to_csv(unmatched_file, index=False)

    csv_files = [f for f in os.listdir(csv_folder) if f.endswith('.csv')]
    csv_files.sort()

    completed_csvs = state_manager.get('completed_csvs', [])
    current_csv = state_manager.get('current_csv')
    current_row = state_manager.get('current_row', 0)
    playlist_mapping = state_manager.get('playlist_mapping', {})

    try:
        for csv_file in csv_files:
            if csv_file in completed_csvs:
                continue

            if current_csv and csv_file != current_csv:
                continue

            state_manager.set('current_csv', csv_file)
            state_manager.save()

            playlist_name = os.path.splitext(csv_file)[0]
            csv_path = os.path.join(csv_folder, csv_file)

            try:
                df = pd.read_csv(csv_path)
            except Exception as e:
                logger.error(f"Error reading {csv_file}: {e}")
                state_manager.set('current_csv', None)
                state_manager.set('current_row', 0)
                state_manager.save()
                current_csv = None
                continue

            if 'Track Name' not in df.columns or 'Artist Name(s)' not in df.columns:
                logger.error(f"CSV {csv_file} is missing required columns. Skipping.")
                state_manager.set('current_csv', None)
                state_manager.set('current_row', 0)
                state_manager.save()
                current_csv = None
                continue

            playlist_id = playlist_mapping.get(playlist_name)

            if not playlist_id:
                logger.info(f"Creating playlist: {playlist_name}")
                try:
                    playlist_id = ytmusic.create_playlist(
                        title=playlist_name,
                        description="Imported using github.com/manavukani/yt-playlist-from-csv",
                        privacy_status="PRIVATE"
                    )

                    if type(playlist_id) is dict:
                        # Sometimes create_playlist returns a dict instead of string id
                        playlist_id = playlist_id.get('id') or playlist_id

                    playlist_mapping[playlist_name] = playlist_id
                    state_manager.set('playlist_mapping', playlist_mapping)
                    state_manager.save()
                    time.sleep(1) # Sleep to avoid rate limits
                except Exception as e:
                    logger.error(f"Failed to create playlist {playlist_name}: {e}")
                    continue

            for index, row in df.iterrows():
                if index < current_row:
                    continue

                track_name = row['Track Name']
                artist_name = row['Artist Name(s)']
                query = f'{track_name} {artist_name}'

                logger.info(f"Searching for: {query}")

                try:
                    search_results = ytmusic.search(query=query, filter="songs", limit=1)

                    if not search_results:
                        logger.warning(f"No results found for: {query}")
                        unmatched_df = pd.DataFrame([{
                            'Playlist Name': playlist_name,
                            'Track Name': track_name,
                            'Artist Name': artist_name
                        }])
                        unmatched_df.to_csv(unmatched_file, mode='a', header=False, index=False)
                    else:
                        video_id = search_results[0]['videoId']

                        if not video_id:
                             logger.warning(f"No video ID found for search result: {query}")
                             continue

                        logger.info(f"Adding video {video_id} to playlist {playlist_name}")

                        max_retries = 3
                        base_delay = 2
                        for attempt in range(max_retries):
                            try:
                                ytmusic.add_playlist_items(playlist_id, [video_id])
                                break # success
                            except Exception as e:
                                if attempt == max_retries - 1:
                                    logger.error(f"Failed to add item after {max_retries} attempts: {e}")
                                    raise
                                delay = base_delay * (2 ** attempt)
                                logger.warning(f"Error adding track. Retrying in {delay} seconds... ({e})")
                                time.sleep(delay)

                    current_row = index + 1
                    state_manager.set('current_row', current_row)
                    state_manager.save()

                    # Be nice to the API
                    time.sleep(1)

                except Exception as e:
                    logger.exception(f"Unexpected error processing track {track_name}: {e}")
                    # Log the failed track and continue
                    unmatched_df = pd.DataFrame([{
                        'Playlist Name': playlist_name,
                        'Track Name': track_name,
                        'Artist Name': artist_name,
                        'Reason': str(e)
                    }])
                    unmatched_df.to_csv(unmatched_file, mode='a', header=False, index=False)

                    # Still increment current row to move past failing tracks
                    current_row = index + 1
                    state_manager.set('current_row', current_row)
                    state_manager.save()

                    # Sleep longer on error before continuing
                    time.sleep(3)


            completed_csvs.append(csv_file)
            state_manager.set('completed_csvs', completed_csvs)
            state_manager.set('current_csv', None)
            state_manager.set('current_row', 0)
            current_csv = None
            current_row = 0
            state_manager.save()
            logger.info(f"Finished processing {csv_file}")

        logger.info("All CSVs processed successfully!")

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    process_csvs()
