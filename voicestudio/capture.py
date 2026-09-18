"""Automated screen capture for script segments.

"terminal" segments are captured for real: the command actually runs via
subprocess, its real output is captured, and a typing-animation clip of the
command + output is rendered with Pillow/ffmpeg as a real-looking terminal
window (title bar, traffic-light buttons, natural typing speed) --
deliberately not a headless-browser terminal recorder (tried Charm's VHS
first; it renders unreliably in this environment), so this has no fragile
external rendering dependency, just Pillow + ffmpeg.

CAUTION: this executes each "terminal" segment's action_detail for real, on
your machine. Review script.json (especially action_detail) before running
`capture` -- this is why it's an explicit opt-in step, not chained silently
into `run`.

Segments the automated backends don't cover yet ("browser", "mobile",
"desktop") fall back to a title card so the pipeline still produces a
complete video end to end; see README for what's next.
"""

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from . import diagram, visuals
from .render import DEFAULT_FORMAT, FPS, dimensions, frames_to_video, load_font, wrap_text

PAGE_BG = (12, 12, 15)
WINDOW_BG = (26, 26, 31)
TITLEBAR_BG = (42, 42, 48)
BORDER = (58, 58, 66)
DOT_COLORS = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]
TEXT_FG = (222, 224, 227)
PROMPT_COLOR = (98, 209, 150)
CURSOR_COLOR = (222, 224, 227)

WINDOW_MARGIN = 70
WINDOW_MAX_HEIGHT = 580  # bounded, not full-bleed -- keeps the window a sane
                          # size and vertically centered on tall/portrait frames
TITLEBAR_H = 40
CORNER_RADIUS = 12
CONTENT_PADDING = 28
FONT_SIZE = 21
LINE_HEIGHT = int(FONT_SIZE * 1.55)

CHARS_PER_SEC = 16  # natural-ish fast-typist pace, not instant
POST_TYPE_PAUSE_S = 0.5
LINE_REVEAL_S = 0.25

NOT_YET_AUTOMATED = {"browser", "mobile", "desktop"}


def _run_command(command: str) -> str:
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
    output = result.stdout
    if result.returncode != 0:
        output += result.stderr
    return output.strip()


def _window_bounds(width: int, height: int):
    x0, x1 = WINDOW_MARGIN, width - WINDOW_MARGIN
    win_h = min(height - 2 * WINDOW_MARGIN, WINDOW_MAX_HEIGHT)
    y0 = (height - win_h) // 2
    y1 = y0 + win_h
    return x0, y0, x1, y1


def _draw_window_chrome(
    draw: ImageDraw.ImageDraw, title: str, font, width: int, height: int
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = _window_bounds(width, height)
    draw.rounded_rectangle([x0, y0, x1, y1], radius=CORNER_RADIUS, fill=WINDOW_BG, outline=BORDER, width=1)
    draw.rectangle([x0 + 1, y0 + CORNER_RADIUS, x1 - 1, y0 + TITLEBAR_H], fill=TITLEBAR_BG)
    # round just the titlebar's top corners (rounded_rectangle would round all four)
    draw.pieslice([x0, y0, x0 + 2 * CORNER_RADIUS, y0 + 2 * CORNER_RADIUS], 180, 270, fill=TITLEBAR_BG)
    draw.pieslice([x1 - 2 * CORNER_RADIUS, y0, x1, y0 + 2 * CORNER_RADIUS], 270, 360, fill=TITLEBAR_BG)
    draw.rectangle([x0 + CORNER_RADIUS, y0, x1 - CORNER_RADIUS, y0 + TITLEBAR_H], fill=TITLEBAR_BG)

    cy = y0 + TITLEBAR_H // 2
    for i, color in enumerate(DOT_COLORS):
        cx = x0 + 26 + i * 22
        r = 6
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    if title:
        tw = font.getlength(title)
        draw.text(((x0 + x1) / 2 - tw / 2, cy - font.size / 2 - 1), title, font=font, fill=(150, 150, 158))

    return x0, y0 + TITLEBAR_H, x1, y1


def capture_terminal_segment(
    command: str, duration_s: float, out_path: Path, tmp_root: Path,
    video_format: str = DEFAULT_FORMAT,
) -> Path:
    frame_dir = tmp_root / f"frames_{out_path.stem}"
    frame_dir.mkdir(parents=True, exist_ok=True)
    width, height = dimensions(video_format)

    font = load_font(FONT_SIZE)
    title_font = load_font(15)
    x0, _, x1, _ = _window_bounds(width, height)
    max_width = (x1 - x0) - 2 * CONTENT_PADDING

    output_text = _run_command(command)
    output_lines = wrap_text(output_text, font, max_width) if output_text else []

    total_frames = max(int(duration_s * FPS), FPS)
    frames_per_char = FPS / CHARS_PER_SEC
    natural_type_frames = max(1, int(len(command) * frames_per_char))
    pause_frames = int(POST_TYPE_PAUSE_S * FPS)
    type_budget = int(total_frames * 0.8)
    type_frames = min(natural_type_frames, max(1, type_budget - pause_frames))

    reveal_step_frames = max(1, int(LINE_REVEAL_S * FPS))
    reveal_frames = min(len(output_lines) * reveal_step_frames, max(0, total_frames - type_frames - pause_frames))

    def draw(command_text: str, cursor_on: bool, lines: list[str], idx: int) -> None:
        img = Image.new("RGB", (width, height), PAGE_BG)
        d = ImageDraw.Draw(img)
        cx0, cy0, cx1, _ = _draw_window_chrome(d, "bash — organize-downloads", title_font, width, height)

        x = cx0 + CONTENT_PADDING
        y = cy0 + CONTENT_PADDING
        prompt_width = font.getlength("$ ")
        d.text((x, y), "$ ", font=font, fill=PROMPT_COLOR)
        d.text((x + prompt_width, y), command_text, font=font, fill=TEXT_FG)
        if cursor_on:
            cursor_x = x + prompt_width + font.getlength(command_text) + 2
            d.rectangle([cursor_x, y + 2, cursor_x + 10, y + FONT_SIZE + 2], fill=CURSOR_COLOR)
        y += LINE_HEIGHT
        for line in lines:
            d.text((x, y), line, font=font, fill=TEXT_FG)
            y += LINE_HEIGHT

        img.save(frame_dir / f"{idx:05d}.png")

    idx = 0
    for i in range(type_frames):
        n_chars = max(1, int(len(command) * (i + 1) / type_frames))
        cursor_on = (i // 6) % 2 == 0
        draw(command[:n_chars], cursor_on, [], idx)
        idx += 1
    for i in range(pause_frames):
        cursor_on = (i // 6) % 2 == 0
        draw(command, cursor_on, [], idx)
        idx += 1
    for i in range(reveal_frames):
        n_lines = max(1, int(len(output_lines) * (i + 1) / reveal_frames)) if reveal_frames else 0
        draw(command, False, output_lines[:n_lines], idx)
        idx += 1
    while idx < total_frames:
        draw(command, False, output_lines, idx)
        idx += 1

    return frames_to_video(frame_dir, out_path)


def capture_segments(
    segments_result: dict, out_dir: Path, tmp_root: Path, video_format: str = DEFAULT_FORMAT
) -> list[dict]:
    """Produce one video clip per segment. Returns segments with clip_path
    added. Prints a note for any segment rendered as a placeholder."""
    out_dir.mkdir(parents=True, exist_ok=True)
    clips = []
    for seg in segments_result["segments"]:
        clip_path = out_dir / f"{seg['id']:03d}.mp4"
        action_type = seg["action_type"]

        if action_type == "terminal":
            capture_terminal_segment(
                seg["action_detail"], seg["duration_s"], clip_path, tmp_root, video_format
            )
        elif action_type == "concept" and seg.get("diagram_steps"):
            diagram.concept_diagram_clip(
                seg["narration"], seg["diagram_steps"], seg["duration_s"], clip_path, tmp_root,
                video_format=video_format,
            )
        else:
            visuals.title_card_clip(
                seg["narration"], seg["duration_s"], clip_path, tmp_root,
                kind=action_type, video_format=video_format,
            )
            if action_type in NOT_YET_AUTOMATED:
                print(
                    f"       [segment {seg['id']}] '{action_type}' capture isn't automated yet "
                    "-- rendered a title card instead"
                )

        clips.append({**seg, "clip_path": str(clip_path)})

    return clips
