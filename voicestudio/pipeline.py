"""v1 end-to-end orchestration: topic -> script -> cloned narration ->
(your screen recording) -> assembled video -> private YouTube upload.

v2 will replace the "your screen recording" step with automated,
segment-timed capture (terminal/browser), removing the manual step below.
"""

from pathlib import Path

from . import assemble, captions, publish, script_gen, voice
from .config import Config, load_config


def run(topic: str, recording_path: Path, config: Config | None = None, upload: bool = True) -> Path:
    config = config or load_config()

    print(f"[1/4] Generating script for: {topic!r}")
    script = script_gen.generate_script(topic, config)
    print(f"       title: {script['title']}  ({len(script['segments'])} segments)")

    audio_dir = config.output_dir / "audio"
    print("[2/4] Cloning narration")
    segments_result = voice.synthesize_segments(script, config, audio_dir)

    print("[3/4] Assembling video")
    srt_path = config.output_dir / "captions.srt"
    captions.build_srt(segments_result["segments"], srt_path)
    final_path = assemble.assemble_video(segments_result, recording_path, config.output_dir, srt_path)
    print(f"       -> {final_path}")

    if upload:
        print("[4/4] Uploading to YouTube (private)")
        video_id = publish.upload_video(final_path, script, privacy_status="private")
        print(f"       -> https://youtu.be/{video_id}  (private -- review, then publish yourself)")
    else:
        print("[4/4] Skipped upload (--no-upload)")

    return final_path
