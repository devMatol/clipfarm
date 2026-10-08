# Plan d'attaque

Une phase = une session Antigravity. On ne passe à la suivante que quand tous les critères de la phase sont verts. Chaque phase se termine par un commit et une ligne dans `CHANGELOG.md`.

Mode conseillé dans Antigravity : **Planning** (l'agent propose un plan, tu valides, il exécute), avec relecture des diffs.

---

## Phase 0 : environnement (30 min)

**But** : tout installer et prouver que le moteur tourne sur ton PC.

1. `powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1`
2. Les tests passent (`uv run pytest -q` dans `engine/`).
3. Test réel sans IA :
   `uv run python -m clipfarm_engine run "C:\...\GTA 6 GAMEPLAY REVEAL (1).mp4" --layout facecam_top --cam 0.739,0.083,0.246,0.245 --llm none --no-transcribe`

**Critères**
- [ ] tous les tests verts
- [ ] des clips 1080x1920 dans `data/projects/<id>/clips/`, facecam en haut, jeu en bas
- [ ] `nvidia-smi` affiche la carte

**Prompt Antigravity**
```
Lis AGENTS.md et docs/05-installation.md. Exécute scripts/setup-windows.ps1, puis les tests du moteur
(engine, uv run pytest -q). Corrige uniquement ce qui empêche l'installation ou les tests de passer sur
cette machine Windows, sans changer le comportement du moteur. Termine par un rapport : versions installées,
GPU détecté, résultat des tests.
```

---

## Phase 1 : moteur IA complet en CLI

**But** : la vraie chaîne avec IA, sur GPU, mesurée sur un jeu de test.

Tâches
1. Valider `transcribe/speech.py` avec WhisperX sur GPU (API exacte de la version installée, `large-v3-turbo`, alignement FR).
2. Valider Demucs : la voix isolée doit contenir le streamer et presque plus le jeu.
3. Valider l'appel Ollama (`highlights/llm.py`) : sortie JSON conforme au schéma, timeout et reprise.
4. Ajouter `--from-step` à la CLI pour relancer à partir d'une étape (ex. `render`).
5. Constituer le jeu de test (`engine/tests/golden/`, voir plan de test) : 3 vidéos à toi annotées au départ.
6. Lancer `python -m clipfarm_engine.eval` et noter les métriques dans `docs/metrics.md`.

**Critères**
- [ ] WER < 20 % sur les extraits annotés (voix du streamer)
- [ ] precision@5 >= 60 % sur les moments annotés
- [ ] vidéo de 30 min traitée en moins de 10 min sur ta carte
- [ ] relancer un rendu seul prend moins de 1 min (cache)

**Prompt Antigravity**
```
Phase 1 de docs/03-plan-attaque.md. Le moteur est dans engine/. Valide sur GPU la transcription
(transcribe/speech.py, WhisperX), l'isolation de voix (Demucs) et le choix des moments par Ollama
(highlights/llm.py). Adapte le code à l'API réelle des versions installées. Ajoute l'option --from-step à
la CLI. Écris des tests pour tout ce que tu ajoutes (les appels IA réels en tests marqués @pytest.mark.gpu,
ignorés par défaut). Ne change pas les sorties déjà testées (mises en page, sous-titres, signaux) sans
mettre à jour leurs tests. Termine par un run complet sur la vidéo que je te donne et le rapport eval.
```

---

## Phase 2 : API + file de jobs + base

**But** : le moteur piloté par une API, avec suivi en direct.

Tâches
1. Dossier `api/` : FastAPI, SQLModel, Postgres (Docker), procrastinate.
2. Modèle de données et routes de `docs/02-architecture.md`.
3. Worker qui appelle `clipfarm_engine.pipeline` et pousse la progression (SSE).
4. Upload en streaming (plusieurs Go sans tout charger en mémoire).
5. Reprise propre : un job planté passe en `failed` avec le message, relançable.

**Critères**
- [ ] `POST /projects` avec un lien ou un fichier, puis `GET /projects/{id}` jusqu'à `ready`
- [ ] progression visible en direct via `/projects/{id}/events`
- [ ] deux projets en file passent l'un après l'autre (un seul job GPU à la fois)
- [ ] tests API (pytest + httpx) verts, moteur simulé dans les tests

**Prompt Antigravity**
```
Phase 2 de docs/03-plan-attaque.md. Crée api/ (FastAPI + SQLModel + Postgres + procrastinate) selon le
modèle de données et les routes de docs/02-architecture.md. Le worker appelle clipfarm_engine.pipeline et
publie la progression en SSE. Un seul job GPU à la fois. Upload multipart en streaming vers data/uploads.
Tests avec un faux pipeline (pas de GPU). Ajoute la commande de lancement dans le README.
```

---

## Phase 3 : interface web MVP

**But** : utiliser ClipFarm sans terminal.

Écrans
1. **Accueil** : liste des projets avec statut.
2. **Nouveau projet** : glisser un fichier ou coller un lien, choisir format, mise en page, style de sous-titres, nombre de clips. Pour la facecam : dessiner le rectangle sur une image de la vidéo.
3. **Projet** : progression par étape, puis grille des clips classés (aperçu, score, titre, accroche, raison).
4. **Clip** : lecteur, réglage début et fin, correction des mots, changement de style, re-rendu, téléchargement.

Stack : Next.js (App Router) + TypeScript + Tailwind + shadcn/ui + TanStack Query. Design sombre, pensé pour le mobile aussi.

**Critères**
- [ ] parcours complet fichier -> clips téléchargés sans terminal
- [ ] la page de progression survit à un rechargement
- [ ] tests Playwright du parcours principal (API simulée)

**Prompt Antigravity**
```
Phase 3 de docs/03-plan-attaque.md. Crée apps/web en Next.js + TypeScript + Tailwind + shadcn/ui +
TanStack Query, branché sur l'API de la phase 2. Écrans : accueil, nouveau projet (upload ou lien, options,
sélection de la facecam en dessinant un rectangle sur une image extraite), projet (progression SSE puis
grille des clips), clip (lecteur, trim, correction des sous-titres, re-rendu). Interface en français, sombre,
utilisable sur mobile. Tests Playwright du parcours principal avec l'API simulée. Utilise le navigateur
d'Antigravity pour vérifier visuellement chaque écran.
```

---

## Phase 4 : mises en page intelligentes

1. Détection automatique de la facecam (MediaPipe : un petit visage immobile dans un coin + contour du cadre avec OpenCV), enregistrée par chaîne (`CamPreset`).
2. Recadrage qui suit le visage ou l'action (position calculée par plan, lissée).
3. OCR des textes incrustés : les sous-titres se placent au-dessus.
4. Diarisation : sous-titres uniquement sur la voix du streamer (option).
5. Accroche texte en haut pendant 3 s.

**Critères** : IoU facecam >= 0,8 sur le jeu de test, aucun chevauchement sous-titres / textes incrustés sur les vidéos de test.

---

## Phase 5 : montage par consigne + éditeur

1. Schéma du plan de montage (Pydantic) et rendu ffmpeg de chaque opération.
2. Route `/clips/{id}/edit` : consigne -> plan JSON (Ollama) -> validation -> rendu.
3. Coupe des silences, zooms, textes, bruitages, musique libre de droits.
4. Intégration de Diffusion Studio editor pour la retouche manuelle.

**Critères** : 10 consignes types du plan de test donnent un rendu conforme, une consigne absurde donne un message clair.

---

## Phase 6 : publication

1. Déployer Postiz à part, créer les apps développeur TikTok, YouTube, Meta.
2. Titre, description et hashtags générés par plateforme.
3. Programmation et calendrier dans ClipFarm, appel à l'API Postiz.
4. Cloudflare Tunnel pour que TikTok récupère les vidéos.

**Critères** : un clip programmé part à l'heure sur YouTube (non répertorié) et sur TikTok (privé tant que l'app n'est pas auditée).

---

## Phase 7 : boucle d'apprentissage

1. Récupération des stats par clip.
2. Tableau de bord (vues, rétention, partages par type de moment).
3. Les meilleurs clips servent d'exemples dans le prompt de détection.
4. Option doublage (VoiceStudio en service séparé).

---

## Règles pour toutes les phases

- Une phase à la fois, tests verts avant de passer à la suivante.
- Toute fonctionnalité a au moins un test automatique, et la vérification visuelle d'une frame pour tout ce qui touche au rendu.
- Pas de nouvelle dépendance payante. Pas de code AGPL importé.
- Les métriques du plan de test sont relancées à la fin des phases 1, 4 et 5.
