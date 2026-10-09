from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

from clipfarm_engine.config import Settings as EngineSettings
from clipfarm_engine.highlights.llm import ask_ollama, ask_gemini


def generate_publishing_metadata(
    clip_title: str,
    hook: str,
    transcript: str,
    platform: str = "youtube",
    image_paths: list[Path] | None = None,
    image_path: Path | None = None,
    creator_name: str = "",
    source_title: str = "",
    source_description: str = "",
    reason: str = "",
    scores: dict[str, Any] | None = None,
    settings: EngineSettings | None = None,
) -> dict[str, Any]:
    """
    Génère des métadonnées (titre viral, description prédictive d'engagement, tags, hashtags)
    en exploitant Google Gemini (multimodal avec vision de plusieurs images et transcription),
    avec repli sur Ollama ou heuristique robuste.
    """
    s = settings or EngineSettings()

    # Préparer les images en base64 (plans larges du tournage + plan du clip)
    all_paths: list[Path] = []
    if image_paths:
        all_paths.extend([p for p in image_paths if p and p.is_file()])
    if image_path and image_path.is_file() and image_path not in all_paths:
        all_paths.append(image_path)

    images_b64: list[tuple[str, str]] = []
    for p in all_paths[:5]:  # Maximum 5 images clés
        try:
            b64_str = base64.b64encode(p.read_bytes()).decode("utf-8")
            ext = p.suffix.lower()
            mime = "image/png" if ext == ".png" else "image/jpeg"
            images_b64.append((mime, b64_str))
        except Exception as img_err:
            print(f"[metadata] Impossible de charger l'image {p}: {img_err}")

    has_images = len(images_b64) > 0

    platform_tag = "#Shorts" if platform == "youtube" else ("#TikTok" if platform == "tiktok" else "#Reels")

    # Construction du contexte vérifié
    ground_truth_lines = []
    if creator_name:
        ground_truth_lines.append(f"- Chaîne / Créateur principal vérifié : {creator_name}")
    if source_title:
        ground_truth_lines.append(f"- Titre original de la vidéo : {source_title}")
    ground_truth_str = "\n".join(ground_truth_lines) if ground_truth_lines else "- Contexte source : Non spécifié"

    visual_section = (
        f"""ANALYSE VISUELLE MULTI-IMAGES & IDENTIFICATION DES PERSONNES ({len(images_b64)} images fournies) :
Tu as sous les yeux {len(images_b64)} images représentatives directement extraites de la vidéo (plans larges de la scène et plans du clip).
1. Examine attentivement les personnes visibles à l'écran : leurs visages, coiffures, silhouettes, logos de vêtements, décors, et accessoires.
2. Identifie qui est réellement présent dans la vidéo (le créateur/streamer, ses invités ou adversaires réels).
3. RÈGLE STRICTE ANTI-HALLUCINATION :
   - INTERDICTION ABSOLUE ET FORMELLE d'inventer des créateurs ou célébrités qui ne sont PAS dans la vidéo (ex: n'invente JAMAIS Michou, Inoxtag, Squeezie, Amixem, MrBeast... s'ils ne sont pas physiquement visibles sur les images ou explicitement au cœur de la vidéo originale).
   - Base-toi UNIQUEMENT sur les protagonistes réels visibles et sur les données vérifiées ci-dessus ({creator_name or 'le créateur'}, invités visibles)."""
        if has_images
        else """ANALYSE CONTEXTUELLE :
Aucune image disponible. Base-toi scrupuleusement sur le créateur vérifié et les dialogues.
INTERDICTION d'inventer d'autres créateurs célèbres non mentionnés dans les données fournies."""
    )

    prompt = f"""Tu es le meilleur stratège en viralité et en psychologie algorithmique sur les réseaux sociaux ({platform.upper()} Shorts / Reels).
Ton objectif est de créer un package de publication (Titre, Description, Mots-clés / Tags, Hashtags) conçu pour MAXIMISER LE CTR (Taux de Clic), LE HOOK RATE ET L'ENGAGEMENT (commentaires).

DONNÉES VÉRIFIÉES DE LA VIDÉO SOURCE :
{ground_truth_str}

DONNÉES DU CLIP :
- Titre actuel du moment : {clip_title}
- Accroche (Hook) : {hook}
- Contexte du moment fort : {reason or "Moment clé capté par l'IA"}
- Transcription des dialogues :
\"\"\"{transcript[:2500]}\"\"\"

{visual_section}

RÈGLES D'OR DE VIRALITÉ & PRÉDICTION D'ENGAGEMENT :
1. TITRE VIRAL PRÉDICTIF (Max 80 caractères) :
   - Doit créer un "Open Loop" irrésistible (boucle de curiosité ouverte) qui force à cliquer sans être du faux clickbait.
   - Mentionne le ou les VRAIS créateurs/personnes identifiées dans la scène.
   - Court, percutant, intrigant, en français naturel.
   - Ne mets pas #Shorts dans le titre du JSON (il sera ajouté automatiquement si YouTube).

2. DESCRIPTION PRÉDICTIVE D'ENGAGEMENT (4 à 5 lignes bien aérées) :
   - Ligne 1 : Accroche textuelle percutante qui contextualise la scène et les vraies personnes présentes.
   - Ligne 2-3 : Résumé croustillant de ce qui se passe réellement dans la scène.
   - Ligne finale (CRUCIALE POUR L'ALGORITHME) : Une question ouverte provocante ou polarisante invitant directement les spectateurs à débattre et commenter immédiatement.

3. TAGS & HASHTAGS :
   - 10 à 15 tags précis sans '#' (vrais noms propres des protagonistes identifiés, thématique, jeu/défi, expressions clés).
   - 5 à 8 hashtags viraux incluant {platform_tag} et le nom des créateurs réels.

Réponds STRICTEMENT par un JSON valide sans texte additionnel :
{{
  "title": "Titre choc et captivant avec les vrais protagonistes",
  "description": "Ligne d'accroche...\\n\\nCe qui se passe dans ce moment...\\n\\nEt vous, vous auriez réagi comment à sa place ? Dis-le en com !",
  "tags": ["motcle1", "motcle2", "vrai_createur", "sujet"],
  "hashtags": ["{platform_tag}", "#Viral", "#Humour", "#Tendance"]
}}"""

    raw_response = None
    try:
        # Priorité à Gemini dès qu'une clé est présente ou configurée
        if s.gemini_api_key:
            raw_response = ask_gemini(prompt, s, images_b64=images_b64 if images_b64 else None)
        elif s.llm_provider == "ollama":
            raw_response = ask_ollama(prompt, s, schema=None)
    except Exception as exc:
        print(f"[metadata] LLM non disponible ({exc}), repli heuristique.")

    if raw_response:
        try:
            clean = raw_response.strip()
            if "```" in clean:
                clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.MULTILINE)
                clean = re.sub(r"\s*```$", "", clean, flags=re.MULTILINE)
            m = re.search(r"\{.*\}", clean, re.DOTALL)
            if m:
                clean = m.group(0)
            data = json.loads(clean)
            title = str(data.get("title") or clip_title).strip()
            # Nettoyer les guillemets superflus
            title = title.strip('"\'')
            if len(title) > 85:
                title = title[:82] + "..."
            if platform == "youtube" and "#Shorts" not in title and "#shorts" not in title:
                title = f"{title} #Shorts"

            description = str(data.get("description") or f"{hook}\n\nDonne ton avis en commentaire !").strip()
            tags = [str(t).replace("#", "").strip() for t in data.get("tags") or ["shorts", "clip", "gaming"]][:20]
            hashtags = [str(h).strip() for h in data.get("hashtags") or [platform_tag, "#Viral"]][:15]

            return {
                "title": title[:100],
                "description": description,
                "tags": tags,
                "hashtags": hashtags,
            }
        except Exception as parse_err:
            print(f"[metadata] Erreur parsing JSON LLM ({parse_err}), repli heuristique.")

    # Repli déterministe
    base_title = hook if (hook and len(hook) < 80) else (clip_title or "Moment fort")
    if platform == "youtube" and "#Shorts" not in base_title:
        final_title = f"{base_title} #Shorts"
    else:
        final_title = base_title

    return {
        "title": final_title[:100],
        "description": f"{hook or clip_title}\n\nExtrait du live ! Qu'en pensez-vous ? Donnez votre avis en commentaire !\n#Shorts #Clip",
        "tags": ["shorts", "clip", "bestof", "stream"],
        "hashtags": [platform_tag, "#Clip", "#Viral"],
    }
