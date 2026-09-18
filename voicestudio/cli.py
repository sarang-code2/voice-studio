import argparse
import json
from pathlib import Path

from . import assemble, captions, pipeline, publish, script_gen, voice
from .config import load_config


def cmd_script(args):
    config = load_config()
    script = script_gen.generate_script(args.topic, config)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(script, indent=2))
    print(f"Wrote {out}  ({len(script['segments'])} segments)")


def cmd_narrate(args):
    config = load_config()
    script = json.loads(Path(args.script).read_text())
    result = voice.synthesize_segments(script, config, Path(args.out_dir))
    print(f"Wrote {args.out_dir}/segments.json  ({len(result['segments'])} clips)")


def cmd_assemble(args):
    segments_result = json.loads(Path(args.segments).read_text())
    out_dir = Path(args.out_dir)
    srt_path = out_dir / "captions.srt"
    captions.build_srt(segments_result["segments"], srt_path)
    final_path = assemble.assemble_video(
        segments_result, Path(args.recording), out_dir, srt_path
    )
    print(f"Wrote {final_path}")


def cmd_publish(args):
    script = json.loads(Path(args.script).read_text())
    video_id = publish.upload_video(Path(args.video), script, privacy_status=args.privacy)
    print(f"https://youtu.be/{video_id}  ({args.privacy})")


def cmd_run(args):
    pipeline.run(args.topic, Path(args.recording), upload=not args.no_upload)


def main():
    parser = argparse.ArgumentParser(prog="voicestudio")
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("script", help="generate a tutorial script from a topic")
    p.add_argument("--topic", required=True)
    p.add_argument("--out", default="output/script.json")
    p.set_defaults(func=cmd_script)

    p = sub.add_parser("narrate", help="clone narration audio for a script")
    p.add_argument("--script", required=True)
    p.add_argument("--out-dir", default="output/audio")
    p.set_defaults(func=cmd_narrate)

    p = sub.add_parser("assemble", help="mux narration + captions onto your screen recording")
    p.add_argument("--segments", required=True, help="segments.json from `narrate`")
    p.add_argument("--recording", required=True, help="your screen recording (mp4)")
    p.add_argument("--out-dir", default="output")
    p.set_defaults(func=cmd_assemble)

    p = sub.add_parser("publish", help="upload a finished video to YouTube (private/unlisted only)")
    p.add_argument("--video", required=True)
    p.add_argument("--script", required=True, help="script.json, for title/description/tags")
    p.add_argument("--privacy", default="private", choices=["private", "unlisted"])
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("run", help="full v1 pipeline: topic -> script -> voice -> assemble -> upload")
    p.add_argument("--topic", required=True)
    p.add_argument("--recording", required=True, help="your screen recording (mp4)")
    p.add_argument("--no-upload", action="store_true")
    p.set_defaults(func=cmd_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
