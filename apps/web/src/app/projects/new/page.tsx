"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Link2, UploadCloud, Sliders, Sparkles, Loader2, Video, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { FacecamSelector, Rect } from "@/components/FacecamSelector";

export default function NewProjectPage() {
  const router = useRouter();
  const [tab, setTab] = useState<"url" | "file">("url");

  // Form states
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [extractedImage, setExtractedImage] = useState<string | null>(null);
  const [layout, setLayout] = useState("auto");
  const [format, setFormat] = useState("9:16");
  const [captions, setCaptions] = useState("punchy");
  const [skipIfSubtitlesPresent, setSkipIfSubtitlesPresent] = useState(true);
  const [maxClips, setMaxClips] = useState(5);
  const [minClipS, setMinClipS] = useState(30);
  const [maxClipS, setMaxClipS] = useState(70);
  const [camRect, setCamRect] = useState<Rect>({ x: 0.739, y: 0.083, w: 0.246, h: 0.245 });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (selectedFile: File) => {
    setFile(selectedFile);
    try {
      const objUrl = URL.createObjectURL(selectedFile);
      const video = document.createElement("video");
      video.src = objUrl;
      video.muted = true;
      video.onloadeddata = () => {
        video.currentTime = Math.min(2.0, (video.duration || 5) / 2);
      };
      video.onseeked = () => {
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth || 1280;
        canvas.height = video.videoHeight || 720;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          setExtractedImage(canvas.toDataURL("image/jpeg"));
        }
        URL.revokeObjectURL(objUrl);
      };
    } catch {
      // Ignorer si échec
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      if (tab === "url") {
        if (!url.trim()) throw new Error("Veuillez saisir une URL valide");
        const res = await api.createProjectFromUrl({
          url: url.trim(),
          layout,
          format,
          captions: captions === "none" ? undefined : captions,
          max_clips: maxClips,
          min_clip_s: minClipS,
          max_clip_s: maxClipS,
          cam: null,
          skip_if_subtitles_present: skipIfSubtitlesPresent,
        });
        router.push(`/projects/${res.project.id}`);
      } else {
        if (!file) throw new Error("Veuillez sélectionner un fichier vidéo");
        const formData = new FormData();
        formData.append("file", file);
        formData.append("layout", layout);
        formData.append("format", format);
        formData.append("captions", captions === "none" ? "" : captions);
        formData.append("max_clips", maxClips.toString());
        formData.append("min_clip_s", minClipS.toString());
        formData.append("max_clip_s", maxClipS.toString());
        formData.append("skip_if_subtitles_present", skipIfSubtitlesPresent.toString());
        if (layout.includes("facecam")) {
          formData.append("cam", JSON.stringify(camRect));
        }
        const res = await api.uploadProjectFile(formData);
        router.push(`/projects/${res.project.id}`);
      }
    } catch (err: any) {
      setError(err.message || "Une erreur est survenue lors de la création du projet");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Navigation retour */}
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-white transition"
      >
        <ArrowLeft className="h-4 w-4" />
        Retour aux projets
      </Link>

      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-white">Nouveau Projet</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Importez une vidéo longue et laissez l'IA générer des clips dynamiques avec sous-titres animés.
        </p>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/50 bg-destructive/10 p-4 text-sm text-rose-300">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Source de la vidéo */}
        <div className="rounded-2xl border border-border/80 bg-card/60 p-6 shadow-sm space-y-5">
          <h2 className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
            <Video className="h-4 w-4 text-purple-400" />
            1. Source de la vidéo
          </h2>

          <div className="flex rounded-xl bg-secondary/50 p-1 border border-border/40">
            <button
              type="button"
              onClick={() => setTab("url")}
              className={`flex-1 flex items-center justify-center gap-2 rounded-lg py-2 text-sm font-medium transition ${
                tab === "url" ? "bg-purple-600 text-white shadow-sm" : "text-muted-foreground hover:text-white"
              }`}
            >
              <Link2 className="h-4 w-4" />
              Lien web (YouTube, Twitch...)
            </button>
            <button
              type="button"
              onClick={() => setTab("file")}
              className={`flex-1 flex items-center justify-center gap-2 rounded-lg py-2 text-sm font-medium transition ${
                tab === "file" ? "bg-purple-600 text-white shadow-sm" : "text-muted-foreground hover:text-white"
              }`}
            >
              <UploadCloud className="h-4 w-4" />
              Fichier local
            </button>
          </div>

          {tab === "url" ? (
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground">URL de la vidéo</label>
              <input
                type="url"
                required={tab === "url"}
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-white placeholder-muted-foreground/60 focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
              />
            </div>
          ) : (
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground">Fichier vidéo (MP4, MKV, MOV)</label>
              <div className="relative border-2 border-dashed border-border/80 hover:border-purple-500/60 rounded-xl p-8 text-center bg-background/50 transition">
                <input
                  type="file"
                  required={tab === "file"}
                  accept="video/*"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleFileChange(f);
                  }}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
                <UploadCloud className="mx-auto h-8 w-8 text-purple-400 mb-2" />
                {file ? (
                  <p className="text-sm font-semibold text-white">{file.name} ({(file.size / 1024 / 1024).toFixed(1)} Mo)</p>
                ) : (
                  <>
                    <p className="text-sm font-medium text-white">Glissez votre vidéo ici ou cliquez pour parcourir</p>
                    <p className="text-xs text-muted-foreground mt-1">Upload en streaming direct sans saturation mémoire</p>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Options de montage & format */}
        <div className="rounded-2xl border border-border/80 bg-card/60 p-6 shadow-sm space-y-6">
          <h2 className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
            <Sliders className="h-4 w-4 text-purple-400" />
            2. Options de mise en page & style
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Format ratio */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-muted-foreground uppercase">Format de sortie</label>
              <select
                value={format}
                onChange={(e) => setFormat(e.target.value)}
                className="w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm text-white focus:border-purple-500 focus:outline-none"
              >
                <option value="9:16">9:16 - TikTok / Shorts / Reels (Vertical)</option>
                <option value="1:1">1:1 - Carré</option>
                <option value="4:5">4:5 - Instagram Portrait</option>
                <option value="16:9">16:9 - Paysage classique</option>
              </select>
            </div>

            {/* Layout */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-muted-foreground uppercase">Mise en page</label>
              <select
                value={layout}
                onChange={(e) => setLayout(e.target.value)}
                className="w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm text-white focus:border-purple-500 focus:outline-none"
              >
                <option value="auto">Auto (Détection automatique facecam / plein écran)</option>
                <option value="facecam_top">Facecam en haut / Jeu en bas</option>
                <option value="center">Centré (recadré sur l'action ou le visage)</option>
                <option value="blur">Fond flou dynamique</option>
              </select>
            </div>

            {/* Style des sous-titres */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-muted-foreground uppercase">Style de sous-titres</label>
              <select
                value={captions}
                onChange={(e) => setCaptions(e.target.value)}
                className="w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm text-white focus:border-purple-500 focus:outline-none"
              >
                <option value="punchy">Punchy (Mot actif jaune, dynamique)</option>
                <option value="clean">Clean (Blanc sobre, contour noir)</option>
                <option value="karaoke">Karaoke (Couleur progressive)</option>
                <option value="none">Aucun sous-titre</option>
              </select>
              <div className="pt-2 flex items-center gap-2">
                <input
                  type="checkbox"
                  id="skipSubtitles"
                  checked={skipIfSubtitlesPresent}
                  onChange={(e) => setSkipIfSubtitlesPresent(e.target.checked)}
                  className="rounded border-border text-purple-600 focus:ring-purple-500"
                />
                <label htmlFor="skipSubtitles" className="text-xs text-muted-foreground cursor-pointer select-none">
                  Pas de sous-titres si la vidéo en a déjà (détection auto)
                </label>
              </div>
            </div>

            {/* Nombre max de clips */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-semibold text-muted-foreground uppercase">
                <span>Nombre max de clips</span>
                <span className="text-purple-400 font-bold">{maxClips}</span>
              </div>
              <input
                type="range"
                min="1"
                max="10"
                value={maxClips}
                onChange={(e) => setMaxClips(Number(e.target.value))}
                className="w-full accent-purple-500 cursor-pointer"
              />
            </div>

            {/* Durée minimale et maximale des clips */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-muted-foreground uppercase">Durée des clips (secondes)</label>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <span className="text-[11px] text-muted-foreground">Min (défaut 30s)</span>
                  <input
                    type="number"
                    min="5"
                    max="180"
                    value={minClipS}
                    onChange={(e) => setMinClipS(Number(e.target.value))}
                    className="w-full mt-1 rounded-xl border border-border bg-background px-3 py-2 text-sm text-white focus:border-purple-500 focus:outline-none"
                  />
                </div>
                <div>
                  <span className="text-[11px] text-muted-foreground">Max (défaut 70s)</span>
                  <input
                    type="number"
                    min="10"
                    max="300"
                    value={maxClipS}
                    onChange={(e) => setMaxClipS(Number(e.target.value))}
                    className="w-full mt-1 rounded-xl border border-border bg-background px-3 py-2 text-sm text-white focus:border-purple-500 focus:outline-none"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Sélecteur de rectangle Facecam : uniquement pour fichier local si layout facecam */}
          {tab === "file" && layout.includes("facecam") && (
            <div className="pt-4 border-t border-border/40">
              <FacecamSelector imageUrl={extractedImage || undefined} initialRect={camRect} onChange={setCamRect} />
            </div>
          )}

          {tab === "url" && layout.includes("facecam") && (
            <div className="pt-4 border-t border-border/40 text-xs text-purple-300/80 bg-purple-500/10 p-3.5 rounded-xl border border-purple-500/20">
              💡 <strong>Cadrage Facecam sur lien :</strong> Dès l'import de la vidéo par le serveur, vous pourrez régler précisément la caméra sur une image extraite avant le début de l'analyse.
            </div>
          )}
        </div>

        {/* Bouton de soumission */}
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={isSubmitting}
            className="flex items-center gap-2 rounded-xl bg-purple-600 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-purple-600/30 hover:bg-purple-500 active:scale-95 disabled:opacity-50 transition"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                <span>Création en cours...</span>
              </>
            ) : (
              <>
                <Sparkles className="h-5 w-5" />
                <span>Lancer la création des clips</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
