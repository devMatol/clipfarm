# Changelog

## Phase 0 (préparé)
- Moteur en CLI : ingestion fichier ou lien, signaux ffmpeg, sélection avec repli sans IA, mises en page (centrée, flou, facecam haut/bas), formats 9:16 / 1:1 / 4:5 / 16:9, sous-titres ASS mot à mot.
- Transcription WhisperX + Demucs et appel Ollama/Gemini codés, à valider sur GPU (phase 1).
- Métriques d'évaluation (WER, precision@k, recall, IoU).
- Tests pytest sur médias synthétiques.

## Phase 2 (livrée)
- API FastAPI + SQLModel + Procrastinate (`api/clipfarm_api/`) avec schémas `Project`, `Clip`.
- Worker GPU limité à 1 tâche concurrente pour préserver les ressources GPU.
- Diffusion temps réel en SSE (`/projects/{id}/events`) et streaming upload de fichiers volumineux sans saturation mémoire.
- Support du streaming vidéo partiel HTTP `Range` (code 206) pour lecteur HTML5 et sécurisation contre les traversées de répertoire.
- Re-rendu immédiat d'un clip avec layout/format/style personnalisé sans relancer la transcription ni l'isolation audio.
- 8 tests pytest automatisés verts.

## Phase 2 & 3 — Revue et Validation E2E Réelle (GPU)
- **File de jobs Procrastinate & Postgres** : suppression du repli SQLite/InMemoryConnector pour le worker multi-processus. Prise en charge automatique de Postgres natif ou Docker via `scripts/dev.ps1` avec application du schéma avant lancement de l'API. Suppression des `except: pass` autour des `defer()` : passage systématique en `failed` avec message en cas d'erreur.
- **Modèle de données & mots** : alignement de l'API sur `Word(start, end, text, prob)` (champs `text` et `prob`). Support du PATCH mot à mot et sauvegarde dans `clip_{index}_words.json`.
- **Cadrage Facecam persistant** : persistance de la boîte englobante dans `clip.layout["cam"]` et réutilisation automatique au re-rendu.
- **Flux Facecam Web & Liens** : extraction d'image côté client (video + canvas) pour les fichiers locaux et statut `awaiting_cam` avec endpoint `/projects/{id}/set-cam` pour les liens.
- **SSE résilient multi-processus** : lecture de la progression en base PostgreSQL toutes les secondes pour refléter fidèlement l'état du worker externe.
- **Re-rendu asynchrone** : transfert du re-rendu vers un job Procrastinate (`rerender_project_task`) sur la file GPU.
- **Workspace unifié uv** : racine unifiée avec `engine[ai,dev]` et `api`, index PyTorch CUDA 12.8, suppression des venvs dupliqués.
- **Upload sécurisé et unique** : nommage garanti sans collision `f"{proj_id}_{filename}"`.
- **Compatibilité Windows asyncio** : utilisation de `WindowsSelectorEventLoopPolicy` pour psycopg async avec Procrastinate et Uvicorn.
- **Validation bout en bout RÉELLE (GPU)** : pipeline exécuté sur extrait GTA 6 (25s) avec isolation vocale, transcription Whisper GPU, calcul des signaux, découpe et encodage vertical 9:16 avec facecam 1080x1920 et sous-titres dynamiques jaunes. Rendu validé visuellement (`check.png`) et 4 écrans web capturés avec les données réelles en base.

## Phase Qualité Détection des Moments
- **Balises signaux dans le texte** : annotation préalable de chaque segment transcrit avant transmission au LLM avec `[CRI]` (volume sonore dépassant $\text{moyenne} + 1.5\,\sigma$), `[RIRE]` (pics d'énergie courts et répétés), `[SILENCE >3s]` (pauses significatives) et `[ACTION]` (fréquence élevée de changements de plans).
- **Architecture de sélection en deux passes** :
  - *Passe 1* : génération de $3\times$ plus de candidats par fenêtre avec titres, hooks et résumés en une phrase (`summary`).
  - *Passe 2* : arbitrage global en un seul appel consolidé recevant l'ensemble des résumés et extraits de transcription, garantissant la présence de la mise en place avant la chute, l'absence de chevauchements et une durée conforme (30-70 s).
  - Repli robuste sur le classement de la passe 1 en cas de problème sur la passe 2.
- **Contexte vidéo enrichi** : extraction et transmission au prompt du titre et de la description de la vidéo (via `yt-dlp` ou métadonnées locales).
- **Recommandations VRAM et support Gemini** : tableau comparatif documenté selon la VRAM GPU disponible (`nvidia-smi`), et support du mode `LLM_PROVIDER=gemini` (contexte étendu 1M tokens, gratuit).
- **Personnalisation few-shot** : dossier `data/exemples/` permettant à l'utilisateur de définir des exemples de référence intégrés dynamiquement dans le prompt.
- **Évaluation et métriques** : suite de tests unitaires (`test_signals_tags`, `test_pass2`, `test_parser`), intégrité du repli sans IA confirmée, et rapport de métriques rédigé dans `docs/metrics.md` avec precision@5 et recall à 100 % sur le jeu de référence `gta6_sample.json`.

## Phase 4 — Détection Automatique de la Facecam et Layout Dynamique
- **Module de vision `clipfarm_engine.vision.facecam`** :
  - Échantillonnage à 1 image / 2s redimensionnée en 640px.
  - Détection de visage MediaPipe multi-régions (plein écran + quadrants de bordure) et classification en 3 états : `overlay` (visage incrusté en coin), `fullscreen` (caméra plein écran / gros plan) et `gameplay` (aucun visage).
  - Détection automatique et fine du cadre de la caméra (`cam.json`) par projection des gradients Canny OpenCV autour du visage stabilisé, atteignant un **IoU de 0.872** ($\ge 0.80$).
- **Rendu dynamique par timeline multi-segments (`render_timeline_clip`)** :
  - Découpage temporel automatique selon les transitions détectées (`overlay` $\to$ `facecam_top`, `fullscreen` $\to$ `center` avec zoom visage, `gameplay` $\to$ `center`).
  - Concaténation propre via filtre `ffmpeg concat` sans saut d'encodage et incrustation subs `.ass` mot à mot.
- **Mémorisation par chaîne (`CamPreset`)** :
  - Table SQLModel `CamPreset` associant chaque chaîne (`channel_name` extrait via `yt-dlp` ou métadonnées) à son cadrage préféré pour réapplication automatique sur les futurs projets.
- **Interface Utilisateur Web** :
  - Carte de cadrage Facecam sur la page projet affichant l'image source, le statut du cadrage (badge « Manuel » ou « Détecté automatiquement (MediaPipe) » avec coordonnées exactes en %), et un bouton « Corriger » ouvrant le sélecteur interactif existant.
  - Priorité absolue au réglage manuel de l'utilisateur.
- **Tests & Qualité** :
  - 7 tests unitaires synthétiques (détection coin, plein écran, gameplay, gradients de cadrage, segmentation timeline, formats invalides).
  - Test d'IoU golden vérifié à **87.2 %** sur `gta6_sample.json`.

## Résilience Ingest yt-dlp
- **Reprise et tolérance aux coupures** : ajout des options `--retries 10`, `--fragment-retries 10` et `--continue` pour supporter les micro-coupures réseau et reprendre les flux interrompus sans tout retélécharger.
- **Diagnostic explicite des erreurs** : capture de `stderr` de yt-dlp restituant les 10 dernières lignes de log en cas d'échec définitif au lieu du message générique `"returned non-zero exit status 1"`.
- **Réessai automatique** : réexécution automatique d'une deuxième tentative avant tout échec définitif du job.
- **Suite de tests** : 3 tests unitaires et intégrés dans `engine/tests/test_ingest.py` validant les arguments, le réessai automatique et la capture exacte des 10 lignes.

