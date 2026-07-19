"""Image sources for the inference CLI.

FolderSource reads image files now; an Esp32CaptureSource (GET /capture) will
implement the same .frames() interface later without touching downstream code.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .naming import sample_code_from_filename

_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


@dataclass
class Frame:
    image_bytes: bytes
    sample_code: str
    captured_at: datetime  # timezone-aware (web ingest requires an offset)
    source_name: str       # original filename, for logging


class FolderSource:
    """Yield Frames from a folder of images, or a single image file."""

    def __init__(self, path):
        self.path = Path(path)

    def frames(self):
        if self.path.is_file():
            paths = [self.path]
        else:
            paths = sorted(
                p for p in self.path.iterdir()
                if p.suffix.lower() in _IMAGE_EXTS
            )
        for p in paths:
            captured_at = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
            yield Frame(
                image_bytes=p.read_bytes(),
                sample_code=sample_code_from_filename(p.name),
                captured_at=captured_at,
                source_name=p.name,
            )
