import json
from clipfarm_engine.config import Settings
from clipfarm_engine.highlights.llm import parse_candidates


def test_parse_candidates_valid_json():
    s = Settings()
    s.min_clip_s = 10
    s.max_clip_s = 60

    payload = {
        "clips": [
            {
                "start": 5.0,
                "end": 25.0,
                "title": "Braquage incroyable",
                "hook": "Regardez ce qui arrive !",
                "summary": "Le joueur tente un braquage mais les flics arrivent.",
                "reason": "Excellente réaction",
                "scores": {"hook": 8, "emotion": 9, "payoff": 8, "standalone": 9},
            }
        ]
    }
    raw = json.dumps(payload)
    cands = parse_candidates(raw, duration=100.0, s=s)
    assert len(cands) == 1
    assert cands[0].start == 5.0
    assert cands[0].end == 25.0
    assert cands[0].title == "Braquage incroyable"
    assert cands[0].summary == "Le joueur tente un braquage mais les flics arrivent."
    assert cands[0].llm_score == (8 + 9 + 8 + 9) / 40.0


def test_parse_candidates_markdown_fenced():
    s = Settings()
    s.min_clip_s = 10
    s.max_clip_s = 60

    raw = """Voici les meilleurs clips trouvés :
```json
{
  "clips": [
    {
      "start": 12.0,
      "end": 35.0,
      "title": "Chute de moto",
      "hook": "Il ne l'avait pas vu !",
      "reason": "Fou rire",
      "scores": {"hook": 7, "emotion": 8, "payoff": 8, "standalone": 7}
    }
  ]
}
```
J'espère que cette sélection vous convient !"""

    cands = parse_candidates(raw, duration=100.0, s=s)
    assert len(cands) == 1
    assert cands[0].title == "Chute de moto"
    assert cands[0].start == 12.0


def test_parse_candidates_drops_invalid_and_out_of_bounds():
    s = Settings()
    s.min_clip_s = 20
    s.max_clip_s = 60

    raw = json.dumps({
        "clips": [
            # Trop court (< 20 * 0.6 = 12s)
            {"start": 5.0, "end": 6.5, "title": "Trop court"},
            # Trop long (> 60 * 1.5 = 90s)
            {"start": 0.0, "end": 120.0, "title": "Trop long"},
            # Données manquantes ou invalides
            {"title": "Pas de start ni end"},
            {"start": "invalide", "end": "invalide", "title": "Types corrompus"},
            # Clip valide
            {"start": 20.0, "end": 55.0, "title": "Clip valide", "scores": {"hook": 8, "emotion": 8, "payoff": 8, "standalone": 8}},
        ]
    })
    cands = parse_candidates(raw, duration=200.0, s=s)
    assert len(cands) == 1
    assert cands[0].title == "Clip valide"


def test_parse_candidates_corrupted_json_returns_empty():
    s = Settings()
    cands = parse_candidates("Ceci n'est pas du JSON { clips: broken", duration=100.0, s=s)
    assert cands == []


def test_short_llm_pick_is_kept_for_snap_to_extend():
    """Regression: with min_clip_s=30, 15 s LLM picks used to be dropped, leaving only signal clips."""
    from clipfarm_engine.config import Settings
    from clipfarm_engine.highlights.llm import parse_candidates
    s = Settings()
    s.min_clip_s, s.max_clip_s = 30, 70
    text = '{"clips": [{"start": 100.0, "end": 115.0, "title": "Court mais bon", "scores": {"hook": 9}}]}'
    cands = parse_candidates(text, duration=600, s=s)
    assert [c.title for c in cands] == ["Court mais bon"]
