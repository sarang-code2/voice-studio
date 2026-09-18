"""Fade-in title-card clips: centered text on a solid background. Used for
concept/note segments, intro/outro cards, and as a placeholder for capture
backends (browser/mobile/desktop) that don't exist yet.

This is intentionally simple -- a functional placeholder, not the final
"animation explaining the concept" motion graphics. Richer concept visuals
(diagrams, motion graphics) are a later phase; see README.
"""

from pathlib import Path

from PIL import Image, ImageDraw

from .render import FPS, HEIGHT, MARGIN, WIDTH, frames_to_video, load_font, wrap_text

BG = (18, 18, 22)
FG = (235, 235, 240)
ACCENT = (98, 209, 150)
FADE_S = 0.6


def title_card_clip(
    text: str, duration_s: float, out_path: Path, tmp_root: Path, heading: str = ""
) -> Path:
    frame_dir = tmp_root / f"frames_{out_path.stem}"
    frame_dir.mkdir(parents=True, exist_ok=True)

    heading_font = load_font(40)
    body_font = load_font(28)
    body_lines = wrap_text(text, body_font, WIDTH - 2 * MARGIN)

    total_frames = max(int(duration_s * FPS), FPS)
    fade_frames = max(int(FADE_S * FPS), 1)

    body_line_height = int(body_font.size * 1.4)
    heading_line_height = int(heading_font.size * 1.8)
    block_height = len(body_lines) * body_line_height + (heading_line_height if heading else 0)

    for i in range(total_frames):
        opacity = min(1.0, (i + 1) / fade_frames)
        img = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(img)
        fg = tuple(int(c * opacity) for c in FG)
        accent = tuple(int(c * opacity) for c in ACCENT)

        y = (HEIGHT - block_height) // 2
        if heading:
            w = heading_font.getlength(heading)
            draw.text(((WIDTH - w) / 2, y), heading, font=heading_font, fill=accent)
            y += heading_line_height

        for line in body_lines:
            w = body_font.getlength(line)
            draw.text(((WIDTH - w) / 2, y), line, font=body_font, fill=fg)
            y += body_line_height

        img.save(frame_dir / f"{i:05d}.png")

    return frames_to_video(frame_dir, out_path)
