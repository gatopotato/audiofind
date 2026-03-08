import argparse
import os
import sys

from dotenv import load_dotenv
from spotipy.exceptions import SpotifyException

from core.spotify import get_spotify_client
from detectors.gemini_detector import detect_metadata_from_image_with_gemini
from detectors.ocr_detector import (
    detect_metadata_from_image,
    metadata_to_query,
    query_candidates_from_metadata,
)
from inputs.image import is_image_path
from inputs.text import get_text_query
from core.spotify import add_track_to_playlist, search_tracks


def _metadata_is_weak(metadata: dict) -> bool:
    title = metadata.get("title", "").strip()
    artist = metadata.get("artist", "").strip()
    if len(title) < 3:
        return True

    # Very noisy OCR fields usually contain few letters and many symbols/digits.
    def letter_ratio(value: str) -> float:
        if not value:
            return 0.0
        letters = sum(ch.isalpha() for ch in value)
        return letters / max(len(value), 1)

    if letter_ratio(title) < 0.5:
        return True
    if artist and letter_ratio(artist) < 0.35:
        return True
    return False


def _search_with_attempts(sp, attempts):
    ranked_tracks = []
    tried = set()
    for q, a in attempts:
        key = (q.strip().lower(), a.strip().lower())
        if not q.strip() or key in tried:
            continue
        tried.add(key)
        try:
            ranked_tracks = search_tracks(sp, q, artist=a, limit=10)
            if ranked_tracks:
                break
        except LookupError:
            continue
    return ranked_tracks


def _print_track(prefix: str, metadata: dict) -> None:
    print(prefix)
    print(f"Title : {metadata['title']}")
    print(f"Artist: {metadata['artist']}")
    print(f"Album : {metadata['album']}")


def _pick_from_top5(ranked_tracks):
    print("Top 5 matches:")
    top5 = ranked_tracks[:5]
    for idx, candidate in enumerate(top5, start=1):
        print(f"{idx}. {candidate['title']} - {candidate['artist']} ({candidate['album']})")
    choice = input("Pick a number to add, or press Enter to cancel: ").strip()
    if not choice:
        return None
    if not choice.isdigit():
        print("Invalid choice. No song added.")
        return None
    picked = int(choice)
    if picked < 1 or picked > len(top5):
        print("Choice out of range. No song added.")
        return None
    return top5[picked - 1]


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
    parser = argparse.ArgumentParser(description="audiofinder phase 1-2")
    parser.add_argument(
        "input_value",
        nargs="*",
        help="Song query text or image path",
    )
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
    parser.add_argument(
        "--no-gemini",
        action="store_true",
        help="Disable Gemini fallback for image input",
    )
    args = parser.parse_args()
    load_dotenv()

    raw_input = " ".join(args.input_value).strip()
    input_is_image = bool(raw_input) and is_image_path(raw_input)
    gemini_enabled = input_is_image and (not args.no_gemini)
    image_metadata = {"title": "", "artist": "", "album": ""}

    if input_is_image:
        try:
            image_metadata = detect_metadata_from_image(raw_input)
        except Exception as exc:
            print(f"OCR failed: {exc}")
            image_metadata = {"title": "", "artist": "", "album": ""}

        print("Detected from image:")
        print(f"Title : {image_metadata.get('title', '')}")
        print(f"Artist: {image_metadata.get('artist', '')}")
        print(f"Album : {image_metadata.get('album', '')}")

        if gemini_enabled and _metadata_is_weak(image_metadata):
            try:
                gemini_metadata = detect_metadata_from_image_with_gemini(raw_input)
                if gemini_metadata.get("title", "").strip():
                    image_metadata = gemini_metadata
                    print("Gemini refinement:")
                    print(f"Title : {image_metadata.get('title', '')}")
                    print(f"Artist: {image_metadata.get('artist', '')}")
                    print(f"Album : {image_metadata.get('album', '')}")
            except Exception as exc:
                print(f"Gemini fallback skipped: {exc}")

        query = metadata_to_query(image_metadata)
        if not query:
            query = input("Could not infer a song. Enter song text manually: ").strip()
    else:
        query = get_text_query(args.input_value)

    if not query:
        print("No query provided.")
        return 1

    playlist_id = (args.playlist_id or os.getenv("SPOTIFY_PLAYLIST_ID", "")).strip()
    if not playlist_id:
        print("Missing playlist ID. Set SPOTIFY_PLAYLIST_ID or pass --playlist-id.")
        return 1

    try:
        sp = get_spotify_client()
        artist_hint = args.artist.strip()

        attempts = []
        if input_is_image:
            for candidate in query_candidates_from_metadata(image_metadata):
                attempts.append((candidate, artist_hint))
                attempts.append((candidate, ""))
            attempts.append((query, artist_hint))
        else:
            attempts.append((query, artist_hint))

        ranked_tracks = _search_with_attempts(sp, attempts)

        if not ranked_tracks and gemini_enabled:
            try:
                gemini_metadata = detect_metadata_from_image_with_gemini(raw_input)
                gemini_attempts = []
                for candidate in query_candidates_from_metadata(gemini_metadata):
                    gemini_attempts.append((candidate, artist_hint))
                    gemini_attempts.append((candidate, ""))
                ranked_tracks = _search_with_attempts(sp, gemini_attempts)
                if ranked_tracks:
                    image_metadata = gemini_metadata
                    print("Using Gemini-derived metadata for search fallback.")
            except Exception as exc:
                print(f"Gemini fallback skipped: {exc}")

        if not ranked_tracks:
            manual = input(
                "Could not find a match from OCR. Enter song text manually: "
            ).strip()
            if not manual:
                print("No query provided. No song added.")
                return 1
            ranked_tracks = search_tracks(sp, manual, artist="", limit=10)

        track = ranked_tracks[0]
        metadata = {
            "title": track["title"],
            "artist": track["artist"],
            "album": track["album"],
        }

        if not args.yes:
            _print_track("Found match:", metadata)
            confirm = input("Add this song to playlist? [y/N]: ").strip().lower()
            if confirm not in {"y", "yes"}:
                if input_is_image:
                    print("Choose next step:")
                    print("1. Show top 5 OCR matches")
                    if gemini_enabled:
                        print("2. Try Gemini refinement")
                    action = input("Enter 1, 2, or press Enter to cancel: ").strip()
                    if not action:
                        print("Cancelled. No song added.")
                        return 0
                    if action == "2" and gemini_enabled:
                        try:
                            gemini_metadata = detect_metadata_from_image_with_gemini(raw_input)
                            gemini_attempts = []
                            for candidate in query_candidates_from_metadata(gemini_metadata):
                                gemini_attempts.append((candidate, artist_hint))
                                gemini_attempts.append((candidate, ""))
                            gemini_ranked = _search_with_attempts(sp, gemini_attempts)
                            if not gemini_ranked:
                                print("Gemini ran but no Spotify matches were found.")
                                print("Cancelled. No song added.")
                                return 0
                            track = gemini_ranked[0]
                            metadata = {
                                "title": track["title"],
                                "artist": track["artist"],
                                "album": track["album"],
                            }
                            _print_track("Gemini match:", metadata)
                            gemini_confirm = input(
                                "Add this Gemini result to playlist? [y/N]: "
                            ).strip().lower()
                            if gemini_confirm in {"y", "yes"}:
                                pass
                            else:
                                picked_track = _pick_from_top5(gemini_ranked)
                                if not picked_track:
                                    print("Cancelled. No song added.")
                                    return 0
                                track = picked_track
                                metadata = {
                                    "title": track["title"],
                                    "artist": track["artist"],
                                    "album": track["album"],
                                }
                        except Exception as exc:
                            print(f"Gemini fallback skipped: {exc}")
                            print("Cancelled. No song added.")
                            return 0
                    elif action == "1":
                        picked_track = _pick_from_top5(ranked_tracks)
                        if not picked_track:
                            print("Cancelled. No song added.")
                            return 0
                        track = picked_track
                        metadata = {
                            "title": track["title"],
                            "artist": track["artist"],
                            "album": track["album"],
                        }
                    else:
                        print("Invalid choice. No song added.")
                        return 1
                else:
                    picked_track = _pick_from_top5(ranked_tracks)
                    if not picked_track:
                        print("Cancelled. No song added.")
                        return 0
                    track = picked_track
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
