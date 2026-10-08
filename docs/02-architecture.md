# Architecture technique

## Principe

Tout tourne sur ton PC Windows avec ta carte NVIDIA. Le moteur Python est en natif (accès direct au GPU), seule la base Postgres tourne dans Docker. Plus tard, le même code peut partir sur un serveur avec Dokploy.

```
 Navigateur (Next.js)  ──HTTP/SSE──>  API FastAPI  ──>  Postgres (projets, clips, jobs)
                                          │
                                          └─ file de jobs (procrastinate, dans Postgres)
                                                │
                                          Worker Python (GPU)
                                          ├─ ffmpeg          découpe, mises en page, rendu
                                          ├─ Demucs          isolation de la voix
                                          ├─ WhisperX        transcription mot à mot (+ pyannote)
                                          ├─ Ollama          choix des moments (LLM local)
                                          ├─ MediaPipe/OCR   facecam, visages, textes (V2)
                                          └─ data/projects/<id>/   fichiers et caches
                                                │
                                          Postiz (auto-hébergé) ──> TikTok, YouTube, Instagram... (V2)
```

## Briques retenues (toutes gratuites)

| Besoin | Outil | Licence | Remarque |
|---|---|---|---|
| Découpe, rendu, sous-titres | ffmpeg + libass | LGPL/GPL | Déjà validé sur la vidéo GTA |
| Téléchargement par lien | yt-dlp | Unlicense | Contraire aux conditions de YouTube : usage perso, à tes risques |
| Isolation de la voix | Demucs (htdemucs) | MIT | Retire musique et bruitages du jeu |
| Transcription mot à mot | WhisperX (faster-whisper + alignement wav2vec2) | BSD-2 | `large-v3-turbo` sur GPU |
| Distinction des voix | pyannote via WhisperX | MIT | Jeton Hugging Face gratuit à créer |
| Choix des moments | Ollama + Qwen3 8B (ou plus gros selon la VRAM) | Apache 2.0 | Local, illimité. Gemini en option (palier gratuit, données utilisées par Google) |
| Changements de plan, volume | ffmpeg (scene, astats) | | Déjà codé |
| Visages, facecam | MediaPipe + OpenCV | Apache 2.0 / Apache 2.0 | V2 |
| Textes à l'écran | RapidOCR | Apache 2.0 | V2 |
| API | FastAPI + SQLModel | MIT | |
| File de jobs | procrastinate (dans Postgres) | MIT | Pas besoin de Redis, marche sur Windows |
| Base | Postgres 17 (Docker) | PostgreSQL | |
| Front | Next.js + TypeScript + Tailwind + shadcn/ui + TanStack Query | MIT | |
| Éditeur timeline | Diffusion Studio editor | MPL-2.0 | V2. Publier les fichiers de ce repo que tu modifies |
| Templates animés | Remotion | Gratuit jusqu'à 3 personnes | V3 |
| Publication | Postiz auto-hébergé | AGPL-3.0 | Tourne à part, on l'appelle par son API publique : ton code reste fermé |
| Doublage | VoiceStudio | AGPL-3.0 | V3, service séparé pour la même raison |
| Accès public pour TikTok | Cloudflare Tunnel | Gratuit | TikTok va chercher la vidéo sur une URL https publique |
| Déploiement serveur | Dokploy | | Plus tard, si tu passes en SaaS |

Repo de référence à lire (pas à copier) : SupoClip (AGPL-3.0), un clone open source d'Opus Clip avec FastAPI, Next.js et face tracking. Bonne source d'idées. Si tu reprends son code, ton projet devient AGPL.

## Matériel & Choix des Modèles LLM

Pour connaître votre VRAM disponible sous Windows :
```powershell
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv
```

### Tableau de sélection `OLLAMA_MODEL` selon la VRAM

| VRAM GPU | Modèle conseillé (`OLLAMA_MODEL`) | Commande d'installation | Caractéristiques |
|---|---|---|---|
| **<= 6 Go** | `qwen2.5:7b-instruct-q4_k_m` ou `qwen3:4b` | `ollama pull qwen2.5:7b` | Empreinte légère (~4,5 Go), inférence rapide. |
| **8 Go** | `qwen3:8b` *(défaut)* ou `llama3.1:8b` | `ollama pull qwen3:8b` | Excellent compromis français / structuration JSON / virilité des hooks. |
| **12 Go** | `mistral-nemo:12b` ou `qwen2.5:14b-instruct-q4_0` | `ollama pull mistral-nemo` | Contexte étendu (128k), très haute fidélité d'analyse. |
| **>= 16 Go** | `qwen2.5:14b` ou `command-r:35b` | `ollama pull qwen2.5:14b` | Analyse sémantique de niveau professionnel. |

> **Note GPU** : Whisper et Ollama ne tournent pas simultanément : le pipeline les exécute séquentiellement (Whisper libère la mémoire avant l'inférence LLM).

### Option `LLM_PROVIDER=gemini` (Palier gratuit)

Pour utiliser Google Gemini avec son contexte étendu (1 million de tokens) :
1. Définir dans `.env` :
   ```env
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=votre_cle_gratuite
   GEMINI_MODEL=gemini-2.5-flash
   ```
2. **Avantage** : Permet d'envoyer l'intégralité de la transcription annotée en une seule fois sans découpage en fenêtres, avec analyse globale immédiate. Gratuit jusqu'à 15 requêtes/minute.


## Arborescence

```
clipfarm/
├─ AGENTS.md                  contexte permanent pour l'agent Antigravity
├─ .agents/rules/             règles par zone du code
├─ .agents/skills/            procédures réutilisables (rendu, tests, livraison de phase)
├─ docs/                      produit, architecture, plan d'attaque, plan de test, installation
├─ engine/                    moteur Python (déjà fonctionnel en CLI)
│  ├─ clipfarm_engine/
│  │  ├─ media/               ffmpeg, mises en page, rendu
│  │  ├─ captions/            sous-titres ASS mot à mot
│  │  ├─ transcribe/          Demucs + WhisperX
│  │  ├─ highlights/          signaux, LLM, sélection
│  │  ├─ pipeline.py          orchestration avec cache
│  │  ├─ eval.py              métriques sur le jeu de test annoté
│  │  └─ __main__.py          CLI
│  └─ tests/                  pytest, médias de test générés par ffmpeg
├─ api/                       FastAPI + worker (phase 2, à créer)
├─ apps/web/                  Next.js (phase 3, à créer)
├─ infra/docker-compose.yml   Postgres (+ adminer)
├─ scripts/setup-windows.ps1  installation en une commande
└─ data/                      projets et clips (ignoré par git)
```

## Pipeline du moteur

Chaque étape écrit son résultat dans `data/projects/<id>/` et le réutilise si le fichier existe.

| Étape | Entrée | Sortie | Statut |
|---|---|---|---|
| ingest | fichier ou lien | `source.json` ou `source.mp4` | fait |
| audio | source | `audio.wav` 16 kHz mono | fait |
| voice | audio.wav | `voice/htdemucs/audio/vocals.wav` | codé, à valider sur GPU |
| transcribe | voix | `words.json` (mot, début, fin, confiance, locuteur) | codé, à valider sur GPU |
| signals | source | `signals.json` (volume/seconde, coupes) | fait |
| highlights | mots + signaux | `highlights.json` (classé) | fait avec repli sans IA, appel Ollama à valider |
| render | candidats | `clips/NN.raw.mp4`, `NN.ass`, `NN.mp4`, `manifest.json` | fait |

Score final d'un clip : `0,75 x score LLM + 0,25 x score des signaux` (0,75 passe à 0 si pas de LLM). Les clips qui se chevauchent à plus de 30 % sont éliminés.

## Modèle de données (phase 2)

```
Project      id, source_url, source_path, status, progress, step, duration, settings(json), error, created_at
Clip         id, project_id, index, start, end, title, hook, reason, scores(json), final_score,
             layout(json), captions(json), edit_plan(json), file_path, status, created_at
CamPreset    id, channel, rect(json)            facecam mémorisée par chaîne
BrandKit     id, name, font, colors(json), logo_path, intro_path, outro_path
Publication  id, clip_id, platform, account, caption, scheduled_at, status, external_id, url, metrics(json)
```

Statuts d'un projet : `queued, ingesting, transcribing, analysing, detecting, rendering, ready, failed`.

## API (phase 2)

| Méthode | Route | Rôle |
|---|---|---|
| POST | `/projects` | créer depuis un lien (JSON) ou un fichier (multipart en streaming) |
| GET | `/projects` | liste |
| GET | `/projects/{id}` | statut, progression, clips |
| GET | `/projects/{id}/events` | progression en direct (SSE) |
| POST | `/projects/{id}/render` | re-rendu avec d'autres options (layout, format, style) |
| PATCH | `/clips/{id}` | modifier début, fin, titre, mots des sous-titres |
| POST | `/clips/{id}/edit` | consigne en français, renvoie et applique un plan de montage (V2) |
| GET | `/media/{path}` | servir les vidéos et miniatures |
| POST | `/clips/{id}/publish` | programmer via Postiz (V2) |

## Plan de montage par consigne (V2)

Le LLM ne touche jamais à ffmpeg directement. Il produit un JSON validé, que le moteur applique :

```json
{
  "trim": {"start": 1.2, "end": 38.5},
  "cut_silences": {"min_silence": 0.6},
  "zooms": [{"start": 4.0, "end": 6.0, "scale": 1.3, "target": "face"}],
  "texts": [{"start": 0, "end": 3, "content": "IL A PAS VU VENIR", "position": "top", "style": "hook"}],
  "sfx": [{"at": 4.0, "name": "boom"}],
  "music": {"track": "lofi_01", "volume": 0.15},
  "captions": {"preset": "punchy", "position": "bottom"}
}
```

Validation par schéma (Pydantic) avant rendu. Une consigne mal comprise donne une erreur lisible, jamais un rendu cassé.

## Publication (V2)

Postiz tourne à part (son propre `docker compose`, voir docs.postiz.com). ClipFarm appelle son API publique pour créer les posts.

Points à connaître :
- **TikTok** : il faut ta propre app développeur TikTok. Tant qu'elle n'a pas passé l'audit, les posts sont forcés en privé et limités à 5 comptes par 24 h. La vidéo doit être accessible en https public (Cloudflare Tunnel).
- **YouTube** : API gratuite avec un quota quotidien. Chaque upload en consomme une grosse part, donc quelques vidéos par jour.
- **Instagram** : compte professionnel + app Meta validée.

## Sécurité et licences

- `.env` jamais commité. Jetons (HF, Gemini, Postiz) uniquement dans `.env`.
- Ne pas importer de code AGPL (Postiz, VoiceStudio, SupoClip) dans `engine/`, `api/` ou `apps/web/` : on les appelle comme services.
- Diffusion Studio editor (MPL-2.0) : les fichiers du repo que tu modifies restent publics, ton code autour peut rester fermé.
