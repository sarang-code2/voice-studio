"""Automated screen capture for script segments.

"terminal" segments are captured for real: the command actually runs via
subprocess, its real output is captured, and a typing-animation clip of the
command + output is rendered with Pillow/ffmpeg -- deliberately not a
headless-browser terminal recorder (tried Charm's VHS first; it renders
unreliably in this environment), so this has no fragile external rendering
dependency, just Pillow + ffmpeg.

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

from . import visuals
from .render import FPS, HEIGHT, MARGIN, WIDTH, frames_to_video, load_font, wrap_text

BG = (30, 30, 34)
FG = (223, 225, 227)
PROMPT_COLOR = (98, 209, 150)
FONT_SIZE = 22
LINE_HEIGHT = int(FONT_SIZE * 1.5)

NOT_YET_AUTOMATED = {"browser", "mobile", "desktop"}


def _run_command(command: str) -> str:
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
    output = result.stdout
    if result.returncode != 0:
        output += result.stderr
    return output.strip()


def capture_terminal_segment(command: str, duration_s: float, out_path: Path, tmp_root: Path) -> Path:
    frame_dir = tmp_root / f"frames_{out_path.stem}"
    frame_dir.mkdir(parents=True, exist_ok=True)

    font = load_font(FONT_SIZE)
    max_width = WIDTH - 2 * MARGIN
    output_text = _run_command(command)
    output_lines = wrap_text(output_text, font, max_width) if output_text else []

    total_frames = max(int(duration_s * FPS), FPS)
    type_frames = max(1, min(int(len(command) * 1.2), total_frames // 2))
    reveal_frames = min(len(output_lines) * 2, total_frames - type_frames) if output_lines else 0

    def draw(command_text: str, lines: list[str], idx: int) -> None:
        img = Image.new("RGB", (WIDTH, HEIGHT), BG)
        d = ImageDraw.Draw(img)
        y = MARGIN
        prompt_width = font.getlength("$ ")
        d.text((MARGIN, y), "$ ", font=font, fill=PROMPT_COLOR)
        d.text((MARGIN + prompt_width, y), command_text, font=font, fill=FG)
        y += LINE_HEIGHT
        for line in lines:
            d.text((MARGIN, y), line, font=font, fill=FG)
            y += LINE_HEIGHT
        img.save(frame_dir / f"{idx:05d}.png")

    idx = 0
    for i in range(type_frames):
        n_chars = max(1, int(len(command) * (i + 1) / type_frames))
        draw(command[:n_chars], [], idx)
        idx += 1
    for i in range(reveal_frames):
        n_lines = max(1, int(len(output_lines) * (i + 1) / reveal_frames))
        draw(command, output_lines[:n_lines], idx)
        idx += 1
    while idx < total_frames:
        draw(command, output_lines, idx)
        idx += 1

    return frames_to_video(frame_dir, out_path)


def capture_segments(segments_result: dict, out_dir: Path, tmp_root: Path) -> list[dict]:
    """Produce one video clip per segment. Returns segments with clip_path
    added. Prints a note for any segment rendered as a placeholder."""
    out_dir.mkdir(parents=True, exist_ok=True)
    clips = []
    for seg in segments_result["segments"]:
        clip_path = out_dir / f"{seg['id']:03d}.mp4"
        action_type = seg["action_type"]

        if action_type == "terminal":
            capture_terminal_segment(seg["action_detail"], seg["duration_s"], clip_path, tmp_root)
        else:
            heading = action_type.upper() if action_type in NOT_YET_AUTOMATED else ""
            visuals.title_card_clip(seg["narration"], seg["duration_s"], clip_path, tmp_root, heading=heading)
            if action_type in NOT_YET_AUTOMATED:
                print(
                    f"       [segment {seg['id']}] '{action_type}' capture isn't automated yet "
                    "-- rendered a title card instead"
                )

        clips.append({**seg, "clip_path": str(clip_path)})

    return clips
