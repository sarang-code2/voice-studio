# voice-studio

Turns a tutorial topic into a narrated, captioned video in your own cloned
voice, and uploads it to YouTube as private/unlisted for review.

**Pipeline:** topic → script (Claude) → cloned narration (Chatterbox) →
screen capture → assembled + captioned video (ffmpeg) → private YouTube
upload.

Two ways to get the screen capture:
- **Automated** (`--auto-capture`): "terminal" segments are captured for
  real -- the command actually runs, its real output is rendered as a
  typing-animation clip. "concept"/"note" segments (and "browser"/"mobile"/
  "desktop" segments, until those backends exist) render as a title card.
  No manual recording needed.
- **Manual** (`--recording <file>`): v1 fallback -- you record your screen
  yourself following the script, and the pipeline retimes it to match the
  narration.

### Current status of the four capture targets

| Target | Status |
|---|---|
| Terminal / CLI | Automated -- commands really run, real output rendered |
| Browser web app | Not yet -- renders as a title card placeholder |
| Mobile (simulator) | Not yet -- renders as a title card placeholder |
| Real desktop apps | Not yet -- renders as a title card placeholder |

(Tried Charm's VHS for terminal capture first; it renders unreliably in
this environment -- Chrome/ttyd spawn but no output file ever gets
written -- so terminal capture is a self-contained Pillow+ffmpeg renderer
instead, no headless-browser dependency.)

### Current status of "animations"

- **Concept segments teach, not just narrate.** `script_gen.py` requires
  the model to include real "concept" segments (motivation, mental model,
  why it works) before any "terminal"/"browser" steps -- not just a list of
  commands.
- **Concept/note segments render as fade-in title cards** (`visuals.py`).
  This is a functional placeholder, not the eventual richer motion
  graphics/diagrams -- that's a later phase.
- **Captions are a soft subtitle track** (`mov_text`, toggleable), not
  burned in -- this Homebrew ffmpeg build has no `libass`.
- Not yet built: cursor highlight/zoom, animated callout boxes,
  intro/outro cards as a distinct feature (today the script's own
  intro/outro "note" segments already render as title cards, which covers
  this reasonably well).

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

If the clip has any background noise/compression artifacts (e.g. pulled
from an existing video), denoise it first -- noisy references produce
noisy/scratchy clones:

```bash
ffmpeg -i raw_clip.wav -af "afftdn=nf=-30,loudnorm=I=-18:TP=-2:LRA=7" \
  -ar 24000 -ac 1 assets/voice_reference/sample.wav
```

### YouTube upload setup

1. In Google Cloud Console, create a project (or reuse one), enable the
   **YouTube Data API v3**, and create an **OAuth client ID** of type
   "Desktop app".
2. Download the client secret JSON and save it as `client_secret.json` in
   the repo root (gitignored).
3. The first time you run `publish` or `run` (without `--no-upload`), a
   browser window opens for you to sign in and grant upload access; the
   resulting token is cached in `token.json` (gitignored) for future runs.

Uploads are always `private` or `unlisted` — the code refuses
`privacy_status="public"`. Review the video in YouTube Studio and flip
visibility yourself when you're ready to ship it.

**Caution:** `capture`/`run --auto-capture` actually executes every
"terminal" segment's command on your machine via subprocess. Review
`script.json`'s `action_detail` fields before running it -- `capture`
prints every terminal command it's about to run first.

## Usage

Full pipeline, automated capture, no upload (review locally first):

```bash
python -m voicestudio.cli run --topic "organizing downloads with bash" \
  --auto-capture --no-upload
```

Full pipeline with manual recording + upload:

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
python -m voicestudio.cli capture  --segments output/audio/segments.json          # automated path
python -m voicestudio.cli assemble --segments output/audio/segments.json          # uses output/clips by default
# -- or, manual recording path --
python -m voicestudio.cli assemble --segments output/audio/segments.json --recording recordings/demo.mp4
python -m voicestudio.cli publish  --video output/final.mp4 --script output/script.json --privacy private
```

## Layout

```
voicestudio/
  script_gen.py   topic -> structured script (Claude API), teaches concepts not just steps
  voice.py        Chatterbox voice cloning -> per-segment narration wavs
  captions.py     segment timings -> SRT
  render.py       shared Pillow/ffmpeg frame-rendering helpers
  capture.py      automated per-segment capture: real terminal execution, or a title card
  visuals.py      fade-in title-card clips (concept/note segments, capture placeholders)
  assemble.py     ffmpeg: concat clips (or retime a manual recording), mux, soft captions
  publish.py      YouTube upload (private/unlisted only)
  pipeline.py     orchestrates the above
  cli.py          command-line entry point
assets/voice_reference/   your voice sample (gitignored)
recordings/               your manual screen recordings, v1 path (gitignored)
demo_workspace/           scratch space used by demo terminal commands (gitignored)
output/                   generated audio/video/scripts/clips (gitignored)
```
