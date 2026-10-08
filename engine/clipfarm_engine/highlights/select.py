"""Merge LLM picks and signal scores, snap to sentence boundaries, dedupe, rank."""

from __future__ import annotations

from ..captions.ass import Word
from ..config import Settings
from .llm import Candidate
from .signals import Signals, candidate_windows


def _sentence_starts(words: list[Word], gap: float = 0.5) -> list[float]:
    starts = []
    for i, w in enumerate(words):
        if i == 0 or words[i - 1].text[-1:] in ".?!" or w.start - words[i - 1].end > gap:
            starts.append(w.start)
    return starts


def _sentence_ends(words: list[Word], gap: float = 0.5) -> list[float]:
    ends = []
    for i, w in enumerate(words):
        if w.text[-1:] in ".?!" or i == len(words) - 1 or words[i + 1].start - w.end > gap:
            ends.append(w.end)
    return ends


def snap(c: Candidate, words: list[Word], s: Settings, tolerance: float = 3.0) -> Candidate:
    """Move start/end to the nearest sentence boundary within tolerance; keep duration in bounds."""
    if words:
        starts = [t for t in _sentence_starts(words) if abs(t - c.start) <= tolerance]
        ends = [t for t in _sentence_ends(words) if abs(t - c.end) <= tolerance]
        if starts:
            c.start = max(0.0, min(starts, key=lambda t: abs(t - c.start)) - 0.15)
        if ends:
            c.end = min(ends, key=lambda t: abs(t - c.end)) + 0.25
    if c.end - c.start > s.max_clip_s:
        c.end = c.start + s.max_clip_s
    if c.end - c.start < s.min_clip_s:
        # too short: stretch to the first sentence end after the minimum, never past the maximum
        later = [t for t in _sentence_ends(words) if c.start + s.min_clip_s <= t <= c.start + s.max_clip_s] if words else []
        c.end = (min(later) + 0.25) if later else c.start + s.min_clip_s
    return c


def _overlap(a: Candidate, b: Candidate) -> float:
    inter = max(0.0, min(a.end, b.end) - max(a.start, b.start))
    return inter / max(1e-6, min(a.end - a.start, b.end - b.start))


def select(llm_cands: list[Candidate], words: list[Word], sig: Signals, s: Settings,
           llm_weight: float = 0.75) -> list[Candidate]:
    cands = list(llm_cands)
    if not cands:  # no LLM: fall back to signals only
        llm_weight = 0.0
    if len(cands) < s.max_clips and sig.loudness:
        # top up with the best signal windows when the LLM returned too few clips
        target_len = (s.min_clip_s + s.max_clip_s) / 2
        length = min(target_len, sig.duration) if sig.duration > 0 else target_len
        min_gap = min(60.0, max(5.0, length / 2))
        for a, b, _ in candidate_windows(sig, length=length, top=s.max_clips * 2, min_gap=min_gap):
            extra = Candidate(a, b, reason="signal audio/scene")
            if all(_overlap(extra, c) < 0.3 for c in cands):
                cands.append(extra)
    for c in cands:
        snap(c, words, s)
        c.signal_score = sig.window_score(c.start, c.end) if sig.loudness else 0.0
        c.final_score = round(llm_weight * c.llm_score + (1 - llm_weight) * c.signal_score, 4)
    cands.sort(key=lambda c: c.final_score, reverse=True)
    kept: list[Candidate] = []
    for c in cands:
        if all(_overlap(c, k) < 0.3 for k in kept):
            kept.append(c)
        if len(kept) >= s.max_clips:
            break
    return kept
