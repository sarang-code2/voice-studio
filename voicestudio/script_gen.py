"""Turn a tutorial topic into a structured script: narration segments paired
with the on-screen action each segment describes."""

import json
import os

from anthropic import Anthropic

from .config import Config

DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")

SYSTEM_PROMPT = """You write scripts for a YouTube tutorial channel about \
automation. Given a topic, produce a JSON script for a screen-recorded \
walkthrough where a narrator explains each step while the viewer's screen \
shows it happening.

The job is to teach the concept properly, not just narrate a list of \
clicks. A viewer who only watches (doesn't copy commands) should still \
come away understanding *why* this works, not just *what* was typed.

Output ONLY valid JSON (no markdown fences, no commentary) matching this \
shape:
{
  "title": "video title, <70 chars",
  "description": "1-2 paragraph YouTube description",
  "tags": ["tag1", "tag2", ...],
  "segments": [
    {
      "id": 1,
      "narration": "what the narrator says during this segment, plain \
spoken sentences, no stage directions",
      "action_type": "terminal" | "browser" | "concept" | "note",
      "action_detail": "the exact command to run, or the exact URL/click \
path to follow, or empty string for 'concept'/'note' segments"
    }
  ]
}

Rules:
- Segments should be short (1-3 sentences of narration each) so they map \
cleanly to individual on-screen actions.
- Before any "terminal"/"browser" steps, include one or more "concept" \
segments that genuinely teach the underlying idea: what problem it solves, \
why this approach works, the mental model. This is the pedagogical core of \
the video -- give it real substance (a concrete example or analogy), not a \
single throwaway sentence. Add more "concept" segments mid-script wherever \
a step needs the "why" explained before the "how".
- Use "note" only for pure framing lines (hook, transition, recap) that \
don't teach anything by themselves -- "concept" is for actual teaching.
- action_detail for "terminal" must be a literal shell command that can be \
run as-is. Each terminal segment runs in its own fresh shell subprocess --
there is no persistent state (cwd, variables) between segments, so never \
rely on a "cd" from an earlier segment; use absolute paths, or chain with \
"&&" within a single action_detail.
- action_detail for "browser" must be a literal URL or a short imperative \
description of the click/type steps (e.g. "open https://x.com, click \
Settings, toggle Dark Mode").
- Start with a short "note" segment (hook/intro) and end with a short \
"note" segment (recap/outro)."""


def generate_script(topic: str, config: Config) -> dict:
    if not config.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set (see .env.example)")

    client = Anthropic(api_key=config.anthropic_api_key)
    message = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Topic: {topic}"}],
    )

    raw = "".join(
        block.text for block in message.content if block.type == "text"
    ).strip()

    try:
        script = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model did not return valid JSON:\n{raw}") from e

    for key in ("title", "description", "tags", "segments"):
        if key not in script:
            raise ValueError(f"Script is missing required key '{key}': {script}")

    return script
