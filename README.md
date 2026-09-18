# voice-studio

Turns a tutorial topic into a narrated video in your own cloned voice, with
real terminal capture and animated concept diagrams, and (optionally)
uploads it to YouTube as private/unlisted for review.

**Pipeline:** topic → script (Claude or a local Ollama model) → cloned
narration (Chatterbox) → screen capture → assembled video (ffmpeg) →
private/unlisted YouTube upload.

## What it actually does

- **Real terminal capture.** "terminal" segments aren't staged -- the
  command actually runs via subprocess on your machine, and its real
  output gets rendered into a typing-animation clip inside an actual-looking
  terminal window (title bar, traffic lights, jittered human-paced typing,
  real scroll-back when content exceeds the window -- old lines roll off
  the top instead of overflowing).
- **Concept segments that teach, with animated diagrams.** The script
  generator is required to explain *why* something works, not just narrate
  a list of commands. When an idea is a sequence of steps, it also gets an
  animated box-and-arrow diagram (`diagram.py`) instead of plain text.
- **Two script-generation backends:** Anthropic's API (needs
  `ANTHROPIC_API_KEY` + a funded console account) or a free local model via
  **Ollama** (`LLM_BACKEND=ollama`, no billing, runs entirely on your
  machine -- noticeably rougher quality, review the script before running
  `capture`).
- **Landscape or portrait/reel output** (`--format landscape|portrait`),
  same pipeline. Portrait scripts are capped at ~60s narration.
- **No caption text duplicated on screen.** `captions.py` still writes a
  standalone `output/captions.srt` (e.g. to upload separately to YouTube),
  but nothing is burned into or muxed onto the video itself.
- **Never auto-publishes as public.** `publish.py` refuses
  `privacy_status="public"` at the code level -- uploads are always
  private/unlisted; you flip visibility yourself in YouTube Studio.

Two ways to get the screen capture:
- **Automated** (`--auto-capture`): described above. "concept"/"note"
  segments (and "browser"/"mobile"/"desktop" segments, until those capture
  backends exist) render as a title card / diagram instead.
- **Manual** (`--recording <file>`): v1 fallback -- you record your screen
  yourself following the script, and the pipeline retimes it to match the
  narration.

### Current status of the four capture targets

| Target | Status |
|---|---|
| Terminal / CLI | Automated -- commands really run, real output rendered, real scrolling |
| Browser web app | Not yet -- renders as a title card placeholder |
| Mobile (simulator) | Not yet -- renders as a title card placeholder |
| Real desktop apps | Not yet -- renders as a title card placeholder |

(Tried Charm's VHS for terminal capture first; it renders unreliably in
this environment -- Chrome/ttyd spawn but no output file ever gets
written -- so terminal capture is a self-contained Pillow+ffmpeg renderer
instead, no headless-browser dependency.)

Not yet built: cursor highlight/zoom, animated callout boxes, richer
motion graphics beyond the step-diagram (e.g. Manim-style explainers).

## Setup

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg
cp .env.example .env
```

Fill in `.env` (see `.env.example` for every option):
- `LLM_BACKEND` — `anthropic` (default) or `ollama`.
- `ANTHROPIC_API_KEY` — only if using the Anthropic backend. Get one at
  [console.anthropic.com](https://console.anthropic.com) (separate
  account/billing from a Claude subscription).
- `OLLAMA_MODEL` / `OLLAMA_HOST` — only if using the Ollama backend.
  Needs `ollama serve` running and a model pulled, e.g.
  `ollama pull llama3.2`.
- `TTS_DEVICE` — `mps` on Apple Silicon (default), `cuda`, or `cpu`.

`.env` is gitignored and never committed -- don't share it if you fork or
hand off this repo. Nothing in this repo's git history has ever contained
a real key.

### Clone your voice

Record a clean 5-15s clip of yourself talking (quiet room, no music/echo,
normal pace) and save it as `assets/voice_reference/sample.wav`. Chatterbox
uses this for zero-shot voice cloning on every line of narration -- no
training step needed. This file is gitignored (private by default).

A couple of real failure modes worth knowing about, found the hard way:

- **Noisy/compressed source (e.g. pulled from an existing video):**
  denoise it first, or the clone inherits the noise as an audible
  scratch/crackle:
  ```bash
  ffmpeg -i raw_clip.wav -af "afftdn=nf=-30,loudnorm=I=-18:TP=-2:LRA=7" \
    -ar 24000 -ac 1 assets/voice_reference/sample.wav
  ```
- **Recorded too quiet:** check levels before using a fresh recording --
  a clip with a good peak but very low RMS (~-35dB) will clone as
  unpleasantly quiet. Boost it to a healthy level (peak around -3dB, RMS
  around -20dB):
  ```bash
  ffprobe -v error -show_entries format=duration -i sample.wav  # sanity check
  ffmpeg -i raw_clip.wav -af "volume=+13dB" -ar 24000 -ac 1 assets/voice_reference/sample.wav
  ```
  (Chatterbox's raw output also isn't peak-safe -- `voice.py` clips
  generated audio to a safe ceiling before saving, regardless of input
  level.)

### YouTube upload setup (optional -- skip if you only want local files)

1. In Google Cloud Console, create a project (or reuse one), enable the
   **YouTube Data API v3**, and create an **OAuth client ID** of type
   "Desktop app".
2. Download the client secret JSON and save it as `client_secret.json` in
   the repo root (gitignored).
3. The first time you run `publish` or `run` (without `--no-upload`), a
   browser window opens for you to sign in and grant upload access; the
   resulting token is cached in `token.json` (gitignored) for future runs.

Uploads are always `private` or `unlisted` -- the code refuses
`privacy_status="public"`. Review the video in YouTube Studio and flip
visibility yourself when you're ready to ship it.

**Caution:** `capture`/`run --auto-capture` actually executes every
"terminal" segment's command on your machine via subprocess. Review
`script.json`'s `action_detail` fields before running it -- `capture`
prints every terminal command it's about to run first.

## Usage

Full pipeline, automated capture, landscape, no upload (review locally
first -- recommended the first few times):

```bash
python -m voicestudio.cli run --topic "how git bisect finds the commit that broke your code" \
  --auto-capture --no-upload --format landscape
```

Same, but as a vertical Reel/Short:

```bash
python -m voicestudio.cli run --topic "..." --auto-capture --no-upload --format portrait
```

Output lands at `output/final.mp4`, alongside `output/script.json` (the
generated script -- always review this before letting `capture` run, since
it contains the real commands about to execute) and `output/captions.srt`.

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
python -m voicestudio.cli script   --topic "..." --out output/script.json --format landscape
python -m voicestudio.cli narrate  --script output/script.json --out-dir output/audio
python -m voicestudio.cli capture  --segments output/audio/segments.json --format landscape   # automated path
python -m voicestudio.cli assemble --segments output/audio/segments.json --format landscape    # uses output/clips by default
# -- or, manual recording path --
python -m voicestudio.cli assemble --segments output/audio/segments.json --recording recordings/demo.mp4
python -m voicestudio.cli publish  --video output/final.mp4 --script output/script.json --privacy private
```

## Layout

```
voicestudio/
  script_gen.py   topic -> structured script (Anthropic API or local Ollama), teaches concepts not just steps
  voice.py        Chatterbox voice cloning -> per-segment narration wavs, peak-limited
  captions.py     segment timings -> standalone SRT (not attached to the video)
  render.py       shared Pillow/ffmpeg frame-rendering helpers, landscape/portrait dimensions
  capture.py      automated per-segment capture: real terminal execution (with scroll-back), or a diagram/title card
  diagram.py      animated box-and-arrow flow diagrams for concept segments
  visuals.py      fade-in title-card clips (note segments, capture placeholders)
  assemble.py     ffmpeg: concat clips (or retime a manual recording), mux -- pads video to match narration exactly
  publish.py      YouTube upload (private/unlisted only, enforced in code)
  pipeline.py     orchestrates the above, writes script.json to disk
  cli.py          command-line entry point
assets/voice_reference/   your voice sample (gitignored)
recordings/               your manual screen recordings, v1 path (gitignored)
demo_workspace/           scratch space used by demo terminal commands (gitignored)
output/                   generated audio/video/scripts/clips (gitignored)
```

## Known limitations

- Browser/mobile/desktop capture backends don't exist yet -- those
  segments render as a title card.
- The Ollama backend is meaningfully less reliable than Claude at
  following the schema and writing good teaching content -- always review
  `output/script.json` before trusting it, especially before `capture` runs
  real commands from it.
- Terminal capture executes real shell commands. There is no sandboxing --
  review every generated script before running `capture` on a topic you
  didn't write yourself.
