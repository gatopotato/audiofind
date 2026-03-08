# audiofinder (Phase 1-2)

Supported inputs:

- text query -> Spotify track search -> add to playlist
- image path -> OCR -> Spotify track search -> add to playlist
- image path -> OCR + optional Gemini refinement -> Spotify track search -> add

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
- `GEMINI_API_KEY` (optional, for `--use-gemini`)
- `GEMINI_MODEL` (optional, defaults to `gemini-2.0-flash`)

4. Install Tesseract OCR engine (required for image input):

- Windows: install "Tesseract OCR" and ensure `tesseract.exe` is in your PATH.
- Verify with:

```bash
tesseract --version
```

## Run

Interactive:

```bash
python main.py
```

Direct query:

```bash
python main.py after hours the weeknd
```

Image input:

```bash
python main.py "C:\\path\\to\\image.png"
```

Image input with Gemini fallback (default behavior):

```bash
python main.py "C:\\path\\to\\image.png"
```

Disable Gemini fallback:

```bash
python main.py "C:\\path\\to\\image.png" --no-gemini
```

Optional artist hint:

```bash
python main.py sojourn --artist joji
```

Override playlist id:

```bash
python main.py blinding lights --playlist-id <playlist_id>
```
