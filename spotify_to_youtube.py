import os
import json
import logging
import datetime
import pandas as pd
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/youtube']

class QuotaExceededError(Exception):
    pass

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

class QuotaTracker:
    DAILY_LIMIT = 10000
    COST_SEARCH = 100
    COST_PLAYLIST_CREATE = 50
    COST_PLAYLIST_INSERT = 50

    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.reset_if_new_day()
        self.current_usage = self.state_manager.get('quota_usage', 0)

    def reset_if_new_day(self):
        last_date = self.state_manager.get('last_run_date')
        today = datetime.date.today().isoformat()
        if last_date != today:
            self.state_manager.set('last_run_date', today)
            self.state_manager.set('quota_usage', 0)
            self.state_manager.save()
            self.current_usage = 0

    def add_usage(self, cost):
        self.reset_if_new_day()
        if self.current_usage + cost >= self.DAILY_LIMIT:
            logger.warning("Approaching daily quota limit. Pausing execution.")
            raise QuotaExceededError("Quota limit reached")

        self.current_usage += cost
        self.state_manager.set('quota_usage', self.current_usage)
        self.state_manager.save()
        logger.info(f"Quota used: {self.current_usage}/{self.DAILY_LIMIT}")

def authenticate():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('client_secrets.json'):
                logger.error("client_secrets.json not found. Please provide it to authenticate.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secrets.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('youtube', 'v3', credentials=creds)

def process_csvs():
    load_dotenv()
    csv_folder = os.getenv('SPOTIFY_CSV_FOLDER')
    if not csv_folder or not os.path.isdir(csv_folder):
        logger.error("SPOTIFY_CSV_FOLDER environment variable not set or invalid directory.")
        return

    youtube = authenticate()
    if not youtube:
        return

    state_manager = StateManager()
    quota_tracker = QuotaTracker(state_manager)

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
                quota_tracker.add_usage(QuotaTracker.COST_PLAYLIST_CREATE)
                logger.info(f"Creating playlist: {playlist_name}")
                request = youtube.playlists().insert(
                    part="snippet,status",
                    body={
                      "snippet": {
                        "title": playlist_name,
                        "description": "Imported from Spotify"
                      },
                      "status": {
                        "privacyStatus": "private"
                      }
                    }
                )
                response = request.execute(num_retries=3)
                playlist_id = response['id']
                playlist_mapping[playlist_name] = playlist_id
                state_manager.set('playlist_mapping', playlist_mapping)
                state_manager.save()

            for index, row in df.iterrows():
                if index < current_row:
                    continue

                track_name = row['Track Name']
                artist_name = row['Artist Name(s)']
                query = f'"{track_name}" "{artist_name}" official audio'

                logger.info(f"Searching for: {query}")

                try:
                    quota_tracker.add_usage(QuotaTracker.COST_SEARCH)

                    search_request = youtube.search().list(
                        part="id",
                        q=query,
                        type="video",
                        maxResults=1
                    )
                    search_response = search_request.execute(num_retries=3)

                    if not search_response.get('items'):
                        logger.warning(f"No results found for: {query}")
                        unmatched_df = pd.DataFrame([{
                            'Playlist Name': playlist_name,
                            'Track Name': track_name,
                            'Artist Name': artist_name
                        }])
                        unmatched_df.to_csv(unmatched_file, mode='a', header=False, index=False)
                    else:
                        video_id = search_response['items'][0]['id']['videoId']

                        logger.info(f"Adding video {video_id} to playlist {playlist_name}")
                        quota_tracker.add_usage(QuotaTracker.COST_PLAYLIST_INSERT)

                        insert_request = youtube.playlistItems().insert(
                            part="snippet",
                            body={
                                "snippet": {
                                    "playlistId": playlist_id,
                                    "resourceId": {
                                        "kind": "youtube#video",
                                        "videoId": video_id
                                    }
                                }
                            }
                        )
                        insert_request.execute(num_retries=3)

                    current_row = index + 1
                    state_manager.set('current_row', current_row)
                    state_manager.save()

                except QuotaExceededError:
                    raise
                except HttpError as e:
                    if hasattr(e, 'resp') and e.resp.status in [403]:
                        raise
                    logger.error(f"HTTP error processing track {track_name}: {e}")
                    # Log the failed track and continue
                    unmatched_df = pd.DataFrame([{
                        'Playlist Name': playlist_name,
                        'Track Name': track_name,
                        'Artist Name': artist_name,
                        'Reason': 'API Error'
                    }])
                    unmatched_df.to_csv(unmatched_file, mode='a', header=False, index=False)

                    # Still increment current row to move past failing tracks
                    current_row = index + 1
                    state_manager.set('current_row', current_row)
                    state_manager.save()
                except Exception as e:
                    logger.exception(f"Unexpected error processing track {track_name}: {e}")
                    # Log the failed track and continue
                    unmatched_df = pd.DataFrame([{
                        'Playlist Name': playlist_name,
                        'Track Name': track_name,
                        'Artist Name': artist_name,
                        'Reason': 'Unexpected Error'
                    }])
                    unmatched_df.to_csv(unmatched_file, mode='a', header=False, index=False)

                    # Still increment current row to move past failing tracks
                    current_row = index + 1
                    state_manager.set('current_row', current_row)
                    state_manager.save()


            completed_csvs.append(csv_file)
            state_manager.set('completed_csvs', completed_csvs)
            state_manager.set('current_csv', None)
            state_manager.set('current_row', 0)
            current_csv = None
            current_row = 0
            state_manager.save()
            logger.info(f"Finished processing {csv_file}")

        logger.info("All CSVs processed successfully!")

    except QuotaExceededError:
        logger.info("Script paused due to quota limits. Run again tomorrow.")
    except HttpError as e:
        logger.error(f"An HTTP error occurred: {e}")
        if hasattr(e, 'resp') and e.resp.status in [403]:
            logger.error("Encountered 403 error. Possibly quota exceeded.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    process_csvs()
