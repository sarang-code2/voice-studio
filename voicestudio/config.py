import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    voice_reference_path: Path
    tts_device: str
    llm_backend: str = "anthropic"
    output_dir: Path = ROOT / "output"
    recordings_dir: Path = ROOT / "recordings"

    def require_voice_reference(self) -> Path:
        if not self.voice_reference_path.exists():
            raise FileNotFoundError(
                f"No voice reference clip at {self.voice_reference_path}. "
                "Record a 5-15s clean clip of your voice and save it there "
                "(see README: 'Clone your voice')."
            )
        return self.voice_reference_path


def load_config() -> Config:
    return Config(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        voice_reference_path=ROOT / os.environ.get(
            "VOICE_REFERENCE_PATH", "assets/voice_reference/sample.wav"
        ),
        tts_device=os.environ.get("TTS_DEVICE", "mps"),
        llm_backend=os.environ.get("LLM_BACKEND", "anthropic"),
    )
