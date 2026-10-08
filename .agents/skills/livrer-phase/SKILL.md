---
name: livrer-phase
description: Procedure pour executer une phase du plan d'attaque ClipFarm de bout en bout (lecture, plan, code, tests, verification, changelog). A utiliser quand l'utilisateur demande de faire ou continuer une phase.
---

# Livrer une phase

1. Lire la phase dans `docs/03-plan-attaque.md`, ses criteres, et la partie correspondante de `docs/02-architecture.md` et `docs/04-plan-de-test.md`.
2. Proposer un plan court (fichiers a creer ou modifier, tests prevus) et attendre la validation.
3. Coder par petites etapes, tests a chaque etape.
4. Lancer tous les tests (`cd engine; uv run pytest -q`, plus front/API si concernes).
5. Verifier en vrai : un run sur une video reelle, frames regardees pour le rendu.
6. Cocher les criteres de la phase un par un dans le rapport final, avec la preuve (sortie de commande, image).
7. Ajouter une entree a `CHANGELOG.md`, mettre a jour `docs/metrics.md` si la phase le demande, commit avec un message clair.
8. Lister ce qui reste fragile ou non teste.
