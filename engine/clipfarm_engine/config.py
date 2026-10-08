"""Settings read from environment variables (see .env.example at the repo root)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def load_dotenv(start: Path | None = None) -> None:
    """Minimal .env loader (no dependency): first .env found from cwd upwards. Real env vars win."""
    here = (start or Path.cwd()).resolve()
    for folder in (here, *here.parents):
        f = folder / ".env"
        if f.is_file():
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            os.environ.setdefault("CLIPFARM_ROOT", str(folder))
            return


load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _data_dir() -> Path:
    p = Path(_env("CLIPFARM_DATA_DIR", "data"))
    if not p.is_absolute():
        p = Path(_env("CLIPFARM_ROOT", str(Path.cwd()))) / p
    return p.resolve()


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: _data_dir())
    language: str = field(default_factory=lambda: _env("CLIPFARM_LANGUAGE", "fr"))

    # Transcription
    whisper_model: str = field(default_factory=lambda: _env("WHISPER_MODEL", "large-v3-turbo"))
    whisper_device: str = field(default_factory=lambda: _env("WHISPER_DEVICE", "cuda"))
    whisper_compute_type: str = field(default_factory=lambda: _env("WHISPER_COMPUTE_TYPE", "float16"))
    isolate_voice: bool = field(default_factory=lambda: _env("ISOLATE_VOICE", "1") == "1")
    hf_token: str = field(default_factory=lambda: _env("HF_TOKEN"))

    # LLM used to pick highlights: "ollama", "gemini" or "none" (signals only)
    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "ollama"))
    ollama_url: str = field(default_factory=lambda: _env("OLLAMA_URL", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: _env("OLLAMA_MODEL", "qwen3:8b"))
    gemini_api_key: str = field(default_factory=lambda: _env("GEMINI_API_KEY"))
    gemini_model: str = field(default_factory=lambda: _env("GEMINI_MODEL", "gemini-2.5-flash"))

    # Clip constraints
    min_clip_s: float = field(default_factory=lambda: float(_env("MIN_CLIP_S", "30")))
    max_clip_s: float = field(default_factory=lambda: float(_env("MAX_CLIP_S", "70")))
    max_clips: int = field(default_factory=lambda: int(_env("MAX_CLIPS", "8")))

    def project_dir(self, project_id: str) -> Path:
        p = self.data_dir / "projects" / project_id
        p.mkdir(parents=True, exist_ok=True)
        return p
