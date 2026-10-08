"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Play,
  RotateCcw,
  Sparkles,
  Sliders,
  ExternalLink,
  Flame,
  ChevronDown,
  ChevronUp,
  Trash2,
} from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Project, ProgressEvent, Clip } from "@/lib/types";
import { FacecamSelector, Rect } from "@/components/FacecamSelector";

const STEPS_ORDER = [
  { id: "ingest", label: "Téléchargement / Ingestion" },
  { id: "voice", label: "Isolation vocale (Demucs)" },
  { id: "transcribe", label: "Transcription WhisperX" },
  { id: "signals", label: "Volume & Changements de plan" },
  { id: "highlights", label: "Sélection des meilleurs moments" },
  { id: "render", label: "Montage & Rendu vertical" },
  { id: "done", label: "Prêt" },
];

export default function ProjectDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [liveProgress, setLiveProgress] = useState<ProgressEvent | null>(null);
  const [camRect, setCamRect] = useState<Rect>({ x: 0.739, y: 0.083, w: 0.246, h: 0.245 });
  const [isSubmittingCam, setIsSubmittingCam] = useState(false);
  const [isEditingCam, setIsEditingCam] = useState(false);
  const [showFallbackClips, setShowFallbackClips] = useState(false);

  // Charger le projet
  const { data: project, isLoading, error, refetch } = useQuery<Project>({
    queryKey: ["project", id],
    queryFn: () => api.getProject(id),
    refetchInterval: (query) => {
      const p = query.state.data;
      if (
        p &&
        (!["ready", "failed", "awaiting_cam"].includes(p.status) ||
          p.clips?.some((c) => c.status === "rendering"))
      ) {
        return 1500;
      }
      return false;
    },
  });

  // Mettre à jour camRect si le projet a un cadrage existant ou détecté
  useEffect(() => {
    if (project) {
      if (project.settings_json?.cam) {
        setCamRect(project.settings_json.cam);
      } else if (project.detected_cam) {
        setCamRect({
          x: project.detected_cam[0],
          y: project.detected_cam[1],
          w: project.detected_cam[2],
          h: project.detected_cam[3],
        });
      }
    }
  }, [project]);

  const handleSetCam = async () => {
    setIsSubmittingCam(true);
    try {
      await api.setCam(id, camRect);
      refetch();
    } catch (err: any) {
      alert(err.message || "Erreur enregistrement facecam");
    } finally {
      setIsSubmittingCam(false);
    }
  };

  // Abonnement SSE pour progression en direct
  useEffect(() => {
    if (!id) return;
    const sseUrl = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/projects/${id}/events`;
    const eventSource = new EventSource(sseUrl);

    eventSource.addEventListener("progress", (e) => {
      try {
        const data: ProgressEvent = JSON.parse(e.data);
        setLiveProgress(data);
        if (data.status === "ready" || data.status === "failed") {
          queryClient.invalidateQueries({ queryKey: ["project", id] });
          queryClient.invalidateQueries({ queryKey: ["projects"] });
        }
      } catch (err) {
        console.error("Erreur parsing SSE:", err);
      }
    });

    eventSource.onerror = () => {
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [id, queryClient]);

  const handleRetry = async () => {
    try {
      await api.retryProject(id);
      refetch();
    } catch (err) {
      alert("Erreur lors de la relance du projet");
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
        <Loader2 className="h-8 w-8 animate-spin text-purple-400" />
        <p className="mt-3 text-sm">Chargement du projet...</p>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="rounded-xl border border-destructive/50 bg-destructive/10 p-6 text-center text-rose-300">
        <AlertCircle className="mx-auto h-8 w-8 text-rose-400 mb-2" />
        <p className="font-semibold">Projet introuvable</p>
        <Link href="/" className="mt-4 inline-block text-xs text-purple-400 underline">
          Retour à l'accueil
        </Link>
      </div>
    );
  }

  const currentStatus = liveProgress?.status || project.status;
  const currentProgress = liveProgress ? liveProgress.progress : project.progress;
  const currentStep = liveProgress ? liveProgress.step : project.step;
  const currentMessage = liveProgress?.message || "";
  const isFinished = currentStatus === "ready";
  const isFailed = currentStatus === "failed";

  return (
    <div className="space-y-8">
      {/* En-tête */}
      <div className="space-y-3">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-white transition"
        >
          <ArrowLeft className="h-4 w-4" />
          Retour aux projets
        </Link>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                #{project.id}
              </span>
              <h1 className="text-2xl font-bold text-white">
                {project.source_url || (project.source_path ? project.source_path.split(/[\\/]/).pop() : project.id)}
              </h1>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Créé le {new Date(project.created_at).toLocaleString("fr-FR")} • Format : {project.settings_json?.format || "9:16"}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {isFailed && (
              <button
                onClick={handleRetry}
                className="inline-flex items-center gap-2 rounded-xl bg-purple-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-purple-500 transition"
              >
                <RotateCcw className="h-4 w-4" />
                Réessayer
              </button>
            )}

            <button
              onClick={async () => {
                if (confirm(`Êtes-vous sûr de vouloir supprimer définitivement le projet #${project.id} et tous ses clips ?`)) {
                  try {
                    await api.deleteProject(project.id);
                    queryClient.invalidateQueries({ queryKey: ["projects"] });
                    router.push("/");
                  } catch (err: any) {
                    alert(err.message || "Erreur lors de la suppression du projet");
                  }
                }
              }}
              className="inline-flex items-center gap-2 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm font-medium text-rose-300 hover:bg-destructive/20 hover:text-white transition"
              title="Supprimer définitivement ce projet"
            >
              <Trash2 className="h-4 w-4 text-rose-400" />
              Supprimer
            </button>
          </div>
        </div>
      </div>

      {/* Si le projet est en attente du réglage facecam pour un lien */}
      {currentStatus === "awaiting_cam" && (
        <div className="rounded-2xl border-2 border-purple-500/80 bg-card p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Sliders className="h-5 w-5 text-purple-400" />
                Vidéo importée : Ajustez le cadrage Facecam
              </h2>
              <p className="text-xs text-muted-foreground mt-1">
                L'import est terminé. Définissez la zone du streamer sur l'image extraite avant de lancer l'analyse IA.
              </p>
            </div>
            <button
              onClick={handleSetCam}
              disabled={isSubmittingCam}
              className="flex items-center gap-2 rounded-xl bg-purple-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg hover:bg-purple-500 disabled:opacity-50 transition"
            >
              {isSubmittingCam ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              Valider et continuer
            </button>
          </div>

          <FacecamSelector
            imageUrl={api.mediaUrl(`projects/${project.id}/frame_5.jpg`)}
            initialRect={camRect}
            onChange={setCamRect}
          />
        </div>
      )}

      {/* Point 4 : Cadrage Facecam détecté avec bouton Corriger */}
      {currentStatus !== "awaiting_cam" && (project.settings_json?.cam || project.detected_cam) && (
        <div className="rounded-2xl border border-border/80 bg-card/60 p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-purple-500/10 p-2.5 border border-purple-500/20 text-purple-400">
                <Sliders className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-white">Zone Facecam du Streamer</h3>
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                    project.settings_json?.cam
                      ? "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                      : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                  }`}>
                    {project.settings_json?.cam ? "Manuel (prioritaire)" : "Détecté automatiquement (MediaPipe)"}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5 font-mono">
                  X: {Math.round(camRect.x * 100)}% | Y: {Math.round(camRect.y * 100)}% | L: {Math.round(camRect.w * 100)}% | H: {Math.round(camRect.h * 100)}%
                </p>
              </div>
            </div>

            <button
              onClick={() => setIsEditingCam(!isEditingCam)}
              className="inline-flex items-center gap-1.5 rounded-xl bg-secondary px-3.5 py-2 text-xs font-semibold text-white hover:bg-purple-600 transition"
            >
              <Sliders className="h-3.5 w-3.5" />
              {isEditingCam ? "Fermer" : "Corriger"}
            </button>
          </div>

          {isEditingCam && (
            <div className="pt-3 border-t border-border/40 space-y-4 animate-in fade-in duration-200">
              <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground">
                  Ajustez le rectangle sur l'image ci-dessous. Le réglage manuel primera sur toute détection.
                </p>
                <button
                  onClick={handleSetCam}
                  disabled={isSubmittingCam}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-purple-600 px-4 py-2 text-xs font-semibold text-white shadow hover:bg-purple-500 disabled:opacity-50 transition"
                >
                  {isSubmittingCam ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                  Enregistrer et réappliquer
                </button>
              </div>

              <FacecamSelector
                imageUrl={api.mediaUrl(`projects/${project.id}/frame_5.jpg`)}
                initialRect={camRect}
                onChange={setCamRect}
              />
            </div>
          )}
        </div>
      )}

      {/* Vue d'avancement si en cours ou en échec */}
      {!isFinished && currentStatus !== "awaiting_cam" && (
        <div className="rounded-2xl border border-border/80 bg-card/70 p-6 shadow-sm space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-white flex items-center gap-2">
              {!isFailed ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin text-purple-400" />
                  <span>Traitement IA en direct...</span>
                </>
              ) : (
                <>
                  <AlertCircle className="h-5 w-5 text-rose-400" />
                  <span className="text-rose-400">Le traitement a échoué</span>
                </>
              )}
            </h2>
            <span className="font-mono text-sm font-bold text-purple-400">
              {Math.round(currentProgress * 100)}%
            </span>
          </div>

          {/* Barre de progression */}
          <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${
                isFailed ? "bg-rose-500" : "bg-gradient-to-r from-purple-500 to-indigo-400"
              }`}
              style={{ width: `${Math.round(currentProgress * 100)}%` }}
            />
          </div>

          {currentMessage && (
            <p className="text-xs text-muted-foreground font-mono bg-secondary/50 p-2.5 rounded-lg border border-border/40">
              {currentMessage}
            </p>
          )}

          {project.error && (
            <div className="rounded-lg bg-rose-500/10 border border-rose-500/20 p-4 text-xs text-rose-300">
              <span className="font-semibold block mb-1">Message d'erreur :</span>
              {project.error}
            </div>
          )}

          {/* Étapes du pipeline */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 pt-2">
            {STEPS_ORDER.slice(0, 6).map((step, idx) => {
              const stepIdx = STEPS_ORDER.findIndex((s) => s.id === currentStep);
              const isPast = idx < stepIdx || isFinished;
              const isCurrent = step.id === currentStep && !isFinished;

              return (
                <div
                  key={step.id}
                  className={`flex items-center gap-2.5 p-3 rounded-xl border text-xs transition ${
                    isCurrent
                      ? "border-purple-500/60 bg-purple-500/10 text-white font-medium"
                      : isPast
                      ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-400"
                      : "border-border/40 bg-secondary/20 text-muted-foreground opacity-60"
                  }`}
                >
                  {isPast ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                  ) : isCurrent ? (
                    <Loader2 className="h-4 w-4 shrink-0 animate-spin text-purple-400" />
                  ) : (
                    <div className="h-4 w-4 shrink-0 rounded-full border border-muted-foreground/40" />
                  )}
                  <span>{step.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Grille des clips générés lorsque ready */}
      {isFinished && (
        <div className="space-y-8">
          {(() => {
            const allClips = project.clips || [];
            // Séparation : clips choisis par l'IA vs clips de remplissage (signal audio/scene)
            const mainClips = allClips.filter(
              (c) => c.reason !== "signal audio/scene"
            );
            const fallbackClips = allClips.filter(
              (c) => c.reason === "signal audio/scene"
            );

            // Si aucun clip n'a été choisi par l'IA mais qu'il y a des clips de signaux, on les affiche en principal
            const displayMain = mainClips.length > 0 ? mainClips : allClips;
            const displayFallback = mainClips.length > 0 ? fallbackClips : [];

            const renderClipCard = (clip: Clip) => {
              const duration = Math.round(clip.end - clip.start);
              const scorePct = Math.round((clip.final_score || 0) * 100);
              const isFallback = clip.layout?.face_fallback || false;
              const isRendering = clip.status === "rendering";

              return (
                <div
                  key={clip.id}
                  className={`flex flex-col justify-between rounded-2xl border bg-card/80 overflow-hidden shadow-sm transition group ${
                    isRendering
                      ? "border-purple-500/80 shadow-purple-500/10 shadow-lg ring-1 ring-purple-500/50"
                      : "border-border/70 hover:border-purple-500/40"
                  }`}
                >
                  {/* Vidéo preview */}
                  <div className="relative aspect-[9/16] w-full bg-black flex items-center justify-center overflow-hidden">
                    <video
                      key={`${clip.id}_${clip.status}_${clip.start}_${clip.end}`}
                      src={api.mediaUrl(
                        clip.file_path
                          ? `projects/${clip.project_id}/clips/${clip.index.toString().padStart(2, "0")}.mp4?t=${clip.status === "rendering" ? "tmp" : clip.end}`
                          : ""
                      )}
                      controls={!isRendering}
                      preload="metadata"
                      className={`h-full w-full object-contain transition-opacity ${isRendering ? "opacity-30 blur-[2px]" : "opacity-100"}`}
                    />

                    {/* Overlay plein écran si re-rendu en cours */}
                    {isRendering && (
                      <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-black/75 backdrop-blur-sm p-4 text-center">
                        <div className="relative mb-3">
                          <Loader2 className="h-10 w-10 animate-spin text-purple-400" />
                          <Sparkles className="h-4 w-4 text-amber-300 absolute -top-1 -right-1 animate-pulse" />
                        </div>
                        <span className="text-xs font-bold text-white uppercase tracking-wider">
                          Re-rendu en cours...
                        </span>
                        <span className="text-[11px] text-purple-300/80 mt-1">
                          Montage & encodage GPU
                        </span>
                      </div>
                    )}

                    <div className="absolute top-2 right-2 rounded-full bg-black/70 backdrop-blur-md px-2 py-0.5 text-[11px] font-bold text-amber-400 border border-amber-500/30 flex items-center gap-1 z-10">
                      <Flame className="h-3 w-3" />
                      {scorePct}/100
                    </div>

                    {/* Badge source de sélection ou statut rendering */}
                    <div className="absolute top-2 left-2 flex flex-col gap-1 z-10">
                      {isRendering ? (
                        <span className="rounded-full bg-purple-600 px-2.5 py-0.5 text-[10px] font-bold text-white border border-purple-400/60 shadow-lg flex items-center gap-1.5 animate-pulse">
                          <Loader2 className="h-3 w-3 animate-spin" />
                          Rendu en cours
                        </span>
                      ) : (
                        <>
                          <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold border backdrop-blur-md ${
                            clip.layout?.origin === "IA" || (clip.reason && clip.reason !== "signal audio/scene")
                              ? "bg-purple-600/80 text-white border-purple-400/50"
                              : "bg-slate-700/80 text-slate-200 border-slate-500/50"
                          }`}>
                            {clip.layout?.origin || (clip.reason !== "signal audio/scene" ? "IA" : "Repli son/image")}
                          </span>
                          {isFallback && (
                            <span className="rounded-full bg-blue-500/80 backdrop-blur-md px-2 py-0.5 text-[10px] font-semibold text-white border border-blue-400/40">
                              Cadré au centre
                            </span>
                          )}
                        </>
                      )}
                    </div>

                    <div className="absolute bottom-2 left-2 rounded-md bg-black/70 backdrop-blur-md px-2 py-0.5 text-[10px] font-mono text-white z-10">
                      {duration}s
                    </div>
                  </div>

                  {/* Infos clip */}
                  <div className="p-4 space-y-3 flex-1 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <h3 className="font-bold text-sm text-white line-clamp-1 group-hover:text-purple-300 transition">
                          {clip.title || `Clip #${clip.index}`}
                        </h3>
                      </div>

                      {clip.hook && (
                        <p className="mt-1 text-xs text-purple-300 font-medium line-clamp-1">
                          🎯 Accroche : "{clip.hook}"
                        </p>
                      )}

                      {clip.reason && (
                        <p className="mt-1.5 text-xs text-muted-foreground line-clamp-2">
                          {clip.reason}
                        </p>
                      )}

                      {/* Indicateur explicite si la facecam a été remplacée par centrage */}
                      {isFallback && (
                        <div className="mt-2 rounded-lg bg-blue-500/10 border border-blue-500/20 px-2.5 py-1 text-[11px] text-blue-300 flex items-center gap-1.5">
                          <span>👤 Visage absent : rendu centré automatiquement</span>
                        </div>
                      )}

                      {isRendering && (
                        <div className="mt-2 rounded-lg bg-purple-500/10 border border-purple-500/30 px-2.5 py-1 text-[11px] text-purple-300 flex items-center gap-1.5">
                          <Loader2 className="h-3 w-3 animate-spin text-purple-400" />
                          <span>Actualisation vidéo et sous-titres en cours...</span>
                        </div>
                      )}
                    </div>

                    <div className="pt-3 border-t border-border/40 flex items-center justify-between">
                      <div className="flex gap-2 text-[10px] text-muted-foreground">
                        {clip.scores?.hook && <span>Hook: {clip.scores.hook}</span>}
                        {clip.scores?.emotion && <span>Émotion: {clip.scores.emotion}</span>}
                      </div>

                      <Link
                        href={`/clips/${clip.id}`}
                        className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                          isRendering
                            ? "bg-purple-600/80 text-white hover:bg-purple-600 shadow-sm"
                            : "bg-secondary text-white hover:bg-purple-600"
                        }`}
                      >
                        {isRendering ? (
                          <>
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            Voir statut
                          </>
                        ) : (
                          <>
                            <Sliders className="h-3.5 w-3.5" />
                            Éditer
                          </>
                        )}
                      </Link>
                    </div>
                  </div>
                </div>
              );
            };

            const hasAiClips = (project.settings_json?.ai_clips_count ?? mainClips.length) > 0;
            const fallbackReason = project.settings_json?.ai_fallback_reason;

            return (
              <>
                {/* Bandeau d'alerte si 0 clip vient de l'IA */}
                {!hasAiClips && (
                  <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-xs text-amber-300 flex items-start gap-3">
                    <AlertCircle className="h-5 w-5 shrink-0 text-amber-400 mt-0.5" />
                    <div>
                      <h4 className="font-bold text-sm text-amber-200">Aucun clip n'a pu être sélectionné par l'IA</h4>
                      <p className="mt-1 text-amber-300/90">
                        {fallbackReason || "L'appel au LLM n'a pas retourné de résultat valide ou a échoué. Le système a automatiquement basculé sur la détection par signaux audio et changements de plan."}
                      </p>
                    </div>
                  </div>
                )}

                {/* Section principale : Clips sélectionnés */}
                <div className="space-y-4">
                  <div className="flex items-center justify-between border-b border-border/60 pb-3">
                    <div>
                      <h2 className="text-xl font-bold text-white flex items-center gap-2">
                        <Flame className="h-5 w-5 text-amber-400" />
                        Clips Détectés & Générés ({displayMain.length})
                      </h2>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Moments forts identifiés par l'analyse. Cliquez sur un clip pour l'éditer, ajuster le début/fin ou les sous-titres.
                      </p>
                    </div>
                  </div>

                  {displayMain.length > 0 ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                      {displayMain.map(renderClipCard)}
                    </div>
                  ) : (
                    <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
                      Aucun clip n'a été produit pour cette vidéo.
                    </div>
                  )}
                </div>

                {/* Section repliée : Autres moments possibles (Clips de remplissage / signaux) */}
                {displayFallback.length > 0 && (
                  <div className="rounded-2xl border border-border/60 bg-card/40 overflow-hidden">
                    <button
                      type="button"
                      onClick={() => setShowFallbackClips(!showFallbackClips)}
                      className="w-full p-4 flex items-center justify-between text-left hover:bg-secondary/30 transition"
                    >
                      <div>
                        <h3 className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
                          <span>Autres moments possibles ({displayFallback.length})</span>
                          <span className="text-[11px] font-normal text-muted-foreground/70 bg-secondary px-2 py-0.5 rounded">
                            Détection par pics de volume & plans
                          </span>
                        </h3>
                        <p className="text-xs text-muted-foreground/60 mt-0.5">
                          Passages secondaires avec score plus modéré
                        </p>
                      </div>
                      {showFallbackClips ? (
                        <ChevronUp className="h-5 w-5 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="h-5 w-5 text-muted-foreground" />
                      )}
                    </button>

                    {showFallbackClips && (
                      <div className="p-4 pt-0 border-t border-border/40">
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 mt-4">
                          {displayFallback.map(renderClipCard)}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
}
