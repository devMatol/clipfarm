---
name: render-clip
description: Rendre ou re-rendre un clip ClipFarm avec une mise en page (centree, flou, facecam), un format et des sous-titres, puis verifier visuellement le resultat. A utiliser pour tester un rendu, regler la zone facecam ou deboguer un probleme d'image ou de sous-titres.
---

# Rendre un clip et le verifier

1. Pipeline complet (cache reutilise si deja fait) :
   `cd engine; uv run python -m clipfarm_engine run "<source>" --layout <center|blur|facecam_top|facecam_bottom> --format 9:16 --cam x,y,w,h`
2. Trouver la zone facecam : extraire une image de la source
   `ffmpeg -ss 60 -i "<source>" -frames:v 1 frame.png`, l'ouvrir, mesurer le cadre de la camera et le convertir en fractions de la largeur et hauteur (x, y, w, h entre 0 et 1).
3. Verifier chaque clip : `ffmpeg -ss 5 -i data/projects/<id>/clips/01.mp4 -frames:v 1 check.png` puis ouvrir l'image.
4. Checklist visuelle :
   - dimensions exactes du format (ffprobe)
   - tete du streamer entiere, pas de bord d'overlay visible
   - sous-titres de 3 mots max, mot actif en jaune, pas sur les textes du jeu
   - jeu centre sur l'action
5. Si un reglage change, relancer : seul le rendu est refait (transcription en cache).
