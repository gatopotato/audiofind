import base64
import json
import os
from pathlib import Path
from typing import Dict

import requests


GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _guess_mime_type(image_path: str) -> str:
    suffix = Path(image_path).suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".bmp":
        return "image/bmp"
    return "application/octet-stream"


def _extract_json_object(text: str) -> Dict[str, str]:
    stripped = text.strip()
    try:
        data = json.loads(stripped)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(stripped[start : end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    raise RuntimeError("Gemini response did not contain valid JSON metadata.")


def detect_metadata_from_image_with_gemini(image_path: str) -> Dict[str, str]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in environment.")

    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    prompt = (
        "You are extracting music metadata from an image/screenshot. "
        "Return ONLY valid JSON with keys: title, artist, album, confidence, reason. "
        "Use empty strings when unknown. confidence must be a number from 0 to 1."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": _guess_mime_type(image_path),
                            "data": base64.b64encode(image_bytes).decode("utf-8"),
                        }
                    },
                ]
            }
        ]
    }

    response = requests.post(
        f"{GEMINI_API_URL}/{model}:generateContent?key={api_key}",
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=45,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Gemini request failed: {response.status_code} {response.text}")

    data = response.json()
    parts = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])
    )
    text = parts[0].get("text", "") if parts else ""
    parsed = _extract_json_object(text)

    return {
        "title": str(parsed.get("title", "")).strip(),
        "artist": str(parsed.get("artist", "")).strip(),
        "album": str(parsed.get("album", "")).strip(),
    }

