"""Ask an LLM (local Ollama by default, or Gemini free tier) to pick the best moments.

Supports:
1. Signal tags ([CRI], [RIRE], [SILENCE >3s], [ACTION]) in transcript lines.
2. Two-pass selection:
   - Pass 1: generates 3x more candidates per chunk with summaries.
   - Pass 2: global evaluation of all candidates with summaries & transcript context.
3. Video context (title and description) in prompts.
4. Custom few-shot examples loaded from data/exemples/.
5. Fast Gemini long-context support.
"""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from ..captions.ass import Word
from ..config import Settings
from .signals import Signals


@dataclass
class Candidate:
    start: float
    end: float
    title: str = ""
    hook: str = ""
    reason: str = ""
    summary: str = ""
    scores: dict[str, float] = field(default_factory=dict)
    llm_score: float = 0.0     # 0..1
    signal_score: float = 0.0  # 0..1
    final_score: float = 0.0

    def to_dict(self) -> dict:
        return self.__dict__.copy()


CLIP_SCHEMA_PASS1 = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "title": {"type": "string"},
                    "hook": {"type": "string"},
                    "summary": {"type": "string"},
                    "reason": {"type": "string"},
                    "scores": {
                        "type": "object",
                        "properties": {k: {"type": "number"} for k in ("hook", "emotion", "payoff", "standalone")},
                        "required": ["hook", "emotion", "payoff", "standalone"],
                    },
                },
                "required": ["start", "end", "title", "hook", "summary", "reason", "scores"],
            },
        }
    },
    "required": ["clips"],
}

CLIP_SCHEMA_PASS2 = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "title": {"type": "string"},
                    "hook": {"type": "string"},
                    "reason": {"type": "string"},
                    "scores": {
                        "type": "object",
                        "properties": {k: {"type": "number"} for k in ("hook", "emotion", "payoff", "standalone")},
                        "required": ["hook", "emotion", "payoff", "standalone"],
                    },
                },
                "required": ["start", "end", "title", "hook", "reason", "scores"],
            },
        }
    },
    "required": ["clips"],
}


TAGS_EXPLANATION = """Balises de detection dans la transcription :
- [CRI] : volume sonore qui depasse la moyenne (+1.5 ecart-type) : cri, reaction forte, hurlement
- [RIRE] : rire detecte dans la voix ou pics d'energie haches
- [SILENCE >3s] : silence ou pause de plus de 3 secondes avant cette parole
- [ACTION] : changements de plan rapides (rythme visuel soutenu)
Prete une attention particuliere aux passages contenant [CRI], [RIRE] ou [ACTION] pour detecter les moments forts !"""


PROMPT_PASS1 = """Tu es un monteur expert en clips courts viraux (TikTok, Shorts, Reels).
Voici un extrait de transcription horodatee (en secondes) d'une video.
{context_block}

{TAGS_EXPLANATION}

{examples_block}

Propose les {n} MEILLEURS moments candidats de cette section.
Criteres :
- hook : les 3 premieres secondes captivent immediatement
- emotion : reaction forte, rire, surprise, colere, punchline
- payoff : la chute ou la conclusion du moment arrive dans le clip
- standalone : comprehensible sans regarder toute la video
- duree entre {min_s:.0f} et {max_s:.0f} secondes (idealement {ideal_s:.0f}s)
- inclus IMPERATIVEMENT la mise en place (ce qui se passe juste avant la reaction) ET la chute
- start au debut d'une phrase, end a la fin d'une phrase
- title : titre court et percutant en francais (max 60 car.)
- hook : texte d'accroche pour le haut de l'ecran (max 40 car.)
- summary : resume en 1 phrase expliquant la situation, la mise en place et la reaction
- scores : notes de 0 a 10 pour chaque critere

Reponds uniquement en JSON strict selon ce schema :
{{"clips": [{{"start": 0, "end": 0, "title": "", "hook": "", "summary": "", "reason": "", "scores": {{"hook": 0, "emotion": 0, "payoff": 0, "standalone": 0}}}}]}}

Transcription :
{transcript}
"""


PROMPT_PASS2 = """Tu es le monteur en chef. Voici une pre-selection de candidats extraits de l'ensemble d'une video.
{context_block}

Parmi cette liste de candidats potentiels, selectionne et classe les {n_final} MEILLEURS moments absolus a monter en clips verticaux.

Regles strictes de selection :
1. Duree entre {min_s:.0f} et {max_s:.0f} secondes.
2. Inclus la mise en place (contexte de depart) ET la chute/reaction.
3. AUCUN CHEVAUCHEMENT entre les clips selectionnes (ecart minimum de 10 secondes si possible).
4. Variete : choisis les moments les plus intenses, surprenants ou droles de la video.
5. Perfectionne le title et le hook de chaque clip retenu.
6. Classe-les du MEILLEUR au MOINS BON.

Reponds uniquement en JSON strict :
{{"clips": [{{"start": 0, "end": 0, "title": "", "hook": "", "reason": "", "scores": {{"hook": 0, "emotion": 0, "payoff": 0, "standalone": 0}}}}]}}

Candidats pre-selectionnes :
{candidates_text}
"""


def load_examples(dir_path: Path | None = None, max_examples: int = 5) -> list[dict]:
    """Load up to `max_examples` reference clips from data/exemples/."""
    if dir_path is None:
        dir_path = Path("data/exemples")
    if not dir_path.is_dir():
        return []

    examples = []
    for f in sorted(dir_path.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "title" in data:
                examples.append(data)
                if len(examples) >= max_examples:
                    break
        except Exception:
            continue
    return examples


def format_examples_block(examples: list[dict]) -> str:
    if not examples:
        return ""
    lines = ["Exemples de moments parfaits de reference :"]
    for i, ex in enumerate(examples, 1):
        lines.append(f"Exemple #{i} :")
        lines.append(f"- Titre : {ex.get('title', '')}")
        if ex.get("hook"):
            lines.append(f"- Hook : {ex.get('hook', '')}")
        if ex.get("why"):
            lines.append(f"- Pourquoi c'est reussi : {ex.get('why', '')}")
        if ex.get("reason"):
            lines.append(f"- Raison : {ex.get('reason', '')}")
        if ex.get("transcript"):
            lines.append(f"  Extrait :\n{ex.get('transcript', '')}")
    return "\n".join(lines)


def format_context_block(title: str = "", description: str = "") -> str:
    ctx = []
    if title:
        ctx.append(f"Titre de la video : {title}")
    if description:
        # Tronquer description pour preserver le contexte
        clean_desc = description.strip().replace("\n", " ")[:300]
        ctx.append(f"Description : {clean_desc}")
    return "\n".join(ctx) if ctx else ""


def transcript_lines(words: list[Word], max_words: int = 25, gap: float = 0.8) -> list[tuple[float, float, str]]:
    """Group words into sentence-like lines: (start, end, text)."""
    lines, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or w.start - cur[-1].end > gap):
            lines.append(cur)
            cur = []
        cur.append(w)
        if w.text[-1:] in ".?!":
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    return [(l[0].start, l[-1].end, " ".join(w.text for w in l)) for l in lines]


def annotate_lines(lines: list[tuple[float, float, str]], sig: Signals | None = None) -> list[tuple[float, float, str]]:
    """Enrich transcript lines with context tags: [CRI], [RIRE], [SILENCE >3s], [ACTION]."""
    if sig is None:
        return lines

    annotated = []
    for i, (start, end, text) in enumerate(lines):
        prev_end = lines[i - 1][1] if i > 0 else None
        tags = sig.detect_tags(start, end, prev_end)
        if tags:
            tag_str = " ".join(tags)
            annotated.append((start, end, f"{tag_str} {text}"))
        else:
            annotated.append((start, end, text))
    return annotated


def windows(lines: list[tuple[float, float, str]], size: float = 480.0, overlap: float = 60.0) -> list[list[tuple[float, float, str]]]:
    """Split a long transcript into overlapping chunks that fit a small model context."""
    if not lines:
        return []
    out, start, last = [], lines[0][0], lines[-1][1]
    while start < last:
        chunk = [l for l in lines if start <= l[0] < start + size]
        if chunk:
            out.append(chunk)
        start += size - overlap
    return out


def build_pass1_prompt(
    chunk: list[tuple[float, float, str]],
    n: int,
    s: Settings,
    title: str = "",
    description: str = "",
    examples: list[dict] | None = None,
) -> str:
    text = "\n".join(f"[{a:.1f}-{b:.1f}] {t}" for a, b, t in chunk)
    context_block = format_context_block(title, description)
    examples_block = format_examples_block(examples or [])
    ideal_s = (s.min_clip_s + s.max_clip_s) / 2
    return PROMPT_PASS1.format(
        n=n,
        min_s=s.min_clip_s,
        max_s=s.max_clip_s,
        ideal_s=ideal_s,
        context_block=context_block,
        TAGS_EXPLANATION=TAGS_EXPLANATION,
        examples_block=examples_block,
        transcript=text,
    )


def build_pass2_prompt(
    candidates: list[Candidate],
    lines: list[tuple[float, float, str]],
    n_final: int,
    s: Settings,
    title: str = "",
    description: str = "",
) -> str:
    context_block = format_context_block(title, description)
    cand_blocks = []
    for i, c in enumerate(candidates, 1):
        # Extraire les répliques correspondantes
        inside_lines = [l for l in lines if l[0] >= c.start - 2.0 and l[1] <= c.end + 2.0]
        snippet = "\n".join(f"  [{a:.1f}-{b:.1f}] {t}" for a, b, t in inside_lines[:6])
        cand_blocks.append(
            f"Candidat #{i} [{c.start:.1f}s - {c.end:.1f}s] (Duree: {c.end - c.start:.1f}s)\n"
            f"- Titre : {c.title}\n"
            f"- Hook : {c.hook}\n"
            f"- Resume : {c.summary or c.reason}\n"
            f"- Extrait transcription :\n{snippet or '  (transcription audio)'}\n"
        )
    candidates_text = "\n".join(cand_blocks)
    return PROMPT_PASS2.format(
        n_final=n_final,
        min_s=s.min_clip_s,
        max_s=s.max_clip_s,
        context_block=context_block,
        candidates_text=candidates_text,
    )


def _post(url: str, payload: dict, timeout: int = 600) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def ask_ollama(prompt: str, s: Settings, schema: dict | None = None) -> str:
    data = _post(f"{s.ollama_url}/api/chat", {
        "model": s.ollama_model,
        "messages": [{"role": "user", "content": prompt}],
        "format": schema or CLIP_SCHEMA_PASS1,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2, "num_ctx": 16384},
    })
    return data["message"]["content"]


def ask_gemini(
    prompt: str,
    s: Settings,
    images_b64: list[tuple[str, str]] | None = None,
) -> str:
    parts: list[dict] = [{"text": prompt}]
    if images_b64:
        for mime, b64_data in images_b64:
            parts.append({"inlineData": {"mimeType": mime, "data": b64_data}})

    models_to_try = [
        s.gemini_model or "gemini-3.5-flash",
        "gemini-3.5-flash",
        "gemini-flash-latest",
        "gemini-3.8-flash",
    ]
    seen = set()
    models = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

    last_exc = None
    for model_name in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={s.gemini_api_key}"
        try:
            data = _post(
                url,
                {
                    "contents": [{"parts": parts}],
                    "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"},
                },
                timeout=60,
            )
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as exc:
            last_exc = exc
            continue

    if last_exc:
        raise last_exc
    raise RuntimeError("Aucun modèle Gemini disponible.")


def parse_candidates(text: str, duration: float, s: Settings) -> list[Candidate]:
    """Tolerant parser: extracts the JSON object, drops invalid clips, clamps values."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out = []
    for c in data.get("clips", []):
        try:
            start, end = float(c["start"]), float(c["end"])
        except (KeyError, TypeError, ValueError):
            continue
        start, end = max(0.0, start), min(duration, end)
        # Keep short picks: select.snap() stretches them to min_clip_s at a sentence end.
        # Dropping them here silently removed every LLM clip when min_clip_s was raised to 30 s.
        if end - start < 3.0 or end - start > s.max_clip_s * 1.5:
            continue
        scores = {k: max(0.0, min(10.0, float(v))) for k, v in (c.get("scores") or {}).items() if isinstance(v, (int, float))}
        llm = sum(scores.values()) / (10 * len(scores)) if scores else 0.5
        title = str(c.get("title", ""))[:80]
        hook = str(c.get("hook", ""))[:60]
        reason = str(c.get("reason", ""))
        summary = str(c.get("summary", ""))
        out.append(Candidate(start, end, title, hook, reason, summary, scores, llm))
    return out


def find_candidates(
    words: list[Word],
    duration: float,
    s: Settings,
    sig: Signals | None = None,
    title: str = "",
    description: str = "",
) -> list[Candidate]:
    ask = {"ollama": ask_ollama, "gemini": ask_gemini}.get(s.llm_provider)
    if ask is None or not words:
        return []

    # 1. Signaux dans le texte : annoter chaque ligne avec [CRI], [RIRE], [SILENCE >3s], [ACTION]
    raw_lines = transcript_lines(words)
    annotated = annotate_lines(raw_lines, sig)

    examples = load_examples()

    # Passe 1 : par fenêtres temporelles, extraire 3x plus de candidats que demandé
    pass1_cands: list[Candidate] = []
    chunk_list = windows(annotated)
    for chunk in chunk_list:
        span = chunk[-1][1] - chunk[0][0]
        # 3x plus de candidats proposés lors de la passe 1
        n_pass1 = max(3, int(span // 120) * 3)
        prompt = build_pass1_prompt(chunk, n_pass1, s, title=title, description=description, examples=examples)
        try:
            raw_response = ask(prompt, s) if s.llm_provider == "gemini" else ask_ollama(prompt, s, schema=CLIP_SCHEMA_PASS1)
            parsed = parse_candidates(raw_response, duration, s)
            pass1_cands.extend(parsed)
        except Exception as exc:
            print(f"[llm] passe 1 fenetre ignoree: {exc}")

    if not pass1_cands:
        print(f"[llm] aucun candidat exploitable en passe 1 ({len(chunk_list)} fenetres) : repli sur les signaux")
        return []

    # Si nous avons assez de candidats pour une passe 2 d'arbitrage global
    if len(pass1_cands) > s.max_clips:
        try:
            print(f"[llm] passe 2 : arbitrage global sur {len(pass1_cands)} candidats pre-selectionnes")
            pass2_prompt = build_pass2_prompt(
                pass1_cands, annotated, s.max_clips, s, title=title, description=description
            )
            raw_pass2 = ask(pass2_prompt, s) if s.llm_provider == "gemini" else ask_ollama(pass2_prompt, s, schema=CLIP_SCHEMA_PASS2)
            pass2_cands = parse_candidates(raw_pass2, duration, s)
            if pass2_cands:
                return pass2_cands
        except Exception as exc:
            print(f"[llm] passe 2 ignoree (repli sur passe 1): {exc}")

    # Repli sur les candidats de passe 1 triés par score LLM
    pass1_cands.sort(key=lambda c: c.llm_score, reverse=True)
    return pass1_cands
