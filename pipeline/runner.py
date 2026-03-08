from typing import Dict

import spotipy

from core.spotify import add_track_to_playlist, search_track


def run_text_pipeline(
    sp: spotipy.Spotify, query: str, playlist_id: str
) -> Dict[str, str]:
    track = search_track(sp, query)
    metadata = {
        "title": track["title"],
        "artist": track["artist"],
        "album": track["album"],
    }
    add_track_to_playlist(sp, track["uri"], playlist_id)
    return metadata

