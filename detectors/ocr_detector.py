import re
from pathlib import Path
from typing import Dict, List

import pytesseract
from PIL import Image
from pytesseract import TesseractNotFoundError


def _configure_tesseract_cmd() -> None:
    if getattr(pytesseract.pytesseract, "tesseract_cmd", ""):
        configured = Path(pytesseract.pytesseract.tesseract_cmd)
        if configured.exists():
            return

    candidates = [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tesseract.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            pytesseract.pytesseract.tesseract_cmd = str(candidate)
            return


def extract_ocr_text(image_path: str) -> str:
    _configure_tesseract_cmd()
    try:
        with Image.open(image_path) as img:
            return pytesseract.image_to_string(img)
    except TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract OCR is not installed. Install Tesseract and ensure it is in PATH."
        ) from exc


def _clean_lines(text: str) -> List[str]:
    lines: List[str] = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if len(line) < 2:
            continue
        if sum(ch.isalnum() for ch in line) < 2:
            continue
        lines.append(line)
    return lines


def _sanitize_field(value: str) -> str:
    cleaned = value
    cleaned = re.sub(r"\b\d{1,2}:\d{2}\b", " ", cleaned)
    cleaned = re.sub(r"\b\d{4}\b", " ", cleaned)
    cleaned = re.sub(r"\b\d[\d,]{2,}\b", " ", cleaned)
    cleaned = re.sub(r"[«»+•|]", " ", cleaned)
    cleaned = re.sub(r"[^A-Za-z0-9\s'&().,-]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_:,")
    return cleaned


def _is_label(line: str) -> bool:
    return line.strip().lower() in {"song", "lyrics", "artist", "album"}


def _has_letters(line: str) -> bool:
    return any(ch.isalpha() for ch in line)


def detect_metadata_from_text(text: str) -> Dict[str, str]:
    lines = [_sanitize_field(line) for line in _clean_lines(text)]
    lines = [line for line in lines if line]
    metadata = {"title": "", "artist": "", "album": ""}
    if not lines:
        return metadata

    # Spotify UI pattern: "Song" label followed by large title line.
    for idx, line in enumerate(lines):
        if line.lower() == "song" and idx + 1 < len(lines):
            next_line = lines[idx + 1]
            if next_line and not _is_label(next_line):
                metadata["title"] = next_line
                break

    # Spotify UI sometimes shows "Artist" label near profile image.
    for idx, line in enumerate(lines):
        if line.lower() == "artist" and idx + 1 < len(lines):
            next_line = lines[idx + 1]
            if next_line and _has_letters(next_line):
                metadata["artist"] = next_line
                break

    # Parse compact meta line: "Artist · Album · 2026 · 2:08 ..."
    for line in lines:
        if "·" in line:
            parts = [_sanitize_field(part) for part in line.split("·")]
            parts = [p for p in parts if p]
            if len(parts) >= 1 and not metadata["artist"] and _has_letters(parts[0]):
                metadata["artist"] = parts[0]
            if len(parts) >= 2 and not metadata["album"] and _has_letters(parts[1]):
                metadata["album"] = parts[1]

    for line in lines:
        dash_match = re.match(r"^(.+?)\s[-|]\s(.+)$", line)
        if dash_match:
            left = _sanitize_field(dash_match.group(1).strip())
            right = _sanitize_field(dash_match.group(2).strip())
            # Ignore noisy numeric tails that OCR reads as artist.
            if left and right and _has_letters(right):
                if not metadata["title"]:
                    metadata["title"] = left
                if not metadata["artist"]:
                    metadata["artist"] = right
                return metadata

        by_match = re.match(r"^(.+?)\s+by\s+(.+)$", line, flags=re.IGNORECASE)
        if by_match:
            if not metadata["title"]:
                metadata["title"] = _sanitize_field(by_match.group(1).strip())
            if not metadata["artist"]:
                metadata["artist"] = _sanitize_field(by_match.group(2).strip())
            return metadata

    candidate_lines = [line for line in lines if not _is_label(line) and _has_letters(line)]
    if not metadata["title"] and candidate_lines:
        metadata["title"] = candidate_lines[0]
    if not metadata["artist"] and len(candidate_lines) > 1:
        metadata["artist"] = candidate_lines[1]
    if not metadata["album"] and len(candidate_lines) > 2:
        metadata["album"] = candidate_lines[2]

    metadata = {k: _sanitize_field(v) for k, v in metadata.items()}
    return metadata


def detect_metadata_from_image(image_path: str) -> Dict[str, str]:
    text = extract_ocr_text(image_path)
    return detect_metadata_from_text(text)


def metadata_to_query(metadata: Dict[str, str]) -> str:
    title = _sanitize_field(metadata.get("title", ""))
    artist = _sanitize_field(metadata.get("artist", ""))
    if title:
        return title
    if title and artist:
        return f"{title} {artist}"
    if artist:
        return artist
    return ""


def query_candidates_from_metadata(metadata: Dict[str, str]) -> List[str]:
    title = _sanitize_field(metadata.get("title", ""))
    artist = _sanitize_field(metadata.get("artist", ""))
    album = _sanitize_field(metadata.get("album", ""))

    candidates: List[str] = []
    if title:
        candidates.append(title)
    if title and artist:
        candidates.append(f"{title} {artist}")
    if album and title:
        candidates.append(f"{title} {album}")
    if artist:
        candidates.append(artist)

    deduped: List[str] = []
    for c in candidates:
        if c and c not in deduped:
            deduped.append(c)
    return deduped
