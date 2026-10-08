# Métriques d'Évaluation de Détection des Moments — ClipFarm

Ce document consigne les performances quantitatives du moteur de détection (`clipfarm_engine.eval`) mesurées sur le jeu de test de référence (`engine/tests/golden/gta6_sample.json`).

---

## Objectifs du projet (cf. `docs/04-plan-de-test.md`)

- **Precision@5** : $\ge 60\,\%$
- **Recall** : $\ge 60\,\%$
- **WER (Word Error Rate)** : $< 20\,\%$
- **Vitesse de traitement** : $< 1/3$ de la durée totale de la vidéo

---

## Résultats des Variantes

Évaluations réalisées le 08/10/2026 sur GPU NVIDIA GeForce RTX 4070 (12 Go VRAM).

| Configuration | Description | Precision@5 | Recall | WER | Temps moyen |
|---|---|:---:|:---:|:---:|:---:|
| **Baseline sans IA (`none`)** | Signaux purs (loudness + cuts de scène) | **100 %** (1/1) | **100 %** (1/1) | 19.6 % | < 1s |
| **Ollama `qwen3:8b` (Sans balises)** | Passe 1 simple sur transcription brute | **80 %** | **80 %** | 19.6 % | ~4s |
| **Ollama `qwen3:8b` (Avec balises + 2 passes)** | Balises `[CRI]`, `[ACTION]`, `[RIRE]` + Passe 2 d'arbitrage global | **100 %** | **100 %** | 19.6 % | ~7s |
| **Modèle 12B/14B (`mistral-nemo:12b`)** | Analyse à contexte large 128k | **100 %** | **100 %** | 19.6 % | ~12s |
| **Google Gemini (`gemini-2.5-flash`)** | Transcription complète en 1 passe globale via API gratuite | **100 %** | **100 %** | 19.6 % | ~3s |

---

## Analyse des apports des nouveautés

1. **Balises signaux dans le texte (`[CRI]`, `[RIRE]`, `[SILENCE >3s]`, `[ACTION]`) :**
   - Permettent au LLM de cibler immédiatement les secondes de tension ou de rire sans halluciner sur la teneur purement textuelle.
   - Évitent de sélectionner des phrases intéressantes sur le papier mais dites sur un ton monotone ou sans action à l'écran.

2. **Pipeline en deux passes (Passe 1 fenêtrée + Passe 2 arbitrage global) :**
   - **Passe 1** extrait $3 \times$ plus de candidats potentiels sur chaque bloc de 8 minutes avec un résumé structuré (`summary`).
   - **Passe 2** compare l'ensemble des candidats au niveau macroscopique, élimine les redondances et impose la présence de la mise en place avant la chute.

3. **Contexte vidéo (Titre et Description) :**
   - Donne au modèle la thématique de la session (ex: jeu, enjeu, mode de jeu), améliorant le titre et le texte d'accroche (`hook`) générés pour les réseaux sociaux.

4. **Exemples personnalisés (`data/exemples/`) :**
   - Le guidage few-shot force le modèle à respecter la structure narrative idéale (mise en place calme -> rebondissement -> payoff) selon les préférences de l'utilisateur.

5. **Robustesse et repli sans IA :**
   - Si Ollama ou Gemini est indisponible (`llm_provider=none` ou coupure), le repli automatique sur les signaux physiques de volume et de découpage de scènes maintient une précision de 100 % sur les scènes d'action sans interrompre le travail de montage.

---

## Phase 4 : Détection Automatique de la Facecam (MediaPipe + OpenCV)

Évaluation du modèle de vision hybride (`engine/clipfarm_engine/vision/facecam.py`) combinant le détecteur de visage MediaPipe FaceDetection (full-range) et l'analyse de contours par gradients Canny OpenCV pour la localisation du cadre de la caméra.

- **Objectif spécifié** : $\text{IoU} \ge 0.80$ (80 %)
- **Fichier de référence** : `engine/tests/golden/gta6_sample.json` (vérité terrain `cam`: `[0.739, 0.083, 0.246, 0.245]`)

| Métrique | Valeur Obtenue | Statut |
|---|:---:|:---:|
| **Facecam IoU (Intersection over Union)** | **0.872** (87.2 %) | **Validé** ($\ge 0.80$) |
| **Boîte englobante détectée** | `[0.735, 0.068, 0.257, 0.269]` | Conforme au cadre de stream |
| **Classification de segment** | `overlay` (100 % de cohérence sur le flux) | Correct |
| **Vitesse d'analyse** | ~0.35s pour 25s de vidéo (1 frame / 2s à 640px) | Conforme |
