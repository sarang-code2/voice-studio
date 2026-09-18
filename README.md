# voice-studio

Turns a tutorial topic into a narrated, captioned video in your own cloned
voice, and uploads it to YouTube as private/unlisted for review.

**Pipeline:** topic → script (Claude) → cloned narration (Chatterbox) →
retimed + captioned video (ffmpeg) → private YouTube upload.

This is **v1**: you record the screen actions yourself, following the
generated script, and the pipeline retimes that recording to match the
narration and assembles the final video. v2 will drive the on-screen
actions (terminal/browser) automatically, timed to each narration segment,
so recording stops being manual.

## Setup

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:
- `ANTHROPIC_API_KEY` — for script generation.
- `TTS_DEVICE` — `mps` on Apple Silicon (default), `cuda`, or `cpu`.

### Clone your voice

Record a clean 5-15s clip of yourself talking (quiet room, no music/echo,
normal pace) and save it as `assets/voice_reference/sample.wav`. Chatterbox
uses this for zero-shot voice cloning on every line of narration — no
training step needed.

### YouTube upload setup

1. In Google Cloud Console, create a project (or reuse one), enable the
   **YouTube Data API v3**, and create an **OAuth client ID** of type
   "Desktop app".
2. Download the client secret JSON and save it as `client_secret.json` in
   the repo root (gitignored).
3. The first time you run `publish` or `run`, a browser window opens for you
   to sign in and grant upload access; the resulting token is cached in
   `token.json` (gitignored) for future runs.

Uploads are always `private` or `unlisted` — the code refuses
`privacy_status="public"`. Review the video in YouTube Studio and flip
visibility yourself when you're ready to ship it.

## Usage

Full pipeline:

```bash
# 1. Generate the script first, so you know what to record
python -m voicestudio.cli script --topic "automating your inbox with n8n" --out output/script.json

# 2. Record your screen following output/script.json, save as recordings/demo.mp4

# 3. Run the rest of the pipeline (narration -> assemble -> private upload)
python -m voicestudio.cli run --topic "automating your inbox with n8n" --recording recordings/demo.mp4
```

Or step by step:

```bash
python -m voicestudio.cli script   --topic "..." --out output/script.json
python -m voicestudio.cli narrate  --script output/script.json --out-dir output/audio
python -m voicestudio.cli assemble --segments output/audio/segments.json --recording recordings/demo.mp4
python -m voicestudio.cli publish  --video output/final.mp4 --script output/script.json --privacy private
```

## Layout

```
voicestudio/
  script_gen.py   topic -> structured script (Claude API)
  voice.py        Chatterbox voice cloning -> per-segment narration wavs
  captions.py     segment timings -> SRT
  assemble.py     ffmpeg: retime recording to narration, mux, burn captions
  publish.py      YouTube upload (private/unlisted only)
  pipeline.py     orchestrates the above
  cli.py          command-line entry point
assets/voice_reference/   your voice sample (gitignored)
recordings/               your screen recordings (gitignored)
output/                   generated audio/video/scripts (gitignored)
```
