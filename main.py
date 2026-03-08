import argparse
import os
import sys

from dotenv import load_dotenv
from spotipy.exceptions import SpotifyException

from core.spotify import get_spotify_client
from inputs.text import get_text_query
from core.spotify import add_track_to_playlist, search_tracks


def _print_spotify_error(exc: SpotifyException) -> None:
    status = getattr(exc, "http_status", None)
    if status == 403:
        print("Spotify rejected playlist write access (403 Forbidden).")
        print("Check the following:")
        print("1. You are logged into the same Spotify account that owns the playlist.")
        print("2. The playlist ID in .env is correct and writable by that account.")
        print("3. Your OAuth token is fresh (delete .cache and re-run).")
        print("4. Your Spotify account is allowlisted in the app dashboard (dev mode).")
        return

    if status == 401:
        print("Spotify auth failed (401 Unauthorized).")
        print("Delete .cache and re-run to complete OAuth again.")
        return

    print(f"Spotify API error ({status}): {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="audiofinder phase 1")
    parser.add_argument("query", nargs="*", help="Song query text")
    parser.add_argument(
        "--playlist-id",
        default="",
        help="Spotify playlist ID (overrides SPOTIFY_PLAYLIST_ID env var)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt and add first match directly",
    )
    parser.add_argument(
        "--artist",
        default="",
        help="Optional artist name to improve matching",
    )
    args = parser.parse_args()

    query = get_text_query(args.query)
    if not query:
        print("No query provided.")
        return 1

    load_dotenv()
    playlist_id = (args.playlist_id or os.getenv("SPOTIFY_PLAYLIST_ID", "")).strip()
    if not playlist_id:
        print("Missing playlist ID. Set SPOTIFY_PLAYLIST_ID or pass --playlist-id.")
        return 1

    try:
        sp = get_spotify_client()
        artist_hint = args.artist.strip()
        ranked_tracks = search_tracks(sp, query, artist=artist_hint, limit=10)
        track = ranked_tracks[0]
        metadata = {
            "title": track["title"],
            "artist": track["artist"],
            "album": track["album"],
        }

        if not args.yes:
            print("Found match:")
            print(f"Title : {metadata['title']}")
            print(f"Artist: {metadata['artist']}")
            print(f"Album : {metadata['album']}")
            confirm = input("Add this song to playlist? [y/N]: ").strip().lower()
            if confirm not in {"y", "yes"}:
                print("Top 5 matches:")
                top5 = ranked_tracks[:5]
                for idx, candidate in enumerate(top5, start=1):
                    print(
                        f"{idx}. {candidate['title']} - {candidate['artist']} "
                        f"({candidate['album']})"
                    )
                choice = input(
                    "Pick a number to add, or press Enter to cancel: "
                ).strip()
                if not choice:
                    print("Cancelled. No song added.")
                    return 0
                if not choice.isdigit():
                    print("Invalid choice. No song added.")
                    return 1
                picked = int(choice)
                if picked < 1 or picked > len(top5):
                    print("Choice out of range. No song added.")
                    return 1
                track = top5[picked - 1]
                metadata = {
                    "title": track["title"],
                    "artist": track["artist"],
                    "album": track["album"],
                }

        add_track_to_playlist(sp, track["uri"], playlist_id)
    except SpotifyException as exc:
        _print_spotify_error(exc)
        return 1
    except Exception as exc:
        print(f"Failed: {exc}")
        return 1

    print("Added to playlist:")
    print(f"Title : {metadata['title']}")
    print(f"Artist: {metadata['artist']}")
    print(f"Album : {metadata['album']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
