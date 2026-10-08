"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Download,
  RotateCcw,
  Sliders,
  Type,
  Clock,
  Check,
  Loader2,
  AlertCircle,
  Save,
  Sparkles,
  Send,
  Trash2,
  Mic,
  RefreshCw,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Clip, WordItem } from "@/lib/types";
import { formatTime } from "@/lib/utils";
import { PublishModal } from "@/components/PublishModal";
import { ClipTrimmer } from "@/components/ClipTrimmer";

export default function ClipEditorPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  // Polling automatique si le clip est en cours de rendu
  const {
    data: clip,
    isLoading: isClipLoading,
    error: clipError,
    refetch: refetchClip,
  } = useQuery<Clip>({
    queryKey: ["clip", id],
    queryFn: () => api.getClip(id),
    refetchInterval: (query) => {
      const c = query.state.data;
      if (c && c.status === "rendering") return 1500;
      return false;
    },
  });

  // Charger les mots des sous-titres
  const {
    data: words = [],
    isLoading: isWordsLoading,
    refetch: refetchWords,
  } = useQuery<WordItem[]>({
    queryKey: ["clipWords", id],
    queryFn: () => api.getClipWords(id),
    enabled: !!clip,
  });

  // État local des champs éditables
  const [title, setTitle] = useState("");
  const [start, setStart] = useState<number>(0);
  const [end, setEnd] = useState<number>(0);
  const [editedWords, setEditedWords] = useState<WordItem[]>([]);
  const [userEdits, setUserEdits] = useState<Record<string, string>>({});
  const [layout, setLayout] = useState("center");
  const [format, setFormat] = useState("9:16");
  const [captions, setCaptions] = useState("punchy");
  const [isSaving, setIsSaving] = useState(false);
  const [isRendering, setIsRendering] = useState(false);
  const [isSyncingWords, setIsSyncingWords] = useState(false);
  const [isRegeneratingSubtitles, setIsRegeneratingSubtitles] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [isPublishOpen, setIsPublishOpen] = useState(false);
  const [videoTimestamp, setVideoTimestamp] = useState<number>(Date.now());
  const prevStatusRef = React.useRef<string | undefined>(undefined);

  // Référence et état du lecteur vidéo pour rognage interactif
  const videoRef = React.useRef<HTMLVideoElement | null>(null);
  const [videoCurrentTime, setVideoCurrentTime] = useState<number>(0);
  const [videoDuration, setVideoDuration] = useState<number>(0);

  const handleSeek = (timeSec: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = timeSec;
      setVideoCurrentTime(timeSec);
    }
  };

  const isInitializedRef = React.useRef(false);

  useEffect(() => {
    if (clip && !isInitializedRef.current) {
      isInitializedRef.current = true;
      setTitle(clip.title || "");
      setStart(clip.start);
      setEnd(clip.end);
      setLayout(clip.layout?.name || "center");
      setFormat(clip.layout?.fmt || "9:16");
      setCaptions(clip.captions?.preset || "punchy");
    }

    if (clip) {
      // Détecter la fin d'un rendu
      if (prevStatusRef.current === "rendering" && clip.status === "ready") {
        setSuccessMsg("Clip re-rendu avec succès !");
        setIsRendering(false);
        setVideoTimestamp(Date.now());
        setStart(clip.start);
        setEnd(clip.end);
        refetchWords();
        queryClient.invalidateQueries({ queryKey: ["project", clip.project_id] });
      }
      prevStatusRef.current = clip.status;
    }
  }, [clip, queryClient, refetchWords]);

  useEffect(() => {
    if (words.length > 0 && editedWords.length === 0) {
      setEditedWords(words);
    }
  }, [words, editedWords.length]);

  // Synchronisation propre et déterministe des mots selon la plage temporelle rognée
  useEffect(() => {
    if (!clip || start === undefined || end === undefined || start >= end) return;
    if (start === clip.start && end === clip.end) return;

    const timer = setTimeout(async () => {
      try {
        setIsSyncingWords(true);
        const fetchedWords = await api.getClipWords(clip.id, start, end);
        if (fetchedWords) {
          // Appliquer les corrections manuelles par clé exacte de timecode
          setEditedWords(
            fetchedWords.map((fw) => {
              const key = fw.start.toFixed(2);
              return userEdits[key] !== undefined ? { ...fw, text: userEdits[key] } : fw;
            })
          );
        }
      } catch (err) {
        console.error("Erreur sync mots pour nouvelle portion:", err);
      } finally {
        setIsSyncingWords(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [clip, start, end, userEdits]);

  const handleWordChange = (idx: number, newText: string) => {
    const word = editedWords[idx];
    if (word) {
      const key = word.start.toFixed(2);
      setUserEdits((prev) => ({ ...prev, [key]: newText }));
    }
    const updated = [...editedWords];
    updated[idx] = { ...updated[idx], text: newText };
    setEditedWords(updated);
  };

  const handleDeleteWord = (idx: number) => {
    const word = editedWords[idx];
    if (word) {
      const key = word.start.toFixed(2);
      setUserEdits((prev) => {
        const copy = { ...prev };
        delete copy[key];
        return copy;
      });
    }
    setEditedWords((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSeekWord = (wordStart: number) => {
    if (!clip) return;
    const relSec = Math.max(0, wordStart - clip.start);
    handleSeek(relSec);
  };

  const handleRegenerateSubtitles = async (mode: "reset" | "whisper" = "reset") => {
    if (!clip) return;
    try {
      setIsRegeneratingSubtitles(true);
      setUserEdits({});
      const newWords = await api.regenerateClipWords(clip.id, mode);
      setEditedWords(newWords);
      setSuccessMsg(
        mode === "whisper"
          ? "Sous-titres ré-analysés et régénérés par IA Whisper !"
          : "Sous-titres réinitialisés proprement depuis la transcription originale !"
      );
      setTimeout(() => setSuccessMsg(null), 3500);
      refetchWords();
    } catch (err: any) {
      alert("Échec de la régénération des sous-titres : " + (err.message || String(err)));
    } finally {
      setIsRegeneratingSubtitles(false);
    }
  };

  const handleSaveMetadata = async () => {
    setIsSaving(true);
    setSuccessMsg(null);
    try {
      await api.updateClip(id, {
        title,
        start,
        end,
        words: editedWords,
      });
      setSuccessMsg("Modifications enregistrées !");
      setTimeout(() => setSuccessMsg(null), 3000);
      refetchClip();
    } catch (err: any) {
      alert(err.message || "Erreur lors de l'enregistrement");
    } finally {
      setIsSaving(false);
    }
  };

  const handleRerender = async () => {
    if (!clip) return;
    setIsRendering(true);
    setSuccessMsg(null);
    try {
      // 1. Sauvegarder les modifications actuelles (mots, début, fin)
      await api.updateClip(id, {
        title,
        start,
        end,
        words: editedWords,
      });

      // 2. Lancer le re-rendu ciblé de ce clip (n'affecte pas le statut du projet)
      await api.rerenderClip(clip.id, {
        layout,
        format,
        captions: captions === "none" ? undefined : captions,
      });

      await refetchClip();
      queryClient.invalidateQueries({ queryKey: ["project", clip.project_id] });
    } catch (err: any) {
      alert(err.message || "Erreur lors du rendu");
      setIsRendering(false);
    }
  };

  if (isClipLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
        <Loader2 className="h-8 w-8 animate-spin text-purple-400" />
        <p className="mt-3 text-sm">Chargement du clip...</p>
      </div>
    );
  }

  if (clipError || !clip) {
    return (
      <div className="rounded-xl border border-destructive/50 bg-destructive/10 p-6 text-center text-rose-300">
        <AlertCircle className="mx-auto h-8 w-8 text-rose-400 mb-2" />
        <p className="font-semibold">Clip introuvable</p>
        <Link href="/" className="mt-4 inline-block text-xs text-purple-400 underline">
          Retour à l'accueil
        </Link>
      </div>
    );
  }

  const isClipRendering = clip.status === "rendering" || isRendering;

  const videoUrl = api.mediaUrl(
    clip.file_path
      ? `projects/${clip.project_id}/clips/${clip.index.toString().padStart(2, "0")}.mp4?t=${videoTimestamp}`
      : ""
  );

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Navigation */}
      <Link
        href={`/projects/${clip.project_id}`}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-white transition"
      >
        <ArrowLeft className="h-4 w-4" />
        Retour au projet
      </Link>

      {/* Marqueur visuel lorsque le clip est en cours de re-rendu */}
      {isClipRendering && (
        <div className="rounded-2xl border border-purple-500/80 bg-purple-500/10 p-4 text-purple-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 shadow-lg ring-1 ring-purple-500/40 animate-pulse">
          <div className="flex items-center gap-3">
            <Loader2 className="h-6 w-6 animate-spin text-purple-400 shrink-0" />
            <div>
              <h3 className="font-bold text-sm text-white">Re-rendu de ce clip en cours...</h3>
              <p className="text-xs text-purple-300/90 mt-0.5">
                Le découpage vidéo, les sous-titres pour la nouvelle portion et le montage GPU s'effectuent en arrière-plan.
              </p>
            </div>
          </div>
          <span className="text-xs font-mono font-bold bg-purple-600/50 text-purple-200 px-3 py-1 rounded-full border border-purple-400/40 shrink-0 self-start sm:self-auto">
            ⚡ GPU Encodage
          </span>
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <span>Édition du Clip #{clip.index}</span>
            <span className="text-xs font-mono font-normal text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
              #{clip.id}
            </span>
          </h1>
          <p className="text-xs text-muted-foreground mt-1">
            Ajustez l'intervalle de début/fin, les sous-titres s'adaptent automatiquement, puis re-rendez en un clic.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <a
            href={videoUrl}
            download={`clip_${clip.id}.mp4`}
            className="inline-flex items-center gap-1.5 rounded-xl bg-secondary px-4 py-2.5 text-xs font-semibold text-white hover:bg-secondary/80 transition"
          >
            <Download className="h-4 w-4" />
            Télécharger MP4
          </a>
          <button
            onClick={handleRerender}
            disabled={isClipRendering}
            className="inline-flex items-center gap-1.5 rounded-xl bg-purple-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-purple-600/30 hover:bg-purple-500 disabled:opacity-50 transition"
          >
            {isClipRendering ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Rendu en cours...</span>
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                <span>Re-rendre le clip</span>
              </>
            )}
          </button>
          <button
            onClick={() => setIsPublishOpen(true)}
            disabled={isClipRendering || clip.status !== "ready"}
            className="inline-flex items-center gap-1.5 rounded-xl bg-red-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-red-600/30 hover:bg-red-500 disabled:opacity-50 transition"
          >
            <Send className="h-4 w-4" />
            <span>Publier</span>
          </button>
        </div>
      </div>

      {successMsg && (
        <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-3 text-xs font-semibold text-emerald-300 flex items-center gap-2">
          <Check className="h-4 w-4" />
          {successMsg}
        </div>
      )}

      {/* Grid Lecteur + Éditeur */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Lecteur vidéo (col-span-5) */}
        <div className="lg:col-span-5 flex flex-col items-center">
          <div className="relative aspect-[9/16] w-full max-w-[320px] rounded-2xl overflow-hidden border border-border/80 bg-black shadow-xl">
            <video
              ref={videoRef}
              key={`${videoUrl}_${clip.status}`}
              src={videoUrl}
              controls={!isClipRendering}
              autoPlay={false}
              onTimeUpdate={() => {
                if (videoRef.current) setVideoCurrentTime(videoRef.current.currentTime);
              }}
              onLoadedMetadata={() => {
                if (videoRef.current) {
                  setVideoDuration(videoRef.current.duration);
                  setVideoCurrentTime(videoRef.current.currentTime);
                }
              }}
              className={`h-full w-full object-contain transition-opacity ${
                isClipRendering ? "opacity-30 blur-[2px]" : "opacity-100"
              }`}
            />

            {/* Overlay plein écran si re-rendu en cours */}
            {isClipRendering && (
              <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-black/75 backdrop-blur-sm p-4 text-center">
                <Loader2 className="h-10 w-10 animate-spin text-purple-400 mb-3" />
                <span className="text-sm font-bold text-white uppercase tracking-wider">
                  Re-rendu en cours...
                </span>
                <span className="text-xs text-purple-300/80 mt-1 max-w-[200px]">
                  Encodage de la vidéo et recalage des sous-titres
                </span>
              </div>
            )}
          </div>
          <span className="text-[11px] text-muted-foreground mt-2">
            Position lecture : {formatTime(videoCurrentTime)} / {formatTime(Math.max(1, clip.end - clip.start))}
          </span>
        </div>

        {/* Panneau de réglages (col-span-7) */}
        <div className="lg:col-span-7 space-y-6">
          {/* Titre du clip */}
          <div className="rounded-2xl border border-border/80 bg-card/60 p-5 shadow-sm space-y-3">
            <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground block">
              Titre du clip
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Donnez un titre percutant à votre clip..."
              className="w-full rounded-xl border border-border bg-background px-3.5 py-2.5 text-sm text-white focus:border-purple-500 focus:outline-none"
            />
          </div>

          {/* Outil de Rognage Convivial */}
          <ClipTrimmer
            baseStart={clip.start}
            baseEnd={clip.end}
            currentStart={start}
            currentEnd={end}
            onChangeRange={(newStart, newEnd) => {
              setStart(newStart);
              setEnd(newEnd);
            }}
            videoRef={videoRef}
            videoCurrentTime={videoCurrentTime}
            videoDuration={videoDuration}
            onSeek={handleSeek}
          />

          {/* Options de Rendu & Style */}
          <div className="rounded-2xl border border-border/80 bg-card/60 p-5 shadow-sm space-y-4">
            <h2 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
              <Sparkles className="h-3.5 w-3.5 text-purple-400" />
              Style de rendu
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Mise en page</label>
                <select
                  value={layout}
                  onChange={(e) => setLayout(e.target.value)}
                  className="w-full rounded-xl border border-border bg-background px-2.5 py-2 text-xs text-white focus:outline-none"
                >
                  <option value="center">Centrée</option>
                  <option value="blur">Fond flou</option>
                  <option value="facecam_top">Facecam haut</option>
                  <option value="facecam_bottom">Facecam bas</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-muted-foreground block mb-1">Format</label>
                <select
                  value={format}
                  onChange={(e) => setFormat(e.target.value)}
                  className="w-full rounded-xl border border-border bg-background px-2.5 py-2 text-xs text-white focus:outline-none"
                >
                  <option value="9:16">9:16 (Vertical)</option>
                  <option value="1:1">1:1 (Carré)</option>
                  <option value="4:5">4:5 (Portrait)</option>
                  <option value="16:9">16:9 (Paysage)</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-muted-foreground block mb-1">Sous-titres</label>
                <select
                  value={captions}
                  onChange={(e) => setCaptions(e.target.value)}
                  className="w-full rounded-xl border border-border bg-background px-2.5 py-2 text-xs text-white focus:outline-none"
                >
                  <option value="punchy">Punchy</option>
                  <option value="clean">Clean</option>
                  <option value="karaoke">Karaoke</option>
                  <option value="none">Aucun</option>
                </select>
              </div>
            </div>
          </div>

          {/* Éditeur de sous-titres mot à mot */}
          <div className="rounded-2xl border border-border/80 bg-card/60 p-5 shadow-sm space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div className="flex items-center gap-2">
                <h2 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                  <Type className="h-3.5 w-3.5 text-purple-400" />
                  Sous-titres mot à mot ({editedWords.length} mots)
                </h2>
                {(isSyncingWords || isRegeneratingSubtitles) && (
                  <span className="flex items-center gap-1 text-[10px] text-purple-300 font-medium animate-pulse">
                    <Loader2 className="h-3 w-3 animate-spin text-purple-400" />
                    {isRegeneratingSubtitles ? "Régénération IA..." : "Mise à jour..."}
                  </span>
                )}
              </div>

              {/* Actions : Réinitialiser / Re-transcrire IA / Sauvegarder */}
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={() => handleRegenerateSubtitles("reset")}
                  disabled={isSaving || isSyncingWords || isRegeneratingSubtitles}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-zinc-900 px-2.5 py-1 text-xs font-medium text-zinc-300 hover:text-white hover:bg-zinc-800 disabled:opacity-50 transition"
                  title="Efface les doublons et recharge la transcription originale du projet"
                >
                  <RotateCcw className="h-3 w-3 text-purple-400" />
                  <span>Réinitialiser</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleRegenerateSubtitles("whisper")}
                  disabled={isSaving || isSyncingWords || isRegeneratingSubtitles}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-purple-500/40 bg-purple-500/10 px-2.5 py-1 text-xs font-medium text-purple-200 hover:bg-purple-500/20 disabled:opacity-50 transition"
                  title="Relance l'IA Whisper sur l'extrait audio précis de ce clip"
                >
                  <Mic className="h-3 w-3 text-purple-400" />
                  <span>Re-transcrire IA</span>
                </button>

                <button
                  type="button"
                  onClick={handleSaveMetadata}
                  disabled={isSaving || isSyncingWords || isRegeneratingSubtitles}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-secondary px-3 py-1 text-xs font-semibold text-white hover:bg-secondary/80 disabled:opacity-50 transition"
                >
                  {isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                  <span>Sauvegarder</span>
                </button>
              </div>
            </div>

            {isWordsLoading || isRegeneratingSubtitles ? (
              <div className="py-8 text-center text-xs text-muted-foreground">
                <Loader2 className="mx-auto h-5 w-5 animate-spin text-purple-400 mb-1" />
                {isRegeneratingSubtitles
                  ? "Analyse audio par Whisper en cours..."
                  : "Chargement des mots transcrits..."}
              </div>
            ) : editedWords.length === 0 ? (
              <div className="py-6 text-center text-xs text-muted-foreground border border-dashed border-border/60 rounded-xl space-y-2">
                <p>Aucun mot de transcription trouvé pour ce clip.</p>
                <button
                  type="button"
                  onClick={() => handleRegenerateSubtitles("reset")}
                  className="inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-purple-600/20 text-purple-300 text-xs hover:bg-purple-600/30 transition"
                >
                  <RefreshCw className="w-3 h-3" />
                  Recharger les sous-titres
                </button>
              </div>
            ) : (
              <div className="max-h-64 overflow-y-auto space-y-1.5 pr-1 text-xs">
                {editedWords.map((item, idx) => (
                  <div
                    key={`${item.start}_${idx}`}
                    className="flex items-center gap-2 rounded-lg bg-background/60 p-1.5 border border-border/40 hover:border-purple-500/30 transition group"
                  >
                    <button
                      type="button"
                      onClick={() => handleSeekWord(item.start)}
                      className="font-mono text-[10px] text-muted-foreground hover:text-purple-300 hover:bg-purple-500/10 px-1 py-0.5 rounded transition w-14 shrink-0 text-left"
                      title="Écouter ce mot dans le lecteur vidéo"
                    >
                      ▶ {item.start.toFixed(1)}s
                    </button>
                    <input
                      type="text"
                      value={item.text}
                      onChange={(e) => handleWordChange(idx, e.target.value)}
                      className="flex-1 bg-transparent px-2 py-0.5 text-white font-medium focus:bg-secondary/40 focus:outline-none rounded"
                    />
                    <button
                      type="button"
                      onClick={() => handleDeleteWord(idx)}
                      className="p-1 rounded text-muted-foreground hover:text-rose-400 hover:bg-rose-500/10 opacity-40 group-hover:opacity-100 transition"
                      title="Supprimer ce mot"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Modal de Publication */}
      <PublishModal
        clip={clip}
        isOpen={isPublishOpen}
        onClose={() => setIsPublishOpen(false)}
      />
    </div>
  );
}
