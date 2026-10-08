"""Speech pipeline: optional voice isolation, word-level transcription, optional diarization.

Heavy libraries are imported lazily so the rest of the engine (and the tests)
run without a GPU stack installed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ..captions.ass import Word
from ..config import Settings

INITIAL_PROMPT_FR = "Transcription d'un streamer francais qui parle, reagit, rigole et commente en direct."


def isolate_voice(wav: Path, out_dir: Path) -> Path:
    """Demucs two-stem split: keeps the human voice, drops game music and effects."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", "htdemucs", "-o", str(out_dir), str(wav)]
    subprocess.run(cmd, check=True)
    vocals = out_dir / "htdemucs" / wav.stem / "vocals.wav"
    if not vocals.exists():
        raise FileNotFoundError(vocals)
    return vocals


def _with_whisperx(audio: Path, s: Settings) -> list[Word]:
    import torchaudio
    if not hasattr(torchaudio, "AudioMetaData"):
        from dataclasses import dataclass
        @dataclass
        class _AudioMetaData:
            sample_rate: int = 16000
            num_frames: int = 0
            num_channels: int = 1
            bits_per_sample: int = 16
            encoding: str = "PCM_S"
        torchaudio.AudioMetaData = _AudioMetaData

    import whisperx  # type: ignore

    model = whisperx.load_model(s.whisper_model, s.whisper_device, compute_type=s.whisper_compute_type,
                                language=s.language, asr_options={"initial_prompt": INITIAL_PROMPT_FR})
    data = whisperx.load_audio(str(audio))
    result = model.transcribe(data, batch_size=16, language=s.language)
    align_model, meta = whisperx.load_align_model(language_code=s.language, device=s.whisper_device)
    result = whisperx.align(result["segments"], align_model, meta, data, s.whisper_device, return_char_alignments=False)
    if s.hf_token:
        try:
            from whisperx.diarize import DiarizationPipeline  # type: ignore
            diar = DiarizationPipeline(use_auth_token=s.hf_token, device=s.whisper_device)
            result = whisperx.assign_word_speakers(diar(data), result)
        except Exception as exc:  # diarization is a bonus, never block the pipeline
            print(f"[speech] diarisation ignoree: {exc}")
    words: list[Word] = []
    for seg in result["segments"]:
        for w in seg.get("words", []):
            if "start" in w and "end" in w and w.get("word", "").strip():
                words.append(Word(float(w["start"]), float(w["end"]), w["word"].strip(), float(w.get("score", 1.0)), w.get("speaker")))
    return words


def _with_faster_whisper(audio: Path, s: Settings) -> list[Word]:
    from faster_whisper import WhisperModel  # type: ignore

    model = WhisperModel(s.whisper_model, device=s.whisper_device, compute_type=s.whisper_compute_type)
    segments, _ = model.transcribe(str(audio), language=s.language, word_timestamps=True, vad_filter=True,
                                   condition_on_previous_text=False, beam_size=5, initial_prompt=INITIAL_PROMPT_FR)
    return [Word(w.start, w.end, w.word.strip(), w.probability) for seg in segments for w in (seg.words or []) if w.word.strip()]


def transcribe(audio: Path, s: Settings, min_prob: float = 0.25) -> list[Word]:
    try:
        words = _with_whisperx(audio, s)
    except Exception as exc:
        print(f"[speech] WhisperX indisponible ({exc}), bascule sur faster-whisper")
        words = _with_faster_whisper(audio, s)
    return [w for w in words if w.prob >= min_prob]


def save_words(words: list[Word], path: Path) -> None:
    path.write_text(json.dumps([w.__dict__ for w in words], ensure_ascii=False, indent=0), encoding="utf-8")


def load_words(path: Path) -> list[Word]:
    return [Word(**d) for d in json.loads(path.read_text(encoding="utf-8"))]
