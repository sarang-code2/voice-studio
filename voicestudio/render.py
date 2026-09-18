"""Shared frame-rendering helpers used by capture.py (terminal clips) and
visuals.py (title cards): both draw frames with Pillow and encode them with
ffmpeg. Plain functions, no shared state between calls.

Two output formats: "landscape" (16:9, regular YouTube) and "portrait"
(9:16, Shorts/Reels/TikTok). Callers pass a format name and get pixel
dimensions back -- nothing here is hardcoded to one aspect ratio.
"""

import shutil
import subprocess
from pathlib import Path

from PIL import ImageFont

FORMATS = {
    "landscape": (1280, 720),
    "portrait": (1080, 1920),
}
DEFAULT_FORMAT = "landscape"

FPS = 24
MARGIN = 48

_FONT_PATHS = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Supplemental/Andale Mono.ttf",
]


def dimensions(video_format: str) -> tuple[int, int]:
    if video_format not in FORMATS:
        raise ValueError(f"unknown format {video_format!r}, choose from {list(FORMATS)}")
    return FORMATS[video_format]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines = []
    for raw_line in text.split("\n"):
        if not raw_line:
            lines.append("")
            continue
        current = ""
        for word in raw_line.split(" "):
            trial = f"{current} {word}".strip()
            if font.getlength(trial) <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def frames_to_video(frame_dir: Path, out_path: Path, fps: int = FPS) -> Path:
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-framerate", str(fps), "-i", str(frame_dir / "%05d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_path),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed encoding {out_path}:\n{result.stderr}")
    shutil.rmtree(frame_dir)
    return out_path
