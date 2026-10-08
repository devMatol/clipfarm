from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from clipfarm_engine import pipeline
from clipfarm_engine.config import Settings


def test_ingest_command_arguments_and_retry_success(tmp_path: Path):
    """
    Test avec un faux yt-dlp qui échoue au premier appel,
    puis réussit au deuxième appel :
    - Vérifie la présence de --retries 10, --fragment-retries 10, --continue
    - Vérifie que 2 tentatives sont exécutées
    - Vérifie que le projet est renvoyé avec succès
    """
    s = Settings()
    s.data_dir = tmp_path / "data"

    attempts = 0
    captured_cmds = []
    progress_messages = []

    def mock_progress(step: str, pct: float, msg: str):
        progress_messages.append((step, pct, msg))

    def fake_subprocess_run(cmd, capture_output=True, text=True):
        nonlocal attempts
        attempts += 1
        captured_cmds.append(cmd)

        if attempts == 1:
            # Échec au premier essai avec du stderr
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="",
                stderr="[download] Destination: source.mp4\nERROR: Unable to download webpage: HTTP Error 503\nTemporary failure",
            )

        # Réussite au 2ème essai : on crée le fichier cible pour simuler yt-dlp
        target_path = Path(cmd[cmd.index("-o") + 1])
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"fake mp4 video bytes")

        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="[download] 100% of 10.00MiB",
            stderr="",
        )

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        proj = pipeline.ingest("https://www.youtube.com/watch?v=mock123", s, progress=mock_progress)

    # 1. Vérification du réessai
    assert attempts == 2, f"Attendu 2 tentatives, obtenu {attempts}"
    assert proj.source.exists()

    # 2. Vérification des arguments obligatoires
    first_cmd = captured_cmds[0]
    assert "--retries" in first_cmd
    assert first_cmd[first_cmd.index("--retries") + 1] == "10"
    assert "--fragment-retries" in first_cmd
    assert first_cmd[first_cmd.index("--fragment-retries") + 1] == "10"
    assert "--continue" in first_cmd

    # 3. Vérification de la notification de progression
    retry_notice = [m for m in progress_messages if "echec yt-dlp (tentative 1/2)" in m[2]]
    assert len(retry_notice) == 1


def test_ingest_failure_captures_last_10_lines_of_stderr(tmp_path: Path):
    """
    En cas d'échec répété :
    - Réessaie 1 fois (2 tentatives au total)
    - Capture les 10 dernières lignes de stderr dans l'exception
    - Ne contient pas 'returned non-zero exit status 1'
    """
    s = Settings()
    s.data_dir = tmp_path / "data"

    # Création de 15 lignes distinctes dans stderr
    stderr_lines = [f"Ligne de log stderr #{i:02d}" for i in range(1, 16)]
    mock_stderr = "\n".join(stderr_lines)

    run_calls = 0

    def fake_failing_run(cmd, capture_output=True, text=True):
        nonlocal run_calls
        run_calls += 1
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=1,
            stdout="",
            stderr=mock_stderr,
        )

    with patch("subprocess.run", side_effect=fake_failing_run):
        with pytest.raises(RuntimeError) as exc_info:
            pipeline.ingest("https://www.youtube.com/watch?v=failing123", s)

    # Vérification des 2 tentatives
    assert run_calls == 2

    err_msg = str(exc_info.value)

    # Vérification que le message contient exactement les 10 dernières lignes (lignes 6 à 15)
    for i in range(6, 16):
        assert f"Ligne de log stderr #{i:02d}" in err_msg, f"Ligne {i} manquante dans le message d'erreur"

    # Et qu'il ne contient pas les 5 premières lignes
    for i in range(1, 6):
        assert f"Ligne de log stderr #{i:02d}" not in err_msg, f"Ligne {i} ne devrait pas être dans les 10 dernières"

    # Et pas l'erreur générique CalledProcessError
    assert "returned non-zero exit status 1" not in err_msg


def test_ingest_real_subprocesses_fail_then_succeed(tmp_path: Path):
    """
    Test avec un vrai script python externe jouant le rôle de yt-dlp :
    - Échoue au 1er lancement en écrivant un fichier témoin
    - Réussit au 2nd lancement
    """
    s = Settings()
    s.data_dir = tmp_path / "data"

    counter_file = tmp_path / "run_count.txt"

    # Création d'un faux script yt-dlp exécuté en vrai sous-processus
    fake_script = tmp_path / "fake_ytdlp.py"
    fake_script.write_text(f"""
import sys
from pathlib import Path

counter = Path(r"{counter_file}")
count = 0
if counter.exists():
    count = int(counter.read_text())

count += 1
counter.write_text(str(count))

if count == 1:
    sys.stderr.write("Erreur reseau simulee au premier passage\\n")
    sys.exit(1)

# Second passage : creation du fichier de sortie
out_idx = sys.argv.index("-o")
target = Path(sys.argv[out_idx + 1])
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(b"dummy video")
sys.exit(0)
""", encoding="utf-8")

    # On patche sys.executable + les arguments pour invoquer notre faux script
    orig_run = subprocess.run

    def intercept_run(cmd, *args, **kwargs):
        # Remplacer "-m", "yt_dlp" par l'appel direct au fake_script
        new_cmd = [sys.executable, str(fake_script)] + cmd[4:]
        return orig_run(new_cmd, *args, **kwargs)

    with patch("subprocess.run", side_effect=intercept_run):
        proj = pipeline.ingest("https://www.youtube.com/watch?v=realsubprocess", s)

    assert counter_file.read_text() == "2"
    assert proj.source.exists()
    assert proj.source.read_bytes() == b"dummy video"
