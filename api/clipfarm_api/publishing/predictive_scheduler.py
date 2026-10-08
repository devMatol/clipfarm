from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from clipfarm_engine.config import Settings as EngineSettings
from clipfarm_engine.highlights.llm import ask_gemini, ask_ollama


PARIS_TZ = ZoneInfo("Europe/Paris")


FRENCH_ALGORITHMIC_SLOTS = [
    # (day_of_week 0=Monday, 6=Sunday, hour, minute, name, audience_type, weight)
    (6, 18, 45, "Grand Pic Dominical", "Divertissement familial & record hebdo", 1.0),
    (6, 20, 30, "Prime Dimanche Soir", "Audience captive canapé", 0.95),
    (2, 18, 30, "Pic Mercredi Soir", "Jeunes & Gamers", 0.92),
    (4, 19, 0, "Soirée Vendredi Début Weekend", "Pop culture & punchlines", 0.90),
    (5, 18, 45, "Samedi Soir Détente", "Divertissement chill", 0.88),
    (0, 18, 15, "Lundi Décompression", "Moments courts & humour", 0.82),
    (3, 18, 30, "Jeudi Soir", "High retention", 0.84),
    (1, 18, 15, "Mardi Soir", "Audience active", 0.80),
    (2, 14, 30, "Mercredi Après-Midi", "Collégiens / Lycéens / Étudiants", 0.85),
    (5, 12, 15, "Samedi Déjeuner", "Mobile chill", 0.78),
    (6, 12, 0, "Dimanche Midi", "Avant-première", 0.80),
    (0, 12, 30, "Pause Déjeuner Lundi", "Consommation express", 0.75),
    (3, 12, 30, "Pause Déjeuner Jeudi", "Consommation express", 0.75),
    (4, 12, 30, "Pause Déjeuner Vendredi", "Consommation express", 0.77),
]


def predict_schedule_with_gemini(
    clips: list[dict[str, Any]],
    existing_publications: list[dict[str, Any]],
    target_platforms: list[str],
    start_date: datetime | None = None,
    days_ahead: int = 7,
    settings: EngineSettings | None = None,
) -> dict[str, Any]:
    """
    Analyse les clips disponibles et utilise Google Gemini pour élaborer un calendrier
    de publication prédictif et algorithmiquement optimal.
    """
    s = settings or EngineSettings()
    now_paris = datetime.now(PARIS_TZ)
    base_start = start_date.astimezone(PARIS_TZ) if start_date else (now_paris + timedelta(hours=1))

    if not clips:
        return {"predictions": [], "summary": "Aucun clip à planifier."}

    # Préparation du contexte des clips
    clips_context = []
    for c in clips:
        clips_context.append({
            "id": c.get("id"),
            "index": c.get("index"),
            "title": c.get("title", ""),
            "hook": c.get("hook", ""),
            "reason": c.get("reason", ""),
            "duration_s": round(float(c.get("end", 0)) - float(c.get("start", 0)), 1),
            "scores": c.get("scores", {}),
            "transcript_sample": c.get("transcript", "")[:600],
        })

    # Contexte des publications déjà planifiées pour éviter l'auto-cannibalisation
    existing_context = []
    for pub in existing_publications:
        sched = pub.get("scheduled_at")
        if sched:
            existing_context.append({
                "platform": pub.get("platform"),
                "scheduled_at": sched.isoformat() if hasattr(sched, "isoformat") else str(sched),
                "title": (pub.get("metadata_json") or {}).get("title", "Clip"),
            })

    platforms_str = ", ".join(target_platforms) if target_platforms else "youtube"

    prompt = f"""Tu es le meilleur stratège en algorithmes de recommandation (YouTube Shorts, TikTok, Instagram Reels) pour le marché francophone (France / Fuseau Europe/Paris).
Ta mission est de construire un CALENDRIER DE PUBLICATION PRÉDICTIF OPTIMAL pour une série de clips vidéo courts.

DONNÉES DU PROJET :
- Date de début de programmation : {base_start.strftime("%Y-%m-%d %H:%M")} (heure de Paris)
- Fenêtre de planification : {days_ahead} prochains jours
- Plateformes cibles : {platforms_str}
- Publications déjà prévues dans l'agenda (À NE PAS SURCHARGER / RESPECTER AU MOINS 3H D'ESPACEMENT SUR LA MÊME PLATEFORME) :
{json.dumps(existing_context, ensure_ascii=False, indent=2)}

CLIPS À PROGRAMMER ({len(clips_context)} clips) :
{json.dumps(clips_context, ensure_ascii=False, indent=2)}

RÈGLES D'OR DE L'ALGORITHME ET DE LA PSYCHOLOGIE SOCIALE :
1. PICS D'AUDIENCE ET RETENTION (FRANCE) :
   - Mercredi fin d'après-midi (18h-19h30) et Dimanche fin de journée (17h30-21h) sont les créneaux ROIS à réserver IMPÉRATIVEMENT aux clips ayant le plus fort potentiel viral (meilleur hook, scores élevés).
   - Les clips très courts (< 25s) et rythmés performent extrêmement bien lors des pauses déjeuner (12h15-13h30).
   - Les clips avec un récit ou une émotion forte cartonnent le soir (18h30-20h30).
2. ESPACEMENT ANTI-CANNIBALISATION :
   - Maximum 1 publication par jour par plateforme (ou au grand minimum 4h d'écart) pour laisser à l'algorithme le temps d'attribuer ses impressions initiales.
3. SCORING PRÉDICTIF :
   - Assigne à chaque créneau proposé une note prédictive entre 70 et 99 reflétant l'alignement entre la nature du clip et l'état psychologique de l'audience à cette heure-là.
4. RAISONNEMENT ALGORITHMIQUE :
   - Explique précisément et techniquement en français pourquoi ce moment exact maximise le Hook Rate, l'Average View Duration (AVD) et le partage.

Réponds STRICTEMENT sous forme d'un objet JSON valide conforme à cette structure exacte :
{{
  "summary": "Résumé stratégique global de la planification (ex: 3 clips répartis sur les pics clés Mercredi, Vendredi et Dimanche pour maximiser la rétention globale)",
  "predictions": [
    {{
      "clip_id": "id_du_clip",
      "platform": "youtube",
      "suggested_time": "2026-10-09T18:45:00+02:00",
      "day_name": "Vendredi",
      "slot_name": "Grand Pic Soirée (18h-20h)",
      "predictive_score": 94,
      "algorithmic_reason": "Explication algorithmique détaillée (taux de complétion, pic d'audience, psychologie)",
      "viral_title": "Titre optimisé à fort CTR pour ce créneau",
      "viral_description": "Description incitative avec call-to-action en commentaire",
      "viral_tags": ["tag1", "tag2", "tag3"]
    }}
  ]
}}"""

    raw_response = None
    try:
        if s.gemini_api_key:
            raw_response = ask_gemini(prompt, s)
        elif s.llm_provider == "ollama":
            raw_response = ask_ollama(prompt, s, schema=None)
    except Exception as exc:
        print(f"[predictive_scheduler] LLM request failed ({exc}), falling back to algorithmic heuristic.")

    if raw_response:
        try:
            clean = raw_response.strip()
            if "```" in clean:
                clean = re.sub(r"^```[a-zA-Z]*\n", "", clean)
                clean = re.sub(r"\n```$", "", clean)
            parsed = json.loads(clean.strip())
            if isinstance(parsed, dict) and "predictions" in parsed and parsed["predictions"]:
                # Normaliser et vérifier les dates
                for item in parsed["predictions"]:
                    item.setdefault("platform", target_platforms[0] if target_platforms else "youtube")
                return parsed
        except Exception as parse_err:
            print(f"[predictive_scheduler] Erreur parsing JSON Gemini: {parse_err}. Repli heuristique.")

    # Repli Heuristique Algorithmique Avancé
    return _algorithmic_heuristic_schedule(
        clips=clips_context,
        existing_context=existing_context,
        target_platforms=target_platforms,
        base_start=base_start,
        days_ahead=days_ahead,
    )


def _algorithmic_heuristic_schedule(
    clips: list[dict[str, Any]],
    existing_context: list[dict[str, Any]],
    target_platforms: list[str],
    base_start: datetime,
    days_ahead: int = 7,
) -> dict[str, Any]:
    """
    Planificateur algorithmique de secours qui place chaque clip sur les meilleurs
    créneaux statistiques français tout en évitant les collisions.
    """
    sorted_clips = sorted(
        clips,
        key=lambda c: (
            float((c.get("scores") or {}).get("hook", 5.0))
            + float((c.get("scores") or {}).get("emotion", 5.0))
            + float((c.get("scores") or {}).get("payoff", 5.0))
        ),
        reverse=True,
    )

    taken_slots: set[str] = set()
    for pub in existing_context:
        dt_str = pub.get("scheduled_at")
        if dt_str:
            try:
                dt = datetime.fromisoformat(dt_str)
                # Bloquer le créneau +/- 2 heures
                for delta_h in (-2, -1, 0, 1, 2):
                    block = (dt + timedelta(hours=delta_h)).strftime("%Y-%m-%d_%H")
                    taken_slots.add(block)
            except Exception:
                pass

    available_slots: list[tuple[datetime, str, str, float]] = []
    # Générer les créneaux pour les jours à venir
    for day_offset in range(days_ahead):
        cur_day = base_start + timedelta(days=day_offset)
        weekday = cur_day.weekday()
        for s_wday, s_h, s_m, slot_name, aud, weight in FRENCH_ALGORITHMIC_SLOTS:
            if weekday == s_wday:
                candidate_dt = cur_day.replace(hour=s_h, minute=s_m, second=0, microsecond=0)
                if candidate_dt > base_start:
                    slot_key = candidate_dt.strftime("%Y-%m-%d_%H")
                    if slot_key not in taken_slots:
                        available_slots.append((candidate_dt, slot_name, aud, weight))

    # Trier les créneaux disponibles par poids algorithmique décroissant
    available_slots.sort(key=lambda s: s[3], reverse=True)

    predictions = []
    platform = target_platforms[0] if target_platforms else "youtube"
    french_days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

    for i, clip in enumerate(sorted_clips):
        if i < len(available_slots):
            slot_dt, slot_name, slot_aud, weight = available_slots[i]
        else:
            # S'il n'y a plus de créneaux haute pondération, programmer le lendemain à 18h30
            slot_dt = base_start + timedelta(days=i + 1, hours=18 - base_start.hour, minutes=30 - base_start.minute)
            slot_name = "Créneau Soirée Standard"
            slot_aud = "Audience globale"
            weight = 0.75

        # Score prédictif basé sur l'alignement hook x créneau
        base_score = 75 + int(weight * 20)
        dur = clip.get("duration_s", 30)
        if dur < 25:
            reason = f"{slot_name} : format très punchy ({dur}s) idéal pour un taux de complétion maximal et un boost immédiat par l'algorithme."
        else:
            reason = f"{slot_name} : créneau à forte rétention ({slot_aud}), parfait pour valoriser la montée en tension et la conclusion de ce moment."

        predictions.append({
            "clip_id": clip.get("id"),
            "clip_title": clip.get("title") or f"Clip #{clip.get('index', i+1)}",
            "hook": clip.get("hook", ""),
            "platform": platform,
            "suggested_time": slot_dt.isoformat(),
            "day_name": french_days[slot_dt.weekday()],
            "slot_name": slot_name,
            "predictive_score": min(98, base_score),
            "algorithmic_reason": reason,
            "viral_title": clip.get("title") or f"Moment d'anthologie #{clip.get('index', i+1)}",
            "viral_description": f"{clip.get('hook', 'Regarde jusqu\'à la fin !')}\n\nQu'est-ce que vous en pensez ? Donnez votre avis en commentaire !",
            "viral_tags": ["Shorts", "Viral", "Humour", "Gaming", "BestOf"],
        })

    # Trier les prédictions par ordre chronologique
    predictions.sort(key=lambda p: p["suggested_time"])

    return {
        "summary": f"Planification optimisée par algorithme : {len(predictions)} clips répartis sur les créneaux d'engagement maximal.",
        "predictions": predictions,
    }
