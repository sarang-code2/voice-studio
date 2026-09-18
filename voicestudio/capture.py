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

import random
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

CHARS_PER_SEC = 4  # base pace -- jitter below makes it feel human, not metronomic
POST_TYPE_PAUSE_S = 0.6
LINE_REVEAL_S = 0.3
MIN_OUTPUT_HOLD_S = 2.5  # protected reading time -- typing compression can't eat into this
MIN_TYPE_FRACTION = 0.35  # typing always gets at least this much of the clip, even if that
                           # means eating into the output-hold minimum -- prevents a long
                           # command in a short segment from compressing into an instant blur

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


def _typing_schedule(command: str, chars_per_sec: float) -> list[int]:
    """Frame index at which each character becomes visible. Jittered
    per-character speed plus occasional pauses after spaces, so it reads as
    someone typing, not a metronome. Seeded on the command so it's
    reproducible if you regenerate the same clip."""
    rng = random.Random(hash(command) & 0xFFFFFFFF)
    base = FPS / chars_per_sec
    t = 0.0
    schedule = []
    for ch in command:
        t += base * rng.uniform(0.55, 1.7)
        if ch == " " and rng.random() < 0.25:
            t += base * rng.uniform(1.5, 3.5)  # brief "thinking" pause
        schedule.append(t)
    return [int(round(x)) for x in schedule]


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
    prompt_width = font.getlength("$ ")
    # every command line is drawn indented by prompt_width (continuation
    # lines align under the command text, not under "$ "), so reserve that
    # width for every line -- otherwise a line wrapped to the full window
    # width overflows once shifted right by the indent
    max_width = (x1 - x0) - 2 * CONTENT_PADDING - prompt_width

    output_text = _run_command(command)
    output_lines = wrap_text(output_text, font, max_width) if output_text else []
    full_command_lines = wrap_text(command, font, max_width)

    total_frames = max(int(duration_s * FPS), FPS)
    pause_frames = int(POST_TYPE_PAUSE_S * FPS)
    reveal_step_frames = max(1, int(LINE_REVEAL_S * FPS))
    reveal_frames = len(output_lines) * reveal_step_frames
    min_hold_frames = int(MIN_OUTPUT_HOLD_S * FPS) if output_lines else 0

    # Reading time for the output is normally protected: typing gets
    # whatever's left after pause + reveal + the minimum hold. But typing
    # also gets a floor -- MIN_TYPE_FRACTION of the whole clip -- so a very
    # long command in a short segment can't compress into an instant blur;
    # in that case the floor wins and the output hold shrinks instead.
    available_for_type = max(1, total_frames - pause_frames)
    type_budget = available_for_type - reveal_frames - min_hold_frames
    type_budget = max(type_budget, int(total_frames * MIN_TYPE_FRACTION))
    type_budget = min(type_budget, available_for_type)
    schedule = _typing_schedule(command, CHARS_PER_SEC)
    natural_type_frames = max(1, schedule[-1] if schedule else 1)
    if natural_type_frames > type_budget:
        scale = type_budget / natural_type_frames
        schedule = [int(round(f * scale)) for f in schedule]
    type_frames = schedule[-1] + 1 if schedule else 1

    reveal_frames = min(reveal_frames, max(0, total_frames - type_frames - pause_frames))

    def draw(lines_typed: list[str], cursor_on: bool, output: list[str], idx: int) -> None:
        img = Image.new("RGB", (width, height), PAGE_BG)
        d = ImageDraw.Draw(img)
        cx0, cy0, cx1, _ = _draw_window_chrome(d, "bash — organize-downloads", title_font, width, height)

        x = cx0 + CONTENT_PADDING
        y = cy0 + CONTENT_PADDING
        prompt_width = font.getlength("$ ")
        lines_typed = lines_typed or [""]

        for li, line in enumerate(lines_typed):
            if li == 0:
                d.text((x, y), "$ ", font=font, fill=PROMPT_COLOR)
            d.text((x + prompt_width, y), line, font=font, fill=TEXT_FG)
            if cursor_on and li == len(lines_typed) - 1:
                cursor_x = x + prompt_width + font.getlength(line) + 2
                d.rectangle([cursor_x, y + 2, cursor_x + 10, y + FONT_SIZE + 2], fill=CURSOR_COLOR)
            y += LINE_HEIGHT

        for line in output:
            d.text((x, y), line, font=font, fill=TEXT_FG)
            y += LINE_HEIGHT

        img.save(frame_dir / f"{idx:05d}.png")

    idx = 0
    for i in range(type_frames):
        n_chars = 0
        while n_chars < len(schedule) and schedule[n_chars] <= i:
            n_chars += 1
        cursor_on = (i // 6) % 2 == 0
        lines_typed = wrap_text(command[:n_chars], font, max_width) if n_chars else [""]
        draw(lines_typed, cursor_on, [], idx)
        idx += 1
    for i in range(pause_frames):
        cursor_on = (i // 6) % 2 == 0
        draw(full_command_lines, cursor_on, [], idx)
        idx += 1
    for i in range(reveal_frames):
        n_lines = max(1, int(len(output_lines) * (i + 1) / reveal_frames)) if reveal_frames else 0
        draw(full_command_lines, False, output_lines[:n_lines], idx)
        idx += 1
    while idx < total_frames:
        draw(full_command_lines, False, output_lines, idx)
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
