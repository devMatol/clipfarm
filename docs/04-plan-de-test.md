# Plan de test

## Niveaux de test

| Niveau | Outil | Quand | Ce qui est vérifié |
|---|---|---|---|
| Unitaires | pytest | à chaque modif | sous-titres, mises en page, signaux, parseur LLM, sélection, métriques |
| Médias synthétiques | pytest + ffmpeg | à chaque modif | vidéo générée (3 scènes, pic sonore à 45-55 s) : rendu aux bonnes dimensions, pic détecté, coupes trouvées |
| GPU | pytest `-m gpu` | fin de phase 1, 4, 5 | WhisperX, Demucs, Ollama réels sur un extrait court |
| Qualité (golden) | `clipfarm_engine.eval` | fin de phase 1, 4, 5 | transcription, choix des moments, facecam sur de vraies vidéos annotées |
| API | pytest + httpx | phase 2+ | routes, statuts, erreurs, file de jobs, pipeline simulé |
| Interface | Playwright | phase 3+ | parcours complet, API simulée |
| Visuel | humain + frames | chaque phase rendu | une capture par clip et par mise en page |

État actuel : **22 tests verts** (sous-titres, mises en page, signaux, sélection, pipeline complet sans IA, métriques). Un run réel sur la vidéo GTA (480p) a aussi produit des clips 1080x1920 avec facecam en haut.

## Jeu de test annoté (golden set)

Dossier `engine/tests/golden/`. Un fichier JSON par vidéo (format dans `engine/clipfarm_engine/eval.py`) :

```json
{
  "source": "C:/Users/matth/Videos/stream/session_01.mp4",
  "moments": [{"start": 545, "end": 585, "why": "réaction forte au braquage"}],
  "transcript_ref": [{"start": 550.0, "end": 556.0, "text": "ce qu'il dit vraiment, tapé à la main"}],
  "cam": [0.739, 0.083, 0.246, 0.245]
}
```

Composition visée (vidéos à toi ou avec accord) :
1. Stream gaming avec facecam, voix + jeu bruyant (le cas GTA)
2. Stream sans facecam
3. Discussion face caméra (podcast, vlog)
4. Vidéo avec textes incrustés en bas
5. Vidéo très calme (pour vérifier qu'on ne sort pas de faux moments forts)

Pour chaque vidéo : noter 5 à 10 moments que tu posterais vraiment, retaper 5 phrases du streamer à la main, mesurer la facecam une fois.

## Objectifs chiffrés

| Métrique | Calcul | Objectif MVP | Objectif V2 |
|---|---|---|---|
| WER voix streamer | mots faux / mots de référence | < 20 % | < 12 % |
| precision@5 | part des 5 premiers clips qui recoupent un moment annoté (>= 50 %) | >= 60 % | >= 75 % |
| recall | part des moments annotés retrouvés | >= 50 % | >= 70 % |
| IoU facecam | recouvrement détection / annotation | (manuel au MVP) | >= 0,8 |
| Synchro sous-titres | écart début du mot affiché / début réel | < 150 ms | < 100 ms |
| Temps de traitement | durée totale / durée de la vidéo | < 0,33 | < 0,2 |
| Taux de rendu réussi | clips valides / clips demandés | 100 % | 100 % |

Les résultats de chaque run vont dans `docs/metrics.md` (date, réglages, chiffres), pour voir si une modification améliore ou dégrade.

## Cas de test fonctionnels

### Import
- [ ] fichier mp4, mkv, mov, avec et sans audio
- [ ] fichier avec une image de couverture en piste vidéo (le cas GTA 480p) : la vraie piste est utilisée
- [ ] chemin Windows avec espaces, parenthèses, accents
- [ ] lien YouTube valide, lien invalide (erreur lisible), vidéo privée
- [ ] fichier de plus de 2 Go

### Transcription
- [ ] voix seule : WER faible
- [ ] voix + jeu en anglais : le texte reste en français et ne reprend pas les dialogues du jeu (le bug vu sur le clip "Some sparkling water")
- [ ] passage sans parole : aucun sous-titre inventé ("...", phrases répétées)
- [ ] mots à faible confiance retirés

### Détection
- [ ] chaque clip entre MIN_CLIP_S et MAX_CLIP_S
- [ ] début en début de phrase, fin en fin de phrase
- [ ] pas deux clips qui se chevauchent à plus de 30 %
- [ ] Ollama arrêté : repli sur les signaux, avec un avertissement, pas de crash
- [ ] réponse LLM mal formée : fenêtre ignorée, le reste continue

### Rendu
- [ ] chaque format sort aux dimensions exactes (1080x1920, 1080x1080, 1080x1350, 1920x1080)
- [ ] facecam en haut : la tête n'est pas coupée, pas de bord de l'overlay visible
- [ ] sous-titres : 3 mots max, mot actif surligné, jamais sur les textes du jeu
- [ ] son présent et synchrone
- [ ] relancer le rendu seul réutilise la transcription (moins d'1 min)

### Montage par consigne (phase 5)
Dix consignes de référence, chacune avec le résultat attendu :
1. "coupe les blancs" -> durée réduite, aucun silence > 0,6 s
2. "zoom sur sa tête quand il crie" -> zooms sur les pics de volume
3. "mets IL A PAS VU VENIR en haut au début" -> texte de 0 à 3 s
4. "sous-titres en vert" -> preset modifié
5. "ajoute un boom à 4 secondes" -> bruitage à 4 s
6. "musique lofi en fond très bas" -> piste à faible volume
7. "commence 2 secondes plus tôt" -> trim ajusté
8. "format carré" -> 1080x1080
9. "enlève les gros mots des sous-titres" -> mots masqués
10. "fais un truc impossible" -> message clair, aucun rendu cassé

### Publication (phase 6)
- [ ] programmation à une heure précise, envoi à l'heure
- [ ] erreur plateforme (jeton expiré) : statut `failed` + message, rien de perdu
- [ ] TikTok non audité : post privé, comme prévu

## Vérification visuelle

Pour tout changement de rendu, extraire une frame par clip et la regarder :
```
ffmpeg -ss 5 -i data/projects/<id>/clips/01.mp4 -frames:v 1 check.png
```
Antigravity peut le faire et ouvrir l'image lui-même : le demander dans le prompt de phase.

## Commandes

```
cd engine
uv run pytest -q                 # tests rapides (sans GPU)
uv run pytest -q -m gpu          # tests IA réels (phase 1+)
uv run python -m clipfarm_engine.eval tests/golden/session_01.json ../data/projects/<id>
```
