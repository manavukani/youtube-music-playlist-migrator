import os
import sys
import json
from argparse import ArgumentParser

from . import backend
from . import auth as auth_module
from . import state

def auth():
    """
    Runs ytmusicapi OAuth setup
    """
    def parse_arguments():
        parser = ArgumentParser(description="Runs ytmusicapi OAuth setup")
        return parser.parse_args()
    parse_arguments()
    auth_module.setup_oauth()

def load_csv():
    """
    Converts --csv-dir folder -> playlists.json
    """
    def parse_arguments():
        parser = ArgumentParser(description="Converts CSV files in a directory to playlists.json")
        default_csv_dir = os.environ.get("CSV_FOLDER")
        parser.add_argument(
            "--csv-dir",
            default=default_csv_dir,
            required=default_csv_dir is None,
            help="Directory containing CSV files (default: $CSV_FOLDER)"
        )
        parser.add_argument("--output", default="playlists.json", help="Output JSON file")
        return parser.parse_args()
    args = parse_arguments()
    backend.csv_to_json(args.csv_dir, args.output)

def list_playlists():
    """
    Lists Spotify playlists from JSON + YTMusic playlists
    """
    def parse_arguments():
        parser = ArgumentParser(description="Lists playlists from playlists.json and YTMusic")
        return parser.parse_args()
    parse_arguments()

    yt = auth_module.get_ytmusic()

    try:
        spotify_pls = backend.load_playlists_json()
        print("== Source Playlists (from JSON)")
        for src_pl in spotify_pls.get("playlists", []):
            print(f"{src_pl.get('id')} - {src_pl.get('name', ''):50} ({len(src_pl.get('tracks', []))} tracks)")
    except FileNotFoundError:
        print("== Source Playlists (from JSON)\nNot found. Run load-csv first.")

    print()
    print("== YTMusic Playlists")
    try:
        for pl in yt.get_library_playlists(limit=5000):
            print(f"{pl.get('playlistId')} - {pl.get('title', ''):40} ({pl.get('count', '?')} tracks)")
    except Exception as e:
        print(f"Error fetching YTMusic playlists: {e}")

def copy_playlist():
    """
    Copies one playlist by ID
    """
    def parse_arguments():
        parser = ArgumentParser(description="Copies one playlist by ID")
        parser.add_argument("playlist_id", help="ID of the source playlist from playlists.json (e.g., file name)")
        parser.add_argument("--yt-id", default=None, help="YTMusic playlist ID or +Name")
        parser.add_argument("--dry-run", action="store_true", help="Don't write any changes")
        parser.add_argument("--track-sleep", type=float, default=0.1, help="Sleep between tracks (default 0.1s)")
        parser.add_argument("--algo", type=int, default=0, help="Search algorithm (0=exact, 1=extended, 2=approximate)")
        parser.add_argument("--privacy", default="PRIVATE", help="Privacy for new playlists (PRIVATE/PUBLIC/UNLISTED)")
        return parser.parse_args()
    args = parse_arguments()
    yt = auth_module.get_ytmusic()
    backend.copy_playlist(
        args.playlist_id,
        ytmusic_playlist_id=args.yt_id,
        dry_run=args.dry_run,
        track_sleep=args.track_sleep,
        yt_search_algo=args.algo,
        privacy_status=args.privacy,
        yt=yt
    )

def copy_all():
    """
    Copies all playlists
    """
    def parse_arguments():
        parser = ArgumentParser(description="Copies all playlists")
        parser.add_argument("--dry-run", action="store_true", help="Don't write any changes")
        parser.add_argument("--track-sleep", type=float, default=0.1, help="Sleep between tracks (default 0.1s)")
        parser.add_argument("--algo", type=int, default=0, help="Search algorithm (0=exact, 1=extended, 2=approximate)")
        parser.add_argument("--privacy", default="PRIVATE", help="Privacy for new playlists (PRIVATE/PUBLIC/UNLISTED)")
        return parser.parse_args()
    args = parse_arguments()
    yt = auth_module.get_ytmusic()
    backend.copy_all_playlists(
        track_sleep=args.track_sleep,
        dry_run=args.dry_run,
        yt_search_algo=args.algo,
        privacy_status=args.privacy,
        yt=yt
    )

def status():
    """
    Shows current state.json
    """
    def parse_arguments():
        parser = ArgumentParser(description="Shows current migration state")
        return parser.parse_args()
    parse_arguments()

    st = state.StateManager()
    print("Current State:")
    print(json.dumps(st.state, indent=4))

def reset():
    """
    Clears state.json to start fresh
    """
    def parse_arguments():
        parser = ArgumentParser(description="Clears migration state")
        return parser.parse_args()
    parse_arguments()

    if os.path.exists('state.json'):
        os.remove('state.json')
        print("Reset state.json.")
    else:
        print("No state.json found.")
