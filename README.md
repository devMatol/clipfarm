# ClipFarm

Vidéo longue (fichier ou lien) -> meilleurs moments détectés par IA -> clips verticaux mis en page et sous-titrés -> publication. 100 % gratuit, en local sur ton PC.

## Démarrer l'application MVP (sans terminal)

Une seule commande lance Postgres, l'API FastAPI, le worker GPU et le frontend Web :
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```
Puis ouvre ton navigateur sur **http://localhost:3000** !

Pour la documentation interactive de l'API : **http://localhost:8000/docs**.

## Ce qui marche déjà (moteur en ligne de commande)

```
cd engine
uv run python -m clipfarm_engine run "C:\chemin\video.mp4" --layout facecam_top --cam 0.739,0.083,0.246,0.245
```

- Détection des moments : LLM local (Ollama) + volume + changements de plan, avec repli sans IA
- Mises en page : centrée, fond flou, facecam en haut ou en bas
- Formats : 9:16, 1:1, 4:5, 16:9
- Sous-titres mot à mot, mot actif surligné
- Cache par étape dans `data/projects/<id>/`

Options utiles : `--llm none` (sans IA), `--no-transcribe` (sans sous-titres), `--max-clips 5`, `--captions clean`.

## Documentation

| Fichier | Contenu |
|---|---|
| `docs/01-produit.md` | fonctionnalités et priorités |
| `docs/02-architecture.md` | stack gratuite, licences, données, API |
| `docs/03-plan-attaque.md` | les 8 phases avec critères et prompts Antigravity |
| `docs/04-plan-de-test.md` | tests, jeu annoté, objectifs chiffrés |
| `docs/05-installation.md` | installation et problèmes connus |
| `AGENTS.md`, `.agents/` | règles et procédures lues par l'agent |
