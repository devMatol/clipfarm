from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


def deduplicate_words(words: list[dict[str, Any]], tolerance: float = 0.05) -> list[dict[str, Any]]:
    """Dédoublonne strictement une liste de mots par proximité temporelle."""
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: float(w["start"]))
    deduped: list[dict[str, Any]] = [sorted_words[0]]
    for w in sorted_words[1:]:
        last = deduped[-1]
        # Si le mot a un départ quasi identique (< tolerance)
        if abs(float(w["start"]) - float(last["start"])) < tolerance:
            # S'ils ont le même texte, on ignore le doublon
            if w.get("text", "").strip().lower() == last.get("text", "").strip().lower():
                continue
            # Si le texte diffère, on privilégie le plus long/pertinent
            if len(w.get("text", "").strip()) > len(last.get("text", "").strip()):
                deduped[-1] = w
            continue
        deduped.append(w)
    return deduped


def resolve_clip_words(
    pdir: Path,
    clip_index: int,
    start: float,
    end: float,
    custom_words: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    """
    Résout et fusionne proprement la liste des mots pour l'intervalle [start, end].
    - Priorité absolue aux corrections utilisateur (custom_words ou clip_{index}_words.json).
    - Ajoute les mots maîtres de words.json si la plage [start, end] s'étend au-delà.
    - Dédoublonne strictement pour éviter tout décalage ou mot dupliqué.
    """
    from clipfarm_engine.transcribe.speech import load_words

    # 1. Charger la transcription globale
    words_path = pdir / "words.json"
    master_words = load_words(words_path) if words_path.exists() else []

    # 2. Mots maîtres dans l'intervalle [start, end]
    in_range_master = [
        {
            "start": float(w.start),
            "end": float(w.end),
            "text": str(w.text).strip(),
            "prob": float(w.prob),
        }
        for w in master_words
        if w.start >= (start - 0.05) and w.end <= (end + 0.05) and str(w.text).strip()
    ]

    # 3. Charger les éventuels mots personnalisés existants
    existing_custom: list[dict[str, Any]] = []
    if custom_words is not None:
        existing_custom = custom_words
    else:
        custom_words_path = pdir / f"clip_{clip_index}_words.json"
        if custom_words_path.exists():
            try:
                existing_custom = json.loads(custom_words_path.read_text(encoding="utf-8"))
            except Exception:
                existing_custom = []

    # Si aucun mot personnalisé, on renvoie directement les mots maîtres dédoublonnés
    if not existing_custom:
        return deduplicate_words(in_range_master)

    # 4. Filtrer les custom_words dans [start, end]
    filtered_custom = [
        {
            "start": float(w["start"]),
            "end": float(w["end"]),
            "text": str(w.get("text") or w.get("word") or "").strip(),
            "prob": float(w.get("prob") or w.get("score") or 1.0),
        }
        for w in existing_custom
        if float(w["start"]) >= (start - 0.05) and float(w["end"]) <= (end + 0.05) and str(w.get("text") or w.get("word") or "").strip()
    ]

    if not filtered_custom:
        return deduplicate_words(in_range_master)

    # Vérifier si la plage a été étendue au-delà des bornes des custom_words
    custom_min_start = min(w["start"] for w in filtered_custom)
    custom_max_end = max(w["end"] for w in filtered_custom)

    extra_master = [
        mw for mw in in_range_master
        if mw["start"] < (custom_min_start - 0.05) or mw["end"] > (custom_max_end + 0.05)
    ]

    combined = filtered_custom + extra_master
    return deduplicate_words(combined)


def regenerate_clip_words(
    pdir: Path,
    clip_index: int,
    start: float,
    end: float,
    mode: str = "reset",
) -> list[dict[str, Any]]:
    """
    Regénère les sous-titres d'un clip.
    - mode == "reset" : supprime clip_{clip_index}_words.json et recharge words.json.
    - mode == "whisper" : exécute Whisper sur le segment audio spécifique [start, end].
    """
    custom_words_path = pdir / f"clip_{clip_index}_words.json"
    if custom_words_path.exists():
        try:
            custom_words_path.unlink()
        except Exception:
            pass

    if mode == "whisper":
        import subprocess
        from clipfarm_engine.config import Settings
        from clipfarm_engine.transcribe.speech import transcribe

        audio_src = pdir / "audio.wav"
        if not audio_src.exists():
            vocal_path = pdir / "voice" / "vocals.wav"
            if vocal_path.exists():
                audio_src = vocal_path

        if audio_src.exists():
            segment_wav = pdir / f"clip_{clip_index}_retranscribe.wav"
            try:
                duration = max(0.5, end - start)
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start),
                    "-t", str(duration),
                    "-i", str(audio_src),
                    "-ar", "16000", "-ac", "1",
                    str(segment_wav),
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                s = Settings()
                raw_words = transcribe(segment_wav, s)
                re_words = [
                    {
                        "start": round(start + float(w.start), 2),
                        "end": round(start + float(w.end), 2),
                        "text": str(w.text).strip(),
                        "prob": float(w.prob),
                    }
                    for w in raw_words
                    if str(w.text).strip()
                ]
                if re_words:
                    clean_words = deduplicate_words(re_words)
                    custom_words_path.write_text(json.dumps(clean_words, ensure_ascii=False, indent=2), encoding="utf-8")
                    return clean_words
            except Exception as exc:
                print(f"[regenerate_clip_words] Whisper retranscription échouée ({exc}), repli sur words.json")
            finally:
                if segment_wav.exists():
                    try:
                        segment_wav.unlink()
                    except Exception:
                        pass

    # mode == "reset" ou repli
    clean_words = resolve_clip_words(pdir, clip_index, start, end)
    custom_words_path.write_text(json.dumps(clean_words, ensure_ascii=False, indent=2), encoding="utf-8")
    return clean_words
