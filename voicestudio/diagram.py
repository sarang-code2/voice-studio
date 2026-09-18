"""Animated flow-diagram clips for concept segments: narration text plus a
short sequence of labeled boxes connected by arrows, each appearing in turn
across the segment's duration -- a lightweight, dependency-free stand-in
for real motion graphics/illustrations (still just Pillow + ffmpeg, same
renderer family as capture.py and visuals.py).

Falls back to a plain title card (visuals.py) when a concept segment has no
diagram_steps -- not every idea reduces cleanly to a flow.
"""

from pathlib import Path

from PIL import Image, ImageDraw

from .render import DEFAULT_FORMAT, FPS, MARGIN, dimensions, frames_to_video, load_font, load_sans_font, wrap_text

BG = (18, 18, 23)
FG = (235, 235, 240)
ACCENT = (108, 219, 160)
BOX_BG = (36, 48, 42)
ARROW_COLOR = (130, 165, 150)
KICKER = "THE IDEA"

FADE_S = 0.5
STEP_LEAD_S = 0.4  # delay before the diagram starts, after the text fades in
STEP_GROW_FRAC = 0.6  # fraction of a step's time budget spent animating in
SLIDE_PX = 14


def _ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) * (1 - t)


def concept_diagram_clip(
    text: str, steps: list[str], duration_s: float, out_path: Path, tmp_root: Path,
    video_format: str = DEFAULT_FORMAT,
) -> Path:
    frame_dir = tmp_root / f"frames_{out_path.stem}"
    frame_dir.mkdir(parents=True, exist_ok=True)
    width, height = dimensions(video_format)
    is_portrait = height > width

    label_font = load_sans_font(26 if is_portrait else 22)
    body_font = load_sans_font(38 if is_portrait else 30)
    step_font = load_sans_font(21 if is_portrait else 19)

    text_max_width = width - 2 * MARGIN - 80
    text_left = (width - text_max_width) // 2 if is_portrait else MARGIN + 40
    body_lines = wrap_text(text, body_font, text_max_width)
    body_line_height = int(body_font.size * 1.4)
    label_block = int(label_font.size * 2.2)
    text_block_height = label_block + len(body_lines) * body_line_height
    text_to_diagram_gap = 70 if is_portrait else 76

    n = max(1, len(steps))
    if is_portrait:
        box_w = width - 2 * MARGIN - 60
        box_h = 96
        gap = 50
        box_x0 = MARGIN + 30
        diagram_height = n * box_h + (n - 1) * gap
    else:
        box_h = 130
        gap = 44
        box_w = min(230, (width - 2 * MARGIN - (n - 1) * gap) // n)
        total_diagram_w = n * box_w + (n - 1) * gap
        box_x0 = (width - total_diagram_w) // 2
        diagram_height = box_h

    # center the whole text+diagram block in the frame, rather than pinning
    # it to the top with empty space left dangling below
    block_height = text_block_height + text_to_diagram_gap + diagram_height
    text_y0 = max(MARGIN, (height - block_height) // 2)
    diagram_top = text_y0 + text_block_height + text_to_diagram_gap

    total_frames = max(int(duration_s * FPS), FPS)
    fade_frames = max(int(FADE_S * FPS), 1)
    lead_frames = int(STEP_LEAD_S * FPS)
    diagram_frames = max(1, total_frames - lead_frames)
    step_frames = max(1, diagram_frames // n)

    for i in range(total_frames):
        text_opacity = min(1.0, (i + 1) / fade_frames)
        img = Image.new("RGB", (width, height), BG)
        draw = ImageDraw.Draw(img)
        fg = tuple(int(c * text_opacity) for c in FG)
        acc = tuple(int(c * text_opacity) for c in ACCENT)

        ty = text_y0
        draw.text((text_left, ty), KICKER, font=label_font, fill=acc)
        ty += label_block
        for line in body_lines:
            draw.text((text_left, ty), line, font=body_font, fill=fg)
            ty += body_line_height

        for idx, label in enumerate(steps):
            reveal_frame = lead_frames + idx * step_frames
            local = i - reveal_frame
            if local < 0:
                continue
            grow_frames = max(1, int(step_frames * STEP_GROW_FRAC))
            progress = _ease_out(local / grow_frames)
            slide = int(SLIDE_PX * (1 - progress))
            box_fg = tuple(int(c * progress) for c in ACCENT)
            box_bg = tuple(int(v * progress) for v in BOX_BG)
            label_fg = tuple(int(c * progress) for c in FG)

            if is_portrait:
                bx0, bx1 = box_x0, box_x0 + box_w
                by0 = diagram_top + idx * (box_h + gap) + slide
                by1 = by0 + box_h
            else:
                bx0 = box_x0 + idx * (box_w + gap)
                bx1 = bx0 + box_w
                by0 = diagram_top + slide
                by1 = by0 + box_h

            draw.rounded_rectangle([bx0, by0, bx1, by1], radius=10, fill=box_bg, outline=box_fg, width=2)
            label_lines = wrap_text(label, step_font, box_w - 24)[:3]
            ly = by0 + (box_h - len(label_lines) * int(step_font.size * 1.3)) // 2
            for ll in label_lines:
                lw = step_font.getlength(ll)
                draw.text((bx0 + (box_w - lw) / 2, ly), ll, font=step_font, fill=label_fg)
                ly += int(step_font.size * 1.3)

            if idx > 0:
                arrow_col = tuple(int(c * progress) for c in ARROW_COLOR)
                if is_portrait:
                    ax = bx0 + box_w / 2
                    ay0, ay1 = by0 - gap + 6, by0 - 6
                    draw.line([(ax, ay0), (ax, ay1)], fill=arrow_col, width=3)
                    draw.polygon([(ax - 6, ay1 - 8), (ax + 6, ay1 - 8), (ax, ay1)], fill=arrow_col)
                else:
                    ay = by0 + box_h / 2
                    ax0, ax1 = bx0 - gap + 6, bx0 - 6
                    draw.line([(ax0, ay), (ax1, ay)], fill=arrow_col, width=3)
                    draw.polygon([(ax1 - 8, ay - 6), (ax1 - 8, ay + 6), (ax1, ay)], fill=arrow_col)

        img.save(frame_dir / f"{i:05d}.png")

    return frames_to_video(frame_dir, out_path)
