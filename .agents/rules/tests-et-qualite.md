---
trigger: model_decision
description: A lire avant de declarer une tache terminee, ou quand on touche aux tests, aux metriques ou au rendu video
---

# Tests et qualite

- Une tache n'est terminee que si `uv run pytest -q` (et les tests du front si touches) sont verts.
- Pour tout changement de rendu : extraire une image de chaque clip produit et la regarder.
- Fin des phases 1, 4 et 5 : lancer `clipfarm_engine.eval` sur `engine/tests/golden/` et ajouter les chiffres a `docs/metrics.md` (date, reglages, resultats).
- Objectifs MVP : WER < 20 %, precision@5 >= 60 %, rendu reussi 100 %, traitement < 1/3 de la duree de la video.
- Un bug corrige = un test qui l'aurait attrape.
