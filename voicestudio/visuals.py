"""Title-card clips for segments with no automated screen capture:
concept/note segments, and a placeholder for browser/mobile/desktop until
those capture backends exist. Fade-in text with a kicker label and accent
bar so each segment kind reads distinctly (not just plain centered text).

This is intentionally simple -- a functional placeholder, not the eventual
richer "animation explaining the concept" motion graphics. That's a later
phase; see README.
"""

from pathlib import Path

from PIL import Image, ImageDraw

from .render import DEFAULT_FORMAT, FPS, MARGIN, dimensions, frames_to_video, load_sans_font, wrap_text

BG = (16, 16, 20)
FG = (235, 235, 240)
FADE_S = 0.6

KIND_STYLE = {
    "concept": {"label": "THE IDEA", "accent": (98, 209, 150)},
    "note": {"label": "", "accent": (120, 150, 235)},
    "browser": {"label": "BROWSER -- COMING SOON", "accent": (230, 175, 80)},
    "mobile": {"label": "MOBILE -- COMING SOON", "accent": (230, 175, 80)},
    "desktop": {"label": "DESKTOP -- COMING SOON", "accent": (230, 175, 80)},
}


def title_card_clip(
    text: str, duration_s: float, out_path: Path, tmp_root: Path,
    kind: str = "note", video_format: str = DEFAULT_FORMAT,
) -> Path:
    frame_dir = tmp_root / f"frames_{out_path.stem}"
    frame_dir.mkdir(parents=True, exist_ok=True)
    width, height = dimensions(video_format)

    style = KIND_STYLE.get(kind, KIND_STYLE["note"])
    accent = style["accent"]
    label = style["label"]

    # portrait/reel frames are narrower -- bigger type reads better at
    # phone-scroll speed and fills the frame instead of leaving it sparse
    is_portrait = height > width
    label_font = load_sans_font(26 if is_portrait else 22)
    body_font = load_sans_font(40 if is_portrait else 32)
    content_width = width - 2 * MARGIN - 80
    body_lines = wrap_text(text, body_font, content_width)

    total_frames = max(int(duration_s * FPS), FPS)
    fade_frames = max(int(FADE_S * FPS), 1)

    body_line_height = int(body_font.size * 1.45)
    label_block = int(label_font.size * 2.2) if label else 0
    block_height = len(body_lines) * body_line_height + label_block
    bar_width = 5
    bar_height = block_height + 16

    for i in range(total_frames):
        opacity = min(1.0, (i + 1) / fade_frames)
        img = Image.new("RGB", (width, height), BG)
        draw = ImageDraw.Draw(img)
        fg = tuple(int(c * opacity) for c in FG)
        acc = tuple(int(c * opacity) for c in accent)

        left_x = (width - content_width) // 2
        y = (height - block_height) // 2

        draw.rectangle([left_x - 28, y - 8, left_x - 28 + bar_width, y - 8 + bar_height], fill=acc)

        if label:
            draw.text((left_x, y), label, font=label_font, fill=acc)
            y += label_block

        for line in body_lines:
            draw.text((left_x, y), line, font=body_font, fill=fg)
            y += body_line_height

        img.save(frame_dir / f"{i:05d}.png")

    return frames_to_video(frame_dir, out_path)
