"""Stitch narration audio, captions, and your screen recording into a final
video.

v1 assumption: you recorded the screen actions yourself, roughly following
the script's pacing, but the recording length won't exactly match the
generated narration. We retime the (silent) recording to match the
narration's total duration by uniformly speeding it up or slowing it down,
then mux the narration audio over it.

No caption/subtitle track is attached to the video -- a soft mov_text track
was tried, but some players (QuickTime included) display it automatically
regardless of the "toggle" intent, which just duplicates the narration as
on-screen text. `captions.build_srt()` still writes output/captions.srt
separately, in case you want to upload it to YouTube as an optional caption
file.

Once the automated capture pipeline (v2) drives + records the actions itself
timed to each segment's audio, this retiming step goes away.
"""

import subprocess
from pathlib import Path

from . import captions
from .render import DEFAULT_FORMAT, dimensions

GAP_S = captions.GAP_S


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def _build_narration_track(segments: list[dict], sample_rate: int, out_dir: Path) -> Path:
    silence_path = out_dir / "_silence.wav"
    _run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r={sample_rate}:cl=mono",
        "-t", str(GAP_S), str(silence_path),
    ])

    list_path = out_dir / "_concat_list.txt"
    with open(list_path, "w") as f:
        for i, seg in enumerate(segments):
            f.write(f"file '{Path(seg['audio_path']).resolve()}'\n")
            if i < len(segments) - 1:
                f.write(f"file '{silence_path.resolve()}'\n")

    narration_path = out_dir / "narration.wav"
    _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-ar", str(sample_rate), "-ac", "1", str(narration_path),
    ])
    return narration_path


def assemble_video(segments_result: dict, recording_path: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    segments = segments_result["segments"]
    sample_rate = segments_result["sample_rate"]

    narration_path = _build_narration_track(segments, sample_rate, out_dir)
    narration_duration = _probe_duration(narration_path)
    video_duration = _probe_duration(recording_path)
    speed_factor = narration_duration / video_duration

    final_path = out_dir / "final.mp4"
    _run([
        "ffmpeg", "-y",
        "-i", str(recording_path),
        "-i", str(narration_path),
        "-filter_complex", f"[0:v]setpts=PTS*{speed_factor}[v]",
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-c:a", "aac",
        "-shortest",
        str(final_path),
    ])
    return final_path


def assemble_from_clips(
    segments_result: dict, clips: list[dict], out_dir: Path,
    video_format: str = DEFAULT_FORMAT,
) -> Path:
    """v2 assembly: each segment already has its own clip (real terminal
    capture or a title card) whose duration exactly matches its narration
    segment, so this is a straight concat -- no retiming heuristic needed."""
    out_dir.mkdir(parents=True, exist_ok=True)
    video_width, video_height = dimensions(video_format)
    sample_rate = segments_result["sample_rate"]
    narration_path = _build_narration_track(segments_result["segments"], sample_rate, out_dir)

    norm_dir = out_dir / "_norm_clips"
    norm_dir.mkdir(parents=True, exist_ok=True)
    concat_list = out_dir / "_clips_concat.txt"
    with open(concat_list, "w") as f:
        for i, clip in enumerate(clips):
            norm_path = norm_dir / f"{i:05d}.mp4"
            _run([
                "ffmpeg", "-y", "-i", clip["clip_path"],
                "-vf",
                f"scale={video_width}:{video_height}:force_original_aspect_ratio=decrease,"
                f"pad={video_width}:{video_height}:(ow-iw)/2:(oh-ih)/2",
                "-r", "24", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(norm_path),
            ])
            f.write(f"file '{norm_path.resolve()}'\n")

    silent_video = out_dir / "_silent.mp4"
    _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", str(silent_video),
    ])

    final_path = out_dir / "final.mp4"
    _run([
        "ffmpeg", "-y",
        "-i", str(silent_video), "-i", str(narration_path),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-c:a", "aac",
        "-shortest",
        str(final_path),
    ])
    return final_path
