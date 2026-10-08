import json
from unittest.mock import patch

from clipfarm_engine.captions.ass import Word
from clipfarm_engine.config import Settings
from clipfarm_engine.highlights.llm import Candidate, build_pass2_prompt, find_candidates


def test_build_pass2_prompt():
    s = Settings()
    s.min_clip_s = 30
    s.max_clip_s = 70

    candidates = [
        Candidate(start=10.0, end=45.0, title="Titre 1", hook="Hook 1", summary="Résumé 1", reason="Raison 1"),
        Candidate(start=60.0, end=95.0, title="Titre 2", hook="Hook 2", summary="Résumé 2", reason="Raison 2"),
    ]
    lines = [
        (10.0, 15.0, "Première phrase"),
        (15.5, 20.0, "Deuxième phrase"),
        (60.0, 65.0, "Troisième phrase"),
    ]

    prompt = build_pass2_prompt(candidates, lines, n_final=1, s=s, title="Mon Super Stream", description="Description")
    assert "Mon Super Stream" in prompt
    assert "Candidat #1" in prompt
    assert "Candidat #2" in prompt
    assert "Titre 1" in prompt
    assert "Titre 2" in prompt
    assert "30 et 70 secondes" in prompt


def test_find_candidates_two_pass_execution():
    """find_candidates calls pass 1 per window, then triggers pass 2 when candidates exceed max_clips."""
    s = Settings()
    s.llm_provider = "ollama"
    s.max_clips = 2
    s.min_clip_s = 10
    s.max_clip_s = 30

    # Créer une liste de mots couvrant 60 secondes
    words = [Word(start=float(i), end=float(i) + 0.8, text=f"mot{i}", prob=0.99) for i in range(50)]

    # Passe 1 retourne 4 candidats (plus que max_clips=2)
    pass1_response = json.dumps({
        "clips": [
            {"start": 5.0, "end": 18.0, "title": "C1", "hook": "H1", "summary": "S1", "reason": "R1", "scores": {"hook": 7, "emotion": 7, "payoff": 7, "standalone": 7}},
            {"start": 12.0, "end": 26.0, "title": "C2", "hook": "H2", "summary": "S2", "reason": "R2", "scores": {"hook": 8, "emotion": 8, "payoff": 8, "standalone": 8}},
            {"start": 20.0, "end": 35.0, "title": "C3", "hook": "H3", "summary": "S3", "reason": "R3", "scores": {"hook": 6, "emotion": 6, "payoff": 6, "standalone": 6}},
            {"start": 30.0, "end": 45.0, "title": "C4", "hook": "H4", "summary": "S4", "reason": "R4", "scores": {"hook": 9, "emotion": 9, "payoff": 9, "standalone": 9}},
        ]
    })

    # Passe 2 sélectionne et affine les 2 meilleurs
    pass2_response = json.dumps({
        "clips": [
            {"start": 30.0, "end": 45.0, "title": "C4 Meilleur", "hook": "H4 Top", "reason": "Excellent", "scores": {"hook": 10, "emotion": 9, "payoff": 9, "standalone": 9}},
            {"start": 5.0, "end": 18.0, "title": "C1 Solide", "hook": "H1 Bon", "reason": "Très bon", "scores": {"hook": 8, "emotion": 8, "payoff": 8, "standalone": 8}},
        ]
    })

    call_count = 0
    def mock_ask_ollama(prompt, settings, schema=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return pass1_response
        return pass2_response

    with patch("clipfarm_engine.highlights.llm.ask_ollama", side_effect=mock_ask_ollama):
        cands = find_candidates(words, duration=60.0, s=s)

    assert call_count == 2, "Pass 1 and Pass 2 must both be executed"
    assert len(cands) == 2
    assert cands[0].title == "C4 Meilleur"
    assert cands[1].title == "C1 Solide"


def test_find_candidates_pass2_failure_falls_back_to_pass1():
    """If pass 2 encounters an error, it safely falls back to pass 1 candidates sorted by score."""
    s = Settings()
    s.llm_provider = "ollama"
    s.max_clips = 2
    s.min_clip_s = 10
    s.max_clip_s = 30

    words = [Word(start=float(i), end=float(i) + 0.8, text=f"mot{i}", prob=0.99) for i in range(50)]

    pass1_response = json.dumps({
        "clips": [
            {"start": 5.0, "end": 18.0, "title": "C1", "scores": {"hook": 5, "emotion": 5, "payoff": 5, "standalone": 5}},
            {"start": 20.0, "end": 35.0, "title": "C2", "scores": {"hook": 9, "emotion": 9, "payoff": 9, "standalone": 9}},
            {"start": 30.0, "end": 45.0, "title": "C3", "scores": {"hook": 8, "emotion": 8, "payoff": 8, "standalone": 8}},
        ]
    })

    call_count = 0
    def mock_ask_ollama(prompt, settings, schema=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return pass1_response
        # Simuler une panne lors de la passe 2
        raise RuntimeError("Pass 2 timeout")

    with patch("clipfarm_engine.highlights.llm.ask_ollama", side_effect=mock_ask_ollama):
        cands = find_candidates(words, duration=60.0, s=s)

    assert call_count == 2
    # Repli propre sur les 3 candidats de la passe 1, triés par llm_score décroissant
    assert len(cands) == 3
    assert cands[0].title == "C2"  # score 9/10
    assert cands[1].title == "C3"  # score 8/10
    assert cands[2].title == "C1"  # score 5/10
