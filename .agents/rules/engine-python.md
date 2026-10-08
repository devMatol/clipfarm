---
trigger: glob
globs: engine/**
description: Regles du moteur Python (ffmpeg, IA, pipeline)
---

# Moteur Python

- Le coeur (`media/`, `captions/`, `highlights/signals.py`, `highlights/select.py`, `pipeline.py`) n'importe que la stdlib. Les libs IA sont importees dans les fonctions qui en ont besoin.
- Chaque etape du pipeline lit son cache dans `data/projects/<id>/` avant de travailler et ecrit son resultat en JSON lisible.
- Les appels ffmpeg passent par `media/ffmpeg.run()` (erreurs lisibles, encodage utf-8). Ne pas appeler `subprocess` sur ffmpeg ailleurs.
- Mises en page : calculer les tailles en pixels pairs dans `media/layouts.py`, jamais d'expressions ffmpeg du type `iw*0.3`.
- Sous-titres : generer de l'ASS avec `PlayResX/PlayResY` egaux a la sortie, une ligne `Dialogue` par mot.
- Tout appel reseau (Ollama, Gemini, Postiz) a un timeout et un repli.
- Tests : medias synthetiques generes par `tests/media_samples.py`. Aucun fichier video dans le repo. Tests IA reels marques `@pytest.mark.gpu`.
