from pathlib import Path


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


def is_image_path(value: str) -> bool:
    path = Path(value.strip('"').strip("'"))
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS

