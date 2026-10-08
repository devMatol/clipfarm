from clipfarm_engine.highlights.llm import annotate_lines
from clipfarm_engine.highlights.signals import Signals


def test_detect_tags_silence():
    """Silence tag must be added when gap before line is >= 3.0 seconds."""
    sig = Signals(duration=30.0, loudness=[-40.0] * 30, scenes=[])
    # Première ligne commençant à 4.0s
    tags_first = sig.detect_tags(start=4.0, end=7.0, prev_end=None)
    assert "[SILENCE >3s]" in tags_first

    # Deuxième ligne avec écart de 3.5s après la première
    tags_second = sig.detect_tags(start=10.5, end=13.0, prev_end=7.0)
    assert "[SILENCE >3s]" in tags_second

    # Ligne sans silence (écart de 1.0s)
    tags_quick = sig.detect_tags(start=14.0, end=16.0, prev_end=13.0)
    assert "[SILENCE >3s]" not in tags_quick


def test_detect_tags_cri():
    """CRI tag must be added when segment volume exceeds mean + 1.5 * std."""
    # Fond sonore moyen à -40 dB avec un pic à -10 dB entre la seconde 5 et 6
    loudness = [-40.0] * 20
    loudness[5] = -10.0
    sig = Signals(duration=20.0, loudness=loudness, scenes=[])

    # Intervalle couvrant le pic à la seconde 5
    tags_shout = sig.detect_tags(start=4.5, end=6.5)
    assert "[CRI]" in tags_shout

    # Intervalle calme
    tags_calm = sig.detect_tags(start=10.0, end=12.0)
    assert "[CRI]" not in tags_calm


def test_detect_tags_action():
    """ACTION tag must be added when multiple scene changes occur."""
    sig = Signals(duration=20.0, loudness=[-40.0] * 20, scenes=[5.0, 5.8, 6.2])

    tags_action = sig.detect_tags(start=4.5, end=7.0)
    assert "[ACTION]" in tags_action

    tags_calm = sig.detect_tags(start=10.0, end=15.0)
    assert "[ACTION]" not in tags_calm


def test_detect_tags_rire():
    """RIRE tag must be added on rapid energy bursts."""
    # Succession de micro-pics de rire
    loudness = [-50.0] * 20
    loudness[4] = -25.0
    loudness[5] = -40.0
    loudness[6] = -26.0
    sig = Signals(duration=20.0, loudness=loudness, scenes=[])

    tags_laugh = sig.detect_tags(start=3.5, end=7.0)
    assert "[RIRE]" in tags_laugh


def test_annotate_lines():
    """annotate_lines properly prepends detected tags to transcript lines."""
    loudness = [-40.0] * 20
    loudness[5] = -10.0
    sig = Signals(duration=20.0, loudness=loudness, scenes=[5.2, 5.8])

    raw_lines = [
        (0.5, 2.0, "Bonjour tout le monde"),
        (5.0, 7.0, "Attention ça explose"),
    ]

    annotated = annotate_lines(raw_lines, sig)
    assert len(annotated) == 2
    assert annotated[0][2] == "Bonjour tout le monde"
    # La deuxième ligne a un cri et de l'action
    assert "[CRI]" in annotated[1][2]
    assert "[ACTION]" in annotated[1][2]
    assert "Attention ça explose" in annotated[1][2]
