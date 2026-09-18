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
      "action_type": "terminal" | "browser" | "note",
      "action_detail": "the exact command to run, or the exact URL/click \
path to follow, or empty string if action_type is 'note' (a segment with \
no on-screen action, e.g. an intro/outro/explanation)"
    }
  ]
}

Rules:
- Segments should be short (1-3 sentences of narration each) so they map \
cleanly to individual on-screen actions.
- action_detail for "terminal" must be a literal shell command that can be \
run as-is.
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
