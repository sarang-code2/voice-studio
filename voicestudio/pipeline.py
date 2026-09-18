"""End-to-end orchestration: topic -> script -> cloned narration -> capture
-> assembled video -> private YouTube upload.

Two ways to get the screen capture:
- auto_capture=True: "terminal" segments are captured automatically (the
  command really runs, its real output is rendered); everything else
  (concept/note segments, and browser/mobile/desktop until those capture
  backends exist) renders as a title card.
- recording_path=<your screen recording>: v1 fallback, retimes your manual
  recording to match the narration.
"""

from pathlib import Path

from . import assemble, capture, captions, publish, script_gen, voice
from .config import Config, load_config
from .render import DEFAULT_FORMAT
from .script_gen import REEL_MAX_SECONDS


def run(
    topic: str,
    recording_path: Path | None = None,
    auto_capture: bool = False,
    config: Config | None = None,
    upload: bool = True,
    video_format: str = DEFAULT_FORMAT,
) -> Path:
    if bool(recording_path) == bool(auto_capture):
        raise ValueError("pass exactly one of recording_path or auto_capture=True")

    config = config or load_config()

    print(f"[1/5] Generating script for: {topic!r} ({video_format})")
    script = script_gen.generate_script(topic, config, video_format)
    print(f"       title: {script['title']}  ({len(script['segments'])} segments)")

    audio_dir = config.output_dir / "audio"
    print("[2/5] Cloning narration")
    segments_result = voice.synthesize_segments(script, config, audio_dir)

    total_narration_s = captions.total_narration_duration(segments_result["segments"])
    if video_format == "portrait" and total_narration_s > REEL_MAX_SECONDS:
        print(
            f"       WARNING: narration is {total_narration_s:.0f}s, over the "
            f"{REEL_MAX_SECONDS}s reel cap -- topic may be too broad for a reel. "
            "Continuing anyway; consider a narrower topic and re-running."
        )

    srt_path = config.output_dir / "captions.srt"
    captions.build_srt(segments_result["segments"], srt_path)
    print(f"       captions written to {srt_path} (not attached to the video -- upload separately if wanted)")

    if auto_capture:
        print("[3/5] Capturing screen actions automatically")
        clips = capture.capture_segments(
            segments_result, config.output_dir / "clips", config.output_dir / "_tmp", video_format
        )
        print("[4/5] Assembling video")
        final_path = assemble.assemble_from_clips(segments_result, clips, config.output_dir, video_format)
    else:
        print(f"[3/5] Using your recording: {recording_path}")
        print("[4/5] Assembling video")
        final_path = assemble.assemble_video(segments_result, recording_path, config.output_dir)

    print(f"       -> {final_path}")

    if upload:
        print("[5/5] Uploading to YouTube (private)")
        video_id = publish.upload_video(final_path, script, privacy_status="private")
        print(f"       -> https://youtu.be/{video_id}  (private -- review, then publish yourself)")
    else:
        print("[5/5] Skipped upload (--no-upload)")

    return final_path
