import os
import json
import csv
import time
import re
from typing import Optional, Union, Iterator, Dict, List
from collections import namedtuple
from dataclasses import dataclass, field
from ytmusicapi import YTMusic

import logging

from .auth import get_ytmusic
from .state import StateManager, RateLimiter

logger = logging.getLogger(__name__)

SongInfo = namedtuple("SongInfo", ["title", "artist", "album"])

@dataclass
class ResearchDetails:
    query: Optional[str] = field(default=None)
    songs: Optional[List[Dict]] = field(default=None)
    suggestions: Optional[List[str]] = field(default=None)

def csv_to_json(csv_dir: str, output_file: str = "playlists.json") -> None:
    """Reads CSVs from csv_dir and converts them to the expected playlists.json format"""
    playlists_data = {"playlists": []}

    if not os.path.exists(csv_dir):
        raise ValueError(f"CSV directory {csv_dir} does not exist.")

    csv_files = [f for f in os.listdir(csv_dir) if f.endswith('.csv')]
    csv_files.sort()

    for csv_file in csv_files:
        pl_name = os.path.splitext(csv_file)[0]
        csv_path = os.path.join(csv_dir, csv_file)

        # We need a predictable ID for each playlist. Just using the filename.
        pl_id = csv_file

        tracks = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    print(f"Skipping {csv_file}: No headers found.")
                    continue

                # Try to handle slightly different column names
                track_col = 'Track Name' if 'Track Name' in reader.fieldnames else None
                artist_col = 'Artist Name(s)' if 'Artist Name(s)' in reader.fieldnames else 'Artist Name' if 'Artist Name' in reader.fieldnames else None
                album_col = 'Album Name' if 'Album Name' in reader.fieldnames else None

                if not track_col or not artist_col:
                    print(f"Skipping {csv_file}: Missing 'Track Name' or 'Artist Name(s)' columns.")
                    continue

                for row in reader:
                    track_name = row.get(track_col, "").strip()
                    artist_name = row.get(artist_col, "").strip()
                    album_name = row.get(album_col, "").strip() if album_col else ""

                    if not track_name or not artist_name:
                        continue

                    tracks.append({
                        "track": {
                            "name": track_name,
                            "artists": [{"name": artist_name}],
                            "album": {"name": album_name}
                        }
                    })

            playlists_data["playlists"].append({
                "id": pl_id,
                "name": pl_name,
                "tracks": tracks
            })
            print(f"Loaded {len(tracks)} tracks from {csv_file}")

        except Exception as e:
            print(f"Error reading {csv_file}: {e}")

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(playlists_data, f, indent=4)

    print(f"Successfully wrote {len(playlists_data['playlists'])} playlists to {output_file}")


def lookup_song(
    yt: YTMusic,
    track_name: str,
    artist_name: str,
    album_name: str,
    yt_search_algo: int,
    details: Optional[ResearchDetails] = None,
) -> dict:
    """Look up a song on YTMusic

    Given the Spotify track information, it does a lookup for the album by the same
    artist on YTMusic, then looks at the first 3 hits looking for a track with exactly
    the same name. In the event that it can't find that exact track, it then does
    a search of songs for the track name by the same artist and simply returns the
    first hit.

    The idea is that finding the album and artist and then looking for the exact track
    match will be more likely to be accurate than searching for the song and artist and
    relying on the YTMusic yt_search_algorithm to figure things out, especially for short tracks
    that might have many contradictory hits like "Survival by Yes".

    Args:
        `yt` (YTMusic)
        `track_name` (str): The name of the researched track
        `artist_name` (str): The name of the researched track's artist
        `album_name` (str): The name of the researched track's album
        `yt_search_algo` (int): 0 for exact matching, 1 for extended matching (search past 1st result), 2 for approximate matching (search in videos)
        `details` (ResearchDetails): If specified, more information about the search and the response will be populated for use by the caller.

    Raises:
        ValueError: If no track is found, it returns an error

    Returns:
        dict: The infos of the researched song
    """
    albums = yt.search(query=f"{album_name} by {artist_name}", filter="albums")
    for album in albums[:3]:
        # print(album)
        # print(f"ALBUM: {album['browseId']} - {album['title']} - {album['artists'][0]['name']}")

        try:
            for track in yt.get_album(album["browseId"])["tracks"]:
                if track["title"] == track_name:
                    return track
            # print(f"{track['videoId']} - {track['title']} - {track['artists'][0]['name']}")
        except Exception as e:
            logger.warning("Unable to lookup album (%s), continuing...", e)

    query = f"{track_name} by {artist_name}"
    if details:
        details.query = query
        details.suggestions = yt.get_search_suggestions(query=query)
    songs = yt.search(query=query, filter="songs")

    match yt_search_algo:
        case 0:
            if details:
                details.songs = songs
            return songs[0]

        case 1:
            for song in songs:
                if (
                    song["title"] == track_name
                    and song["artists"][0]["name"] == artist_name
                    and song["album"]["name"] == album_name
                ):
                    return song
                # print(f"SONG: {song['videoId']} - {song['title']} - {song['artists'][0]['name']} - {song['album']['name']}")

            raise ValueError(
                f"Did not find {track_name} by {artist_name} from {album_name}"
            )

        case 2:
            #  This would need to do fuzzy matching
            for song in songs:
                # Remove everything in brackets in the song title
                song_title_without_brackets = re.sub(r"[\[(].*?[])]", "", song["title"])
                if (
                    (
                        song_title_without_brackets == track_name
                        and song["album"]["name"] == album_name
                    )
                    or (song_title_without_brackets == track_name)
                    or (song_title_without_brackets in track_name)
                    or (track_name in song_title_without_brackets)
                ) and (
                    song["artists"][0]["name"] == artist_name
                    or artist_name in song["artists"][0]["name"]
                ):
                    return song

            # Finds approximate match
            # This tries to find a song anyway. Works when the song is not released as a music but a video.
            else:
                track_name = track_name.lower()
                first_song_title = songs[0]["title"].lower()
                if (
                    track_name not in first_song_title
                    or songs[0]["artists"][0]["name"] != artist_name
                ):  # If the first song is not the one we are looking for
                    logger.debug("Not found in songs, searching videos")
                    new_songs = yt.search(
                        query=f"{track_name} by {artist_name}", filter="videos"
                    )  # Search videos

                    # From here, we search for videos reposting the song. They often contain the name of it and the artist. Like with 'Nekfeu - Ecrire'.
                    for new_song in new_songs:
                        new_song_title = new_song[
                            "title"
                        ].lower()  # People sometimes mess up the capitalization in the title
                        if (
                            track_name in new_song_title
                            and artist_name in new_song_title
                        ) or (track_name in new_song_title):
                            logger.debug("Found a video match for track")
                            return new_song
                    else:
                        # Basically we only get here if the song isn't present anywhere on YouTube
                        raise ValueError(
                            f"Did not find {track_name} by {artist_name} from {album_name}"
                        )
                else:
                    return songs[0]

def _is_likely_mismatch(src: SongInfo, dst_track: dict) -> bool:
    """Heuristic: does the YTMusic result look wrong for the source track?"""
    def normalize(s: str) -> str:
        return re.sub(r"[^\w\s]", "", s.lower()).strip()

    dst_title = normalize(dst_track.get("title", ""))
    src_title = normalize(src.title)

    dst_artists = dst_track.get("artists", [])
    dst_artist = normalize(dst_artists[0]["name"]) if dst_artists else ""
    src_artist = normalize(src.artist)

    title_match = src_title in dst_title or dst_title in src_title
    artist_match = src_artist in dst_artist or dst_artist in src_artist

    return not title_match or not artist_match

def load_playlists_json(filename: str = "playlists.json", encoding: str = "utf-8"):
    """Load the `playlists.json` playlist file"""
    try:
        return json.load(open(filename, "r", encoding=encoding))
    except FileNotFoundError:
        raise FileNotFoundError(f"File {filename} not found. Did you run 'load-csv' first?")

def iter_spotify_playlist(
    src_pl_id: Optional[str] = None,
    spotify_playlist_file: str = "playlists.json",
    spotify_encoding: str = "utf-8",
    reverse_playlist: bool = True,
) -> Iterator[SongInfo]:
    """Songs from a specific playlist"""
    spotify_pls = load_playlists_json(spotify_playlist_file, spotify_encoding)

    def find_spotify_playlist(spotify_pls: Dict, src_pl_id: Union[str, None]) -> Dict:
        """Return the playlist that matches the `src_pl_id`."""
        for src_pl in spotify_pls["playlists"]:
            if src_pl_id is not None and str(src_pl.get("id")) == src_pl_id:
                return src_pl
        raise ValueError(f"Could not find playlist {src_pl_id}")

    src_pl = find_spotify_playlist(spotify_pls, src_pl_id)
    src_pl_name = src_pl["name"]

    print(f"== Source Playlist: {src_pl_name}")

    pl_tracks = src_pl["tracks"]
    if reverse_playlist:
        pl_tracks = reversed(pl_tracks)

    for src_track in pl_tracks:
        if src_track["track"] is None:
            logger.warning("Track seems to be malformed, skipping: %r", src_track)
            continue

        try:
            src_album_name = src_track["track"].get("album", {}).get("name", "")
            src_track_artist = src_track["track"]["artists"][0]["name"]
        except (TypeError, KeyError, IndexError) as e:
            logger.error("Track is malformed: %r", src_track)
            continue
        src_track_name = src_track["track"]["name"]

        yield SongInfo(src_track_name, src_track_artist, src_album_name)

def _ytmusic_create_playlist(
    yt: YTMusic, title: str, description: str, privacy_status: str = "PRIVATE"
) -> str:
    """Wrapper on ytmusic.create_playlist with backoff retries"""
    exception_sleep = 5
    for _ in range(10):
        try:
            id = yt.create_playlist(
                title=title, description=description, privacy_status=privacy_status
            )
            time.sleep(1) # Wait to avoid missing playlist ID error
            return id
        except Exception as e:
            logger.warning("Retrying create_playlist '%s': %s (in %ds)", title, e, exception_sleep)
            time.sleep(exception_sleep)
            exception_sleep *= 2

    raise ValueError(f"Could not create playlist '{title}' after multiple retries")

def get_playlist_id_by_name(yt: YTMusic, title: str) -> Optional[str]:
    """Look up a YTMusic playlist ID by name."""
    try:
        playlists = yt.get_library_playlists(limit=5000)
    except KeyError as e:
        logger.error("Playlist lookup by name failed for '%s': %s", title, e)
        return None

    for pl in playlists:
        if pl["title"] == title:
            return pl["playlistId"]

    return None

def write_unmatched_track(playlist_name, track_name, artist_name, reason="Not Found"):
    unmatched_file = 'unmatched_tracks.csv'
    file_exists = os.path.exists(unmatched_file)
    with open(unmatched_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['Timestamp', 'Playlist Name', 'Track Name', 'Artist Name', 'Reason'])
        writer.writerow([
            time.strftime("%Y-%m-%dT%H:%M:%S"),
            playlist_name,
            track_name,
            artist_name,
            reason
        ])

def copier(
    src_tracks: Iterator[SongInfo],
    dst_pl_id: Optional[str] = None,
    dry_run: bool = False,
    track_sleep: float = 0.1,
    yt_search_algo: int = 0,
    *,
    yt: Optional[YTMusic] = None,
    csv_file_id: Optional[str] = None,
    playlist_name: Optional[str] = None
) -> Dict:
    """
    Copies tracks to YTMusic, saving state per-row so it can resume.
    Returns a dict with keys: added, errors, duplicates, skipped.
    """
    if yt is None:
        yt = get_ytmusic()

    state_manager = StateManager()
    rate_limiter = RateLimiter(track_sleep=track_sleep)

    if dst_pl_id is not None:
        try:
            yt_pl = yt.get_playlist(playlistId=dst_pl_id)
        except Exception as e:
            logger.error("Unable to find YTMusic playlist %s: %s", dst_pl_id, e)
            raise ValueError(f"Invalid YTMusic playlist {dst_pl_id}")
        logger.info("== Youtube Playlist: %s", yt_pl['title'])
        if not playlist_name:
            playlist_name = yt_pl['title']

    tracks_added_set = set()
    duplicate_count = 0
    error_count = 0

    current_row = state_manager.get('current_row', 0)

    # Check if we should even process this
    completed_csvs = state_manager.get('completed_csvs', [])
    if csv_file_id and csv_file_id in completed_csvs:
        logger.info("Skipping %s — already completed.", csv_file_id)
        return {"added": 0, "errors": 0, "duplicates": 0, "skipped": True}

    if csv_file_id:
        state_manager.set('current_csv', csv_file_id)
        state_manager.save()

    for index, src_track in enumerate(src_tracks):
        if index < current_row:
            continue

        logger.info("Source: %s - %s - %s", src_track.title, src_track.artist, src_track.album)

        try:
            dst_track = lookup_song(
                yt, src_track.title, src_track.artist, src_track.album, yt_search_algo
            )
        except Exception as e:
            logger.error("Lookup failed for '%s' by '%s': %s", src_track.title, src_track.artist, e)
            write_unmatched_track(playlist_name or "Unknown", src_track.title, src_track.artist, reason=str(e))
            error_count += 1

            # Still advance state
            current_row = index + 1
            state_manager.set('current_row', current_row)
            state_manager.save()
            continue

        yt_artist_name = "<Unknown>"
        if "artists" in dst_track and len(dst_track["artists"]) > 0:
            yt_artist_name = dst_track["artists"][0]["name"]
        logger.info("  Match: %s - %s", dst_track['title'], yt_artist_name)

        if _is_likely_mismatch(src_track, dst_track):
            logger.warning(
                "Possible mismatch — Source: '%s' by '%s' | Matched: '%s' by '%s'",
                src_track.title, src_track.artist,
                dst_track['title'], yt_artist_name
            )
            write_unmatched_track(
                playlist_name or "Unknown",
                src_track.title,
                src_track.artist,
                reason=f"POSSIBLE_MISMATCH — matched '{dst_track['title']}' by '{yt_artist_name}'"
            )

        if dst_track["videoId"] in tracks_added_set:
            logger.warning("Duplicate videoId skipped: %s", dst_track["videoId"])
            duplicate_count += 1
            write_unmatched_track(
                playlist_name or "Unknown",
                src_track.title,
                src_track.artist,
                reason=f"DUPLICATE (videoId: {dst_track['videoId']})"
            )
        tracks_added_set.add(dst_track["videoId"])

        if not dry_run:
            exception_sleep = 5
            for _ in range(10):
                try:
                    if dst_pl_id is not None:
                        yt.add_playlist_items(
                            playlistId=dst_pl_id,
                            videoIds=[dst_track["videoId"]],
                            duplicates=False,
                        )
                    else:
                        yt.rate_song(dst_track["videoId"], "LIKE")
                    break
                except Exception as e:
                    logger.warning("Retrying add_playlist_items for %s: %s (in %ds)", dst_pl_id, e, exception_sleep)
                    time.sleep(exception_sleep)
                    exception_sleep *= 2

        # Rate limit / track sleep
        rate_limiter.apply_sleep()

        # Save progress
        current_row = index + 1
        state_manager.set('current_row', current_row)
        state_manager.save()

    results = {
        "added": len(tracks_added_set),
        "duplicates": duplicate_count,
        "errors": error_count,
        "skipped": False,
    }

    print()
    print(
        f"Added {results['added']} tracks, encountered {results['duplicates']} duplicates, {results['errors']} errors"
    )

    if csv_file_id:
        completed_csvs.append(csv_file_id)
        state_manager.set('completed_csvs', completed_csvs)
        state_manager.set('current_csv', None)
        state_manager.set('current_row', 0)
        state_manager.save()

    return results

def copy_playlist(
    spotify_playlist_id: str,
    ytmusic_playlist_id: Optional[str] = None,
    spotify_playlists_encoding: str = "utf-8",
    dry_run: bool = False,
    track_sleep: float = 0.1,
    yt_search_algo: int = 0,
    reverse_playlist: bool = True,
    privacy_status: str = "PRIVATE",
    yt: Optional[YTMusic] = None
):
    """
    Copy a playlist by ID to a YTMusic playlist
    """
    print("Using search algo n°: ", yt_search_algo)
    if yt is None:
        yt = get_ytmusic()
    pl_name: str = ""

    if ytmusic_playlist_id and ytmusic_playlist_id.startswith("+"):
        pl_name = ytmusic_playlist_id[1:]
        ytmusic_playlist_id = get_playlist_id_by_name(yt, pl_name)
        print(f"Looking up playlist '{pl_name}': id={ytmusic_playlist_id}")

    if ytmusic_playlist_id is None:
        print("No YouTube playlist ID provided, creating playlist...")
        spotify_pls: dict = load_playlists_json()
        for pl in spotify_pls["playlists"]:
            if pl["id"] == spotify_playlist_id:
                pl_name = pl["name"]

        if not pl_name:
            pl_name = f"Imported Playlist {spotify_playlist_id}"

        ytmusic_playlist_id = _ytmusic_create_playlist(
            yt,
            title=pl_name,
            description="Imported from CSV",
            privacy_status=privacy_status,
        )

        print(f"NOTE: Created playlist '{pl_name}' with ID: {ytmusic_playlist_id}")

    copier(
        iter_spotify_playlist(
            spotify_playlist_id,
            spotify_encoding=spotify_playlists_encoding,
            reverse_playlist=reverse_playlist,
        ),
        ytmusic_playlist_id,
        dry_run,
        track_sleep,
        yt_search_algo,
        yt=yt,
        csv_file_id=spotify_playlist_id,
        playlist_name=pl_name
    )

def copy_all_playlists(
    track_sleep: float = 0.1,
    dry_run: bool = False,
    spotify_playlists_encoding: str = "utf-8",
    yt_search_algo: int = 0,
    reverse_playlist: bool = True,
    privacy_status: str = "PRIVATE",
    yt: Optional[YTMusic] = None
):
    """
    Copy all playlists to YTMusic playlists
    """
    spotify_pls = load_playlists_json()
    if yt is None:
        yt = get_ytmusic()
    state_manager = StateManager()

    for src_pl in spotify_pls["playlists"]:
        pl_name = src_pl["name"]
        pl_id = src_pl["id"]

        # Check state: if completed, skip
        completed_csvs = state_manager.get('completed_csvs', [])
        current_csv = state_manager.get('current_csv')

        if pl_id in completed_csvs:
            print(f"Playlist '{pl_name}' already copied in previous run. Skipping.")
            continue

        if current_csv and current_csv != pl_id:
            # We are mid-run on another playlist, we should skip others until we get to it.
            print(f"Skipping '{pl_name}' as we need to resume '{current_csv}' first.")
            continue

        if pl_name == "":
            pl_name = f"Unnamed Playlist {src_pl['id']}"

        dst_pl_id = get_playlist_id_by_name(yt, pl_name)
        print(f"Looking up playlist '{pl_name}': id={dst_pl_id}")
        if dst_pl_id is None:
            if dry_run:
                print(f"Dry-run: Would create playlist '{pl_name}'")
                dst_pl_id = "DRY_RUN_ID"
            else:
                dst_pl_id = _ytmusic_create_playlist(
                    yt, title=pl_name, description="Imported from CSV", privacy_status=privacy_status
                )
                print(f"NOTE: Created playlist '{pl_name}' with ID: {dst_pl_id}")

        copier(
            iter_spotify_playlist(
                src_pl["id"],
                spotify_encoding=spotify_playlists_encoding,
                reverse_playlist=reverse_playlist,
            ),
            dst_pl_id,
            dry_run,
            track_sleep,
            yt_search_algo,
            yt=yt,
            csv_file_id=pl_id,
            playlist_name=pl_name
        )
        print("\nPlaylist done!\n")

    print("All done!")
