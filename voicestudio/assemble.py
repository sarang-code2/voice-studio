"""Stitch narration audio, captions, and your screen recording into a final
video.

v1 assumption: you recorded the screen actions yourself, roughly following
the script's pacing, but the recording length won't exactly match the
generated narration. We retime the (silent) recording to match the
narration's total duration by uniformly speeding it up or slowing it down,
then mux the narration audio over it and burn in captions.

Once the automated capture pipeline (v2) drives + records the actions itself
timed to each segment's audio, this retiming step goes away.
"""

import subprocess
from pathlib import Path

from . import captions

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


def _escape_for_filter(path: Path) -> str:
    # ffmpeg filter arguments treat : and ' specially.
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def assemble_video(
    segments_result: dict, recording_path: Path, out_dir: Path, srt_path: Path
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    segments = segments_result["segments"]
    sample_rate = segments_result["sample_rate"]

    narration_path = _build_narration_track(segments, sample_rate, out_dir)
    narration_duration = _probe_duration(narration_path)
    video_duration = _probe_duration(recording_path)
    speed_factor = narration_duration / video_duration

    final_path = out_dir / "final.mp4"
    srt_arg = _escape_for_filter(srt_path)
    _run([
        "ffmpeg", "-y",
        "-i", str(recording_path),
        "-i", str(narration_path),
        "-filter_complex",
        f"[0:v]setpts=PTS*{speed_factor},subtitles='{srt_arg}'[v]",
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-c:a", "aac", "-shortest",
        str(final_path),
    ])
    return final_path
