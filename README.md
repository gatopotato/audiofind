# audiofinder (Phase 1)

Phase 1 supports text input only:

- text query -> Spotify track search -> add to playlist

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill values:

- `SPOTIPY_CLIENT_ID`
- `SPOTIPY_CLIENT_SECRET`
- `SPOTIPY_REDIRECT_URI`
- `SPOTIFY_PLAYLIST_ID`

## Run

Interactive:

```bash
python main.py
```

Direct query:

```bash
python main.py after hours the weeknd
```

Override playlist id:

```bash
python main.py blinding lights --playlist-id <playlist_id>
```
