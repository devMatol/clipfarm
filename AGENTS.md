# ClipFarm : instructions pour l'agent

## Le projet

Application locale qui transforme une vidéo longue (fichier ou lien) en clips verticaux : détection des meilleurs moments par IA, mise en page (facecam / jeu), sous-titres mot à mot, montage par consigne, publication programmée. Utilisateur : un développeur front (React/Angular) francophone sur Windows avec un GPU NVIDIA.

Lis selon le besoin :
- `docs/01-produit.md` : fonctionnalités et priorités (MVP, V2, V3)
- `docs/02-architecture.md` : stack, modèle de données, API, pipeline
- `docs/03-plan-attaque.md` : les phases et leurs critères d'acceptation
- `docs/04-plan-de-test.md` : stratégie de test et objectifs chiffrés
- `docs/05-installation.md` : installation et problèmes connus

## Contraintes non négociables

1. **Gratuit** : aucun service payant, aucune clé obligatoire. Une option payante doit rester désactivée par défaut.
2. **Local d'abord** : tout tourne sur le PC Windows. Le moteur Python reste en natif (GPU), Docker seulement pour Postgres.
3. **Pas de code AGPL importé** (Postiz, VoiceStudio, SupoClip) : ce sont des services qu'on appelle par API.
4. **Une phase à la fois** : ne commence pas une fonctionnalité d'une phase suivante.
5. **Tests verts avant de rendre la main.** Toute fonctionnalité ajoutée a un test.
6. **Ne casse pas ce qui marche** : mises en page, sous-titres, signaux et sélection sont testés. Si tu changes leur sortie, mets à jour les tests et explique pourquoi.

## Commandes

```
# moteur
cd engine
uv sync --extra ai --extra dev
uv run pytest -q
uv run python -m clipfarm_engine run "<video ou lien>" --layout facecam_top --cam 0.739,0.083,0.246,0.245
uv run python -m clipfarm_engine.eval tests/golden/<nom>.json ../data/projects/<id>

# infra
docker compose -f infra/docker-compose.yml up -d
```

## Organisation du code

- `engine/clipfarm_engine/` : moteur. Le cœur n'utilise que la stdlib + ffmpeg. Les libs lourdes (whisperx, demucs, mediapipe) sont importées dans les fonctions, jamais en haut de module.
- `api/` (phase 2) : FastAPI, SQLModel, procrastinate. Appelle `clipfarm_engine.pipeline`, ne réimplémente rien.
- `apps/web/` (phase 3) : Next.js App Router, TypeScript strict, Tailwind, shadcn/ui, TanStack Query.
- `data/` : sorties, jamais commitées.

## Style

- Python 3.12, typé, fonctions courtes, `ruff` propre. Messages utilisateur en français.
- Chemins Windows : toujours `pathlib`, jamais de concaténation de chaînes. Pour les filtres ffmpeg qui prennent un fichier (ass, subtitles), lancer ffmpeg depuis le dossier du fichier et passer un nom relatif (voir `media/render.py`).
- Erreurs : une étape qui échoue (Ollama absent, diarisation refusée) dégrade proprement avec un message, elle ne fait pas planter tout le job.

## Pièges déjà rencontrés

- Fichiers avec image de couverture : `probe()` ignore les pistes `attached_pic`.
- Whisper forcé en français transcrit aussi les dialogues anglais du jeu : isoler la voix (Demucs) avant, diarisation ensuite.
- `cublas64_12.dll` manquant = torch sans CUDA. Ne pas basculer en CPU en silence : le signaler.
- Sous-titres trop gros : max 3 mots / 18 caractères par écran, police 72 sur 1920 px de haut.
- Les sous-titres du jeu sont incrustés en bas : marge basse de 300 px par défaut.

## Vérifier un rendu

Toujours extraire une image et la regarder avant de dire qu'un rendu est bon :
`ffmpeg -ss 5 -i data/projects/<id>/clips/01.mp4 -frames:v 1 check.png`
