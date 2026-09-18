"""Build an SRT caption file from timed narration segments."""

from pathlib import Path

GAP_S = 0.3


def _format_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(segments: list[dict], out_path: Path) -> Path:
    lines = []
    t = 0.0
    for i, seg in enumerate(segments, start=1):
        start, end = t, t + seg["duration_s"]
        lines += [
            str(i),
            f"{_format_timestamp(start)} --> {_format_timestamp(end)}",
            seg["narration"],
            "",
        ]
        t = end + GAP_S

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def total_narration_duration(segments: list[dict]) -> float:
    if not segments:
        return 0.0
    return sum(seg["duration_s"] for seg in segments) + GAP_S * (len(segments) - 1)
