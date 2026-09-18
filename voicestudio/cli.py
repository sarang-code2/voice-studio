import argparse
import json
from pathlib import Path

from . import assemble, capture, captions, pipeline, publish, script_gen, voice
from .config import load_config


def cmd_script(args):
    config = load_config()
    script = script_gen.generate_script(args.topic, config, args.format)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(script, indent=2))
    print(f"Wrote {out}  ({len(script['segments'])} segments)")


def cmd_narrate(args):
    config = load_config()
    script = json.loads(Path(args.script).read_text())
    result = voice.synthesize_segments(script, config, Path(args.out_dir))
    print(f"Wrote {args.out_dir}/segments.json  ({len(result['segments'])} clips)")


def cmd_capture(args):
    segments_result = json.loads(Path(args.segments).read_text())
    print(
        "About to actually run every 'terminal' segment's command on this machine. "
        "Commands:"
    )
    for seg in segments_result["segments"]:
        if seg["action_type"] == "terminal":
            print(f"  [{seg['id']}] {seg['action_detail']}")
    clips_dir = Path(args.out_dir) / "clips"
    tmp_root = Path(args.out_dir) / "_tmp"
    clips = capture.capture_segments(segments_result, clips_dir, tmp_root, args.format)
    print(f"Wrote {len(clips)} clips to {clips_dir}")


def cmd_assemble(args):
    segments_result = json.loads(Path(args.segments).read_text())
    out_dir = Path(args.out_dir)
    srt_path = out_dir / "captions.srt"
    captions.build_srt(segments_result["segments"], srt_path)
    print(f"captions written to {srt_path} (not attached to the video -- upload separately if wanted)")

    if args.recording:
        final_path = assemble.assemble_video(segments_result, Path(args.recording), out_dir)
    else:
        clips_dir = Path(args.clips_dir) if args.clips_dir else out_dir / "clips"
        clips = [
            {**seg, "clip_path": str(clips_dir / f"{seg['id']:03d}.mp4")}
            for seg in segments_result["segments"]
        ]
        final_path = assemble.assemble_from_clips(segments_result, clips, out_dir, args.format)

    print(f"Wrote {final_path}")


def cmd_publish(args):
    script = json.loads(Path(args.script).read_text())
    video_id = publish.upload_video(Path(args.video), script, privacy_status=args.privacy)
    print(f"https://youtu.be/{video_id}  ({args.privacy})")


def cmd_run(args):
    recording_path = Path(args.recording) if args.recording else None
    pipeline.run(
        args.topic,
        recording_path=recording_path,
        auto_capture=args.auto_capture,
        upload=not args.no_upload,
        video_format=args.format,
    )


def main():
    parser = argparse.ArgumentParser(prog="voicestudio")
    sub = parser.add_subparsers(required=True)
    format_help = "landscape (16:9, regular video) or portrait (9:16, Reels/Shorts/TikTok)"

    p = sub.add_parser("script", help="generate a tutorial script from a topic")
    p.add_argument("--topic", required=True)
    p.add_argument("--out", default="output/script.json")
    p.add_argument("--format", default="landscape", choices=["landscape", "portrait"], help=format_help)
    p.set_defaults(func=cmd_script)

    p = sub.add_parser("narrate", help="clone narration audio for a script")
    p.add_argument("--script", required=True)
    p.add_argument("--out-dir", default="output/audio")
    p.set_defaults(func=cmd_narrate)

    p = sub.add_parser(
        "capture",
        help="automatically capture each segment (real terminal commands; title cards for the rest)",
    )
    p.add_argument("--segments", required=True, help="segments.json from `narrate`")
    p.add_argument("--out-dir", default="output")
    p.add_argument("--format", default="landscape", choices=["landscape", "portrait"], help=format_help)
    p.set_defaults(func=cmd_capture)

    p = sub.add_parser("assemble", help="mux narration + captions onto captured clips or your recording")
    p.add_argument("--segments", required=True, help="segments.json from `narrate`")
    p.add_argument("--recording", help="your screen recording (mp4) -- v1 manual path")
    p.add_argument("--clips-dir", help="per-segment clips from `capture` (default: <out-dir>/clips)")
    p.add_argument("--out-dir", default="output")
    p.add_argument("--format", default="landscape", choices=["landscape", "portrait"], help=format_help)
    p.set_defaults(func=cmd_assemble)

    p = sub.add_parser("publish", help="upload a finished video to YouTube (private/unlisted only)")
    p.add_argument("--video", required=True)
    p.add_argument("--script", required=True, help="script.json, for title/description/tags")
    p.add_argument("--privacy", default="private", choices=["private", "unlisted"])
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("run", help="full pipeline: topic -> script -> voice -> capture -> assemble -> upload")
    p.add_argument("--topic", required=True)
    p.add_argument("--recording", help="your screen recording (mp4) -- v1 manual path")
    p.add_argument("--auto-capture", action="store_true", help="capture segments automatically instead")
    p.add_argument("--no-upload", action="store_true")
    p.add_argument("--format", default="landscape", choices=["landscape", "portrait"], help=format_help)
    p.set_defaults(func=cmd_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
