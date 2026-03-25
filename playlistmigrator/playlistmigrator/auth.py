import sys
import os
import json
import subprocess
from ytmusicapi import YTMusic

def get_ytmusic() -> YTMusic:
    """
    Loads oauth.json and returns an authenticated YTMusic client, exits if missing.
    """
    if not os.path.exists("oauth.json"):
        print("ERROR: No file 'oauth.json' exists in the current directory.")
        print("       Have you logged in to YTMusic?  Run 'playlistmigrator auth' to login")
        sys.exit(1)

    try:
        return YTMusic("oauth.json")
    except json.decoder.JSONDecodeError as e:
        print(f"ERROR: JSON Decode error while trying start YTMusic: {e}")
        print("       This typically means a problem with a 'oauth.json' file.")
        print("       Have you logged in to YTMusic?  Run 'playlistmigrator auth' to login")
        sys.exit(1)

def setup_oauth() -> None:
    """
    Runs `python -m ytmusicapi oauth` to help the user set up OAuth credentials interactively.
    """
    print("Setting up YTMusic OAuth...")
    try:
        # Run ytmusicapi oauth as a subprocess
        subprocess.check_call([sys.executable, "-m", "ytmusicapi", "oauth"])
        print("OAuth setup complete. You can now use the migration tool.")
    except subprocess.CalledProcessError as e:
        print(f"Error during OAuth setup: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred during OAuth setup: {e}")
        sys.exit(1)
