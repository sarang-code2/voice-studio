"""Chatterbox wrapper: clone the configured voice and synthesize narration
audio for each script segment."""

import json
from pathlib import Path

import torchaudio as ta
from chatterbox.tts import ChatterboxTTS

from .config import Config

_model = None


def _get_model(config: Config):
    global _model
    if _model is None:
        _model = ChatterboxTTS.from_pretrained(device=config.tts_device)
    return _model


def synthesize_segments(script: dict, config: Config, out_dir: Path) -> dict:
    """Generate one WAV per segment. Writes segments.json to out_dir and
    returns {"sample_rate": int, "segments": [...]} with audio_path and
    duration_s added to each segment."""
    reference = config.require_voice_reference()
    model = _get_model(config)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for segment in script["segments"]:
        wav = model.generate(segment["narration"], audio_prompt_path=str(reference))
        path = out_dir / f"{segment['id']:03d}.wav"
        ta.save(str(path), wav, model.sr)
        duration_s = wav.shape[-1] / model.sr
        results.append({**segment, "audio_path": str(path), "duration_s": duration_s})

    output = {"sample_rate": model.sr, "segments": results}
    with open(out_dir / "segments.json", "w") as f:
        json.dump(output, f, indent=2)

    return output
