# ClipFarm : le produit

## En une phrase

Tu donnes une vidéo longue (fichier ou lien), ClipFarm trouve les meilleurs moments, en fait des clips verticaux montés et sous-titrés, puis les publie sur tes comptes.

## Pour qui

1. **Toi d'abord** : une ferme à clips pour tes contenus et les créateurs avec qui tu as un accord.
2. **Ensuite, peut-être** : un SaaS pour streamers et clippers. Angle différenciant : le gaming et le live (facecam, voix du jeu mélangée à celle du streamer, chat), là où Opus Clip, Klap ou Vizard sont faits pour les podcasts.

## Parcours principal

1. **Nouveau projet** : glisser un fichier ou coller un lien. Choisir le format (9:16, 1:1, 4:5, 16:9), la mise en page, le style de sous-titres et le nombre de clips voulus.
2. **Traitement** : barre de progression par étape (import, voix, transcription, analyse, détection, rendu). On peut fermer la page, le travail continue.
3. **Revue des clips** : liste classée par score, avec aperçu vidéo, titre, accroche, raison du choix et scores détaillés.
4. **Retouche** : ajuster début et fin, corriger un mot, déplacer la facecam, changer de style, ou écrire une consigne ("zoom quand il crie, coupe les blancs").
5. **Export ou publication** : téléchargement, ou programmation sur TikTok, YouTube Shorts, Instagram Reels, etc.
6. **Résultats** : vues et rétention remontées par clip, pour que l'IA apprenne ce qui marche.

## Fonctionnalités

Légende : **MVP** = indispensable pour la première version utilisable, **V2** = juste après, **V3** = ensuite.

### Import
| Fonction | Priorité |
|---|---|
| Upload de fichier local (gros fichiers, plusieurs Go) | MVP |
| Lien YouTube / Twitch / Kick via yt-dlp | MVP |
| Récupération du chat du live (pics de messages = moments forts) | V2 |
| Surveillance d'une chaîne : chaque nouvelle VOD est traitée automatiquement | V3 |
| Import par lot (dossier entier) | V2 |

### Analyse
| Fonction | Priorité |
|---|---|
| Transcription mot à mot (WhisperX, GPU) | MVP |
| Isolation de la voix humaine avant transcription (Demucs) | MVP |
| Volume par seconde et changements de plan (ffmpeg) | MVP (fait) |
| Distinction des voix, streamer vs personnages (diarisation pyannote) | V2 |
| Détection automatique de la facecam | V2 |
| Détection des textes déjà incrustés (OCR) pour ne pas les recouvrir | V2 |
| Détection des rires et cris | V3 |

### Détection des moments
| Fonction | Priorité |
|---|---|
| Choix par LLM local (Ollama) sur la transcription, avec scores hook, émotion, chute, autonomie | MVP |
| Classement mixte LLM + signaux audio et vidéo | MVP (fait) |
| Repli sans IA (signaux seuls) | MVP (fait) |
| Début et fin calés sur les phrases | MVP (fait) |
| Consigne libre ("que les moments drôles", "que les fails") | V2 |
| Apprentissage à partir des performances réelles | V3 |

### Rendu
| Fonction | Priorité |
|---|---|
| Formats 9:16, 1:1, 4:5, 16:9 | MVP (fait) |
| Mises en page : centrée, fond flou, facecam en haut ou en bas | MVP (fait) |
| Sous-titres mot à mot, mot actif surligné, presets de style | MVP (fait) |
| Recadrage qui suit le visage ou l'action | V2 |
| Accroche texte en haut pendant les premières secondes | V2 |
| Brand kit : logo, couleurs, police, intro et outro | V2 |
| Templates animés (Remotion) | V3 |

### Montage par consigne
| Fonction | Priorité |
|---|---|
| Consigne en français transformée en plan de montage JSON, puis rendu | V2 |
| Coupe des silences et des hésitations | V2 |
| Zooms, textes, emojis, bruitages, musique libre de droits | V2 |
| Éditeur timeline pour retoucher à la main (Diffusion Studio editor) | V2 |
| Doublage dans d'autres langues (VoiceStudio en service séparé) | V3 |

### Publication
| Fonction | Priorité |
|---|---|
| Téléchargement des clips + titre, description, hashtags générés | MVP |
| Publication et programmation via Postiz (auto-hébergé) | V2 |
| Calendrier, file d'attente, multi-comptes | V2 |
| Statistiques par clip et par plateforme | V3 |

## Ce qui est hors périmètre

- Génération de vidéo par IA (MiniMax-H3 : licence qui exclut l'UE).
- Copilote d'écran caché type `cue`.
- Tout ce qui servirait à republier le contenu d'autres créateurs sans leur accord.

## Règles produit

- Tout doit tourner gratuitement en local sur le PC (GPU NVIDIA). Un service payant ne peut être qu'une option désactivée par défaut.
- Chaque étape garde son résultat en cache : relancer un rendu avec un autre style prend quelques secondes, pas une nouvelle transcription.
- L'IA propose, l'humain valide : rien n'est publié sans un clic de validation.
