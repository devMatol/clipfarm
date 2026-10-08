# Installation (Windows)

## En une commande

Depuis le dossier du projet, dans PowerShell :

```
powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1
```

Options : `-SkipDocker` si tu ne veux pas encore Postgres, `-Model qwen3:14b` si ta carte a 12 Go ou plus.

Le script installe ce qui manque (Git, Node LTS, uv, ffmpeg, Ollama, Docker Desktop), crée `.env`, installe Python 3.12 et les dépendances du moteur (torch CUDA, WhisperX, Demucs, yt-dlp), télécharge le modèle LLM, lance Postgres et passe les tests.

S'il dit que des outils sont "installés mais pas encore visibles", ferme PowerShell, rouvre-le et relance.

## Comptes gratuits à créer

| Compte | Pourquoi | Quand |
|---|---|---|
| Hugging Face (jeton en lecture) | distinguer la voix du streamer des autres voix | phase 4, optionnel avant |
| Google AI Studio | option Gemini si Ollama ne suffit pas | optionnel |
| TikTok for Developers, Google Cloud (YouTube Data API), Meta for Developers | publication | phase 6 |
| Cloudflare (Tunnel) | URL publique pour TikTok | phase 6 |

Pour Hugging Face : accepter aussi les conditions du modèle de diarisation pyannote indiqué dans le README de WhisperX, sinon le jeton est refusé.

## Ouvrir le projet dans Antigravity

1. File > Open Folder > le dossier `clipfarm`.
2. L'agent lit tout seul `AGENTS.md` et `.agents/rules/`.
3. Commencer par le prompt de la phase 0 dans `docs/03-plan-attaque.md`.

## Problèmes connus

| Symptôme | Cause | Solution |
|---|---|---|
| `cublas64_12.dll is not found` | torch sans CUDA | `cd engine; uv sync --extra ai` (index cu128 déjà configuré) |
| Whisper très lent | tourne sur le processeur | vérifier `WHISPER_DEVICE=cuda` dans `.env` et `nvidia-smi` |
| Sous-titres en anglais ou absurdes | le son du jeu est transcrit | `ISOLATE_VOICE=1`, puis diarisation en phase 4 |
| `.\script.ps1 n'est pas reconnu` | PowerShell n'est pas dans le bon dossier | `cd` dans le dossier du projet d'abord |
| Ollama ne répond pas | service arrêté | lancer l'app Ollama, ou `ollama serve` |
| Postgres injoignable | Docker Desktop fermé | lancer Docker Desktop puis `docker compose -f infra/docker-compose.yml up -d` |
