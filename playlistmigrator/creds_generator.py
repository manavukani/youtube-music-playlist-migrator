import ytmusicapi
from ytmusicapi import YTMusic
import re
import os


def parse_curl_to_raw_headers(curl_text):
    """
    Converts a curl command (including Windows cmd format with ^ escapes)
    into raw HTTP headers that ytmusicapi.setup() can understand.
    """
    # Strip Windows cmd escape characters
    text = curl_text.replace("^\"", "\"").replace("^\\\"", "\"")
    text = text.replace("^%^", "%").replace("^&", "&")
    text = text.replace("^|", "|").replace("^<", "<").replace("^>", ">")
    text = text.replace("^\\'", "'").replace("^ ", " ")
    text = re.sub(r'\^(?=[^\n])', '', text)

    headers = []

    # Extract -H "header: value" pairs
    for match in re.finditer(r'-H\s+"([^"]+)"', text):
        headers.append(match.group(1))

    # Extract -b "cookie_value" and convert to a cookie header
    cookie_match = re.search(r'-b\s+"([^"]+)"', text)
    if cookie_match:
        headers.append(f"cookie: {cookie_match.group(1)}")

    return "\n".join(headers)


def setup_ytmusic_with_request_headers(
    input_file="request_headers.txt", credentials_file="creds.json"
):
    """
    Loads headers from a file (supports raw headers or curl command format)
    and sets up YTMusic connection using ytmusicapi.setup.

    Parameters:
        input_file (str): Path to the file containing headers (raw or curl format).
        credentials_file (str): Path to save the configuration headers (credentials).

    Returns:
        str: Configuration headers string returned by ytmusicapi.setup.
    """
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file {input_file} does not exist.")

    with open(input_file, "r") as file:
        raw_content = file.read()

    # Detect curl command format and convert to raw headers
    if raw_content.strip().startswith("curl"):
        headers_raw = parse_curl_to_raw_headers(raw_content)
    else:
        headers_raw = raw_content

    config_headers = ytmusicapi.setup(
        filepath=credentials_file, headers_raw=headers_raw
    )
    print(f"Configuration headers saved to {credentials_file}")

    verify_credentials(credentials_file)

    return config_headers


def verify_credentials(credentials_file="creds.json"):
    """
    Verifies that the credentials file works by initializing YTMusic
    and fetching library playlists.
    """
    print(f"\nVerifying credentials from {credentials_file}...")
    try:
        yt = YTMusic(credentials_file)
    except Exception as e:
        print(f"FAILED to initialize YTMusic: {e}")
        return False

    print("YTMusic client initialized successfully.")
    print("Fetching your library playlists to verify authentication...\n")

    try:
        playlists = yt.get_library_playlists(limit=5)
    except Exception as e:
        print(f"FAILED to fetch playlists: {e}")
        return False

    if not playlists:
        print("Authenticated, but no playlists found in your library.")
    else:
        print(f"Found {len(playlists)} playlist(s):")
        for pl in playlists:
            count = pl.get("count", "?")
            print(f"  - {pl['title']}  ({count} tracks)")

    print(f"\n{credentials_file} is working correctly.")
    return True


if __name__ == "__main__":
    try:
        # Specify file paths
        request_headers_file = "request_headers.txt"
        credentials_file = "creds.json"

        # Set up YTMusic with raw headers
        print(f"Setting up YTMusic using headers from {request_headers_file}...")
        setup_ytmusic_with_request_headers(
            input_file=request_headers_file, credentials_file=credentials_file
        )

        print("YTMusic setup completed successfully!")

    except Exception as e:
        print(f"An error occurred: {e}")
