import os
import re
from typing import Dict, List, Optional

import requests
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth


SPOTIFY_SCOPE = "playlist-modify-public playlist-modify-private"


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def get_spotify_client() -> spotipy.Spotify:
    load_dotenv()

    client_id = _required_env("SPOTIPY_CLIENT_ID")
    client_secret = _required_env("SPOTIPY_CLIENT_SECRET")
    redirect_uri = _required_env("SPOTIPY_REDIRECT_URI")

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=SPOTIFY_SCOPE,
        open_browser=True,
        cache_path=".cache",
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _to_track_metadata(track: Dict) -> Dict[str, str]:
    artists = ", ".join(artist["name"] for artist in track.get("artists", []))
    return {
        "uri": track["uri"],
        "title": track.get("name", ""),
        "artist": artists,
        "album": track.get("album", {}).get("name", ""),
    }


def search_tracks(
    sp: spotipy.Spotify, query: str, artist: Optional[str] = None, limit: int = 10
) -> List[Dict[str, str]]:
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Search query is empty.")

    q = cleaned
    if artist and artist.strip():
        q = f"track:{cleaned} artist:{artist.strip()}"

    response = sp.search(q=q, type="track", limit=limit)
    items = response.get("tracks", {}).get("items", [])
    if not items:
        raise LookupError(f"No track found for query: {query}")

    query_norm = _normalize(cleaned)
    artist_norm = _normalize(artist or "")

    def score(track: Dict) -> tuple:
        title = track.get("name", "")
        title_norm = _normalize(title)
        artists_norm = " ".join(_normalize(a["name"]) for a in track.get("artists", []))
        popularity = int(track.get("popularity", 0))

        is_exact = 1 if title_norm == query_norm else 0
        starts_with = 1 if title_norm.startswith(query_norm) else 0
        contains = 1 if query_norm and query_norm in title_norm else 0
        artist_match = 1 if artist_norm and artist_norm in artists_norm else 0
        length_gap = -abs(len(title_norm) - len(query_norm))

        return (is_exact, artist_match, starts_with, contains, length_gap, popularity)

    ranked = sorted(items, key=score, reverse=True)
    return [_to_track_metadata(track) for track in ranked]


def search_track(
    sp: spotipy.Spotify, query: str, artist: Optional[str] = None
) -> Dict[str, str]:
    ranked = search_tracks(sp, query, artist=artist, limit=10)
    track = ranked[0]

    return track


def add_track_to_playlist(
    sp: spotipy.Spotify, track_uri: str, playlist_id: str
) -> None:
    if not track_uri.strip():
        raise ValueError("Track URI is empty.")
    if not playlist_id.strip():
        raise ValueError("Playlist ID is empty.")

    # Spotify Dev Mode (Feb/Mar 2026 migration) uses /items for playlist writes.
    token = sp.auth_manager.get_access_token(as_dict=False)
    response = requests.post(
        f"https://api.spotify.com/v1/playlists/{playlist_id}/items",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"uris": [track_uri]},
        timeout=20,
    )
    if response.status_code >= 400:
        raise spotipy.SpotifyException(
            response.status_code,
            -1,
            response.text,
            headers=response.headers,
        )
