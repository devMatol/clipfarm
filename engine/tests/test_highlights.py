import json

from clipfarm_engine.captions.ass import Word
from clipfarm_engine.config import Settings
from clipfarm_engine.highlights import llm, select, signals

from media_samples import sample_video


def test_loudness_finds_the_burst():
    lv = signals.loudness_per_second(sample_video())
    assert 88 <= len(lv) <= 91
    loud = max(range(len(lv)), key=lambda i: lv[i])
    assert 45 <= loud <= 55


def test_scene_changes_at_30_and_60():
    cuts = signals.scene_changes(sample_video())
    assert any(abs(t - 30) < 0.5 for t in cuts) and any(abs(t - 60) < 0.5 for t in cuts)


def test_signal_windows_rank_the_burst_first():
    sig = signals.compute(sample_video())
    best = max(signals.candidate_windows(sig, length=20, top=3), key=lambda w: w[2])
    assert best[0] <= 50 <= best[1]


def test_llm_output_parser_is_tolerant():
    s = Settings()
    text = "Voila :\n" + json.dumps({"clips": [
        {"start": 10, "end": 40, "title": "ok", "hook": "h", "reason": "r", "scores": {"hook": 8, "emotion": 9, "payoff": 7, "standalone": 6}},
        {"start": 50, "end": 52, "title": "trop court"},
        {"start": "x", "end": 9},
        {"start": 60, "end": 999, "title": "clamp", "scores": {"hook": 20}},
    ]}) + "\nfin"
    cands = llm.parse_candidates(text, duration=90, s=s)
    assert [c.title for c in cands] == ["ok", "clamp"]
    assert cands[0].llm_score == 0.75
    assert cands[1].end == 90 and cands[1].scores["hook"] == 10


def test_transcript_windows_overlap_and_cover_everything():
    words = [Word(t, t + 0.4, f"m{t}.") for t in range(0, 1500, 5)]
    lines = llm.transcript_lines(words)
    chunks = llm.windows(lines, size=480, overlap=60)
    covered = {l for c in chunks for l in c}
    assert covered == set(lines) and len(chunks) >= 3


def test_snap_moves_to_sentence_boundaries():
    s = Settings()
    s.min_clip_s, s.max_clip_s = 15, 60
    words = [Word(9.0, 9.5, "Fin."), Word(10.2, 10.6, "Debut"), Word(10.6, 11.0, "phrase"),
             Word(38.0, 38.6, "chute."), Word(39.5, 40.0, "suite")]
    c = select.snap(llm.Candidate(11.5, 39.0), words, s)
    assert abs(c.start - 10.05) < 0.01 and abs(c.end - 38.85) < 0.01


def test_select_without_llm_uses_signals():
    s = Settings()
    s.max_clips = 2
    sig = signals.compute(sample_video())
    kept = select.select([], [], sig, s)
    assert 1 <= len(kept) <= 2
    assert kept[0].start <= 50 <= kept[0].end


def test_short_llm_clip_is_extended_to_a_sentence_end():
    s = Settings()
    s.min_clip_s, s.max_clip_s = 30, 70
    words = [Word(float(t), t + 0.5, "mot." if t in (12, 41, 80) else "mot") for t in range(10, 90)]
    c = select.snap(llm.Candidate(10.0, 25.0), words, s)
    assert c.end - c.start >= 30 and abs(c.end - 41.75) < 0.01


def test_llm_shortfall_is_topped_up_with_signal_windows():
    s = Settings()
    s.max_clips, s.min_clip_s, s.max_clip_s = 3, 10, 20
    sig = signals.compute(sample_video())
    kept = select.select([llm.Candidate(0.0, 15.0, llm_score=0.9)], [], sig, s)
    assert len(kept) >= 2 and kept[0].start == 0.0
