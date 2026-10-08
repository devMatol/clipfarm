"use client";

import React, { useState } from "react";
import {
  Scissors,
  Play,
  Pause,
  RotateCcw,
  Clock,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  Info,
} from "lucide-react";
import { formatTime } from "@/lib/utils";

interface ClipTrimmerProps {
  baseStart: number; // Début originel du clip en base
  baseEnd: number; // Fin originelle du clip en base
  currentStart: number; // Début actuel après rognage
  currentEnd: number; // Fin actuelle après rognage
  onChangeRange: (newStart: number, newEnd: number) => void;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  videoCurrentTime: number;
  videoDuration: number;
  onSeek: (time: number) => void;
}

export function ClipTrimmer({
  baseStart,
  baseEnd,
  currentStart,
  currentEnd,
  onChangeRange,
  videoRef,
  videoCurrentTime,
  videoDuration,
  onSeek,
}: ClipTrimmerProps) {
  const [isPlayingPreview, setIsPlayingPreview] = useState(false);

  // Durée de référence de la vidéo actuelle
  const clipRefDuration = Math.max(1, baseEnd - baseStart);
  const actualDuration = Math.max(0.5, currentEnd - currentStart);

  // Rognage relatif par rapport à la vidéo chargée
  const trimStartSec = Math.max(0, currentStart - baseStart);
  const trimEndSec = Math.max(0, baseEnd - currentEnd);
  const isExtendedStart = currentStart < baseStart;
  const isExtendedEnd = currentEnd > baseEnd;

  // Calcul des pourcentages pour la barre visuelle
  const startPercent = Math.min(95, Math.max(0, (trimStartSec / clipRefDuration) * 100));
  const endPercent = Math.min(100, Math.max(startPercent + 5, ((clipRefDuration - trimEndSec) / clipRefDuration) * 100));
  const playheadPercent = Math.min(100, Math.max(0, (videoCurrentTime / clipRefDuration) * 100));

  // Rognage au curseur actuel de la vidéo
  const handleCutStartAtPlayhead = () => {
    const newStart = Number((baseStart + videoCurrentTime).toFixed(1));
    if (newStart < currentEnd - 1) {
      onChangeRange(newStart, currentEnd);
    } else {
      alert("Le début doit être au moins 1 seconde avant la fin du clip.");
    }
  };

  const handleCutEndAtPlayhead = () => {
    const newEnd = Number((baseStart + videoCurrentTime).toFixed(1));
    if (newEnd > currentStart + 1) {
      onChangeRange(currentStart, newEnd);
    } else {
      alert("La fin doit être au moins 1 seconde après le début du clip.");
    }
  };

  // Ajustement rapide du début (+/- secondes)
  const adjustStart = (deltaSec: number) => {
    const nextStart = Number(Math.max(0, currentStart + deltaSec).toFixed(1));
    if (nextStart < currentEnd - 1) {
      onChangeRange(nextStart, currentEnd);
      // Recaler la vidéo sur le nouveau début si pertinent
      const relSec = Math.max(0, nextStart - baseStart);
      if (relSec < clipRefDuration) onSeek(relSec);
    }
  };

  // Ajustement rapide de la fin (+/- secondes)
  const adjustEnd = (deltaSec: number) => {
    const nextEnd = Number((currentEnd + deltaSec).toFixed(1));
    if (nextEnd > currentStart + 1) {
      onChangeRange(currentStart, nextEnd);
    }
  };

  // Réinitialiser le rognage
  const handleReset = () => {
    onChangeRange(baseStart, baseEnd);
    onSeek(0);
  };

  // Aperçu de la portion rognée
  const handleTogglePreview = () => {
    if (!videoRef.current) return;
    const vid = videoRef.current;

    if (isPlayingPreview) {
      vid.pause();
      setIsPlayingPreview(false);
      return;
    }

    const relStart = Math.max(0, currentStart - baseStart);
    const relEnd = Math.min(clipRefDuration, currentEnd - baseStart);

    vid.currentTime = relStart;
    vid.play();
    setIsPlayingPreview(true);

    const checkInterval = setInterval(() => {
      if (!vid || vid.paused || vid.currentTime >= relEnd) {
        if (vid) vid.pause();
        setIsPlayingPreview(false);
        clearInterval(checkInterval);
      }
    }, 100);
  };

  const isTrimmed = currentStart !== baseStart || currentEnd !== baseEnd;
  const totalTrimDelta = (clipRefDuration - actualDuration).toFixed(1);

  return (
    <div className="space-y-5 rounded-2xl border border-border/80 bg-card/60 p-5 shadow-sm">
      {/* En-tête */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center border border-purple-500/20">
            <Scissors className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <span>Rognage de la vidéo</span>
              {isTrimmed && (
                <span className="text-[10px] bg-purple-500/20 text-purple-300 font-mono px-2 py-0.5 rounded-full border border-purple-500/30">
                  Modifié
                </span>
              )}
            </h2>
            <p className="text-xs text-muted-foreground">
              Coupez les secondes superflues en tête ou en fin de clip en temps réel.
            </p>
          </div>
        </div>

        {/* Bouton Réinitialiser & Aperçu */}
        <div className="flex items-center gap-2 self-start sm:self-auto">
          {isTrimmed && (
            <button
              type="button"
              onClick={handleReset}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border/80 bg-zinc-900 hover:bg-zinc-800 text-xs text-muted-foreground hover:text-white transition"
              title="Rétablir les bornes d'origine du clip"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Réinitialiser</span>
            </button>
          )}

          <button
            type="button"
            onClick={handleTogglePreview}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              isPlayingPreview
                ? "bg-amber-600 text-white hover:bg-amber-500"
                : "bg-purple-600/30 text-purple-200 border border-purple-500/40 hover:bg-purple-600/40"
            }`}
          >
            {isPlayingPreview ? (
              <>
                <Pause className="w-3.5 h-3.5" />
                <span>Pause</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Tester l&apos;extrait</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Résumé de la durée */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-zinc-950/60 p-3.5 rounded-xl border border-border/60 text-xs">
        <div>
          <span className="text-muted-foreground block text-[11px]">Durée initiale</span>
          <span className="font-mono font-bold text-zinc-300">{clipRefDuration.toFixed(1)}s</span>
        </div>
        <div>
          <span className="text-muted-foreground block text-[11px]">Durée rognée</span>
          <span className="font-mono font-bold text-purple-400 text-sm">
            {actualDuration.toFixed(1)}s
          </span>
        </div>
        <div>
          <span className="text-muted-foreground block text-[11px]">Rognage total</span>
          <span
            className={`font-mono font-bold ${
              Number(totalTrimDelta) > 0
                ? "text-rose-400"
                : Number(totalTrimDelta) < 0
                ? "text-emerald-400"
                : "text-zinc-500"
            }`}
          >
            {Number(totalTrimDelta) > 0
              ? `-${totalTrimDelta}s`
              : Number(totalTrimDelta) < 0
              ? `+${Math.abs(Number(totalTrimDelta))}s`
              : "0.0s"}
          </span>
        </div>
        <div>
          <span className="text-muted-foreground block text-[11px]">Curseur vidéo</span>
          <span className="font-mono text-zinc-400">
            {formatTime(videoCurrentTime)} / {formatTime(clipRefDuration)}
          </span>
        </div>
      </div>

      {/* Timeline Visuelle de Rognage */}
      <div className="space-y-2">
        <div className="flex justify-between items-center text-[11px] text-muted-foreground font-mono">
          <span>00:00.0</span>
          <span className="text-purple-300 font-semibold">Zone conservée</span>
          <span>{formatTime(clipRefDuration)}</span>
        </div>

        <div className="relative h-12 w-full rounded-xl bg-zinc-950 border border-zinc-800 overflow-hidden select-none">
          {/* Zone coupée au début */}
          {startPercent > 0 && (
            <div
              style={{ width: `${startPercent}%` }}
              className="absolute left-0 top-0 bottom-0 bg-rose-950/40 border-r border-rose-500/50 flex items-center justify-center text-[10px] font-mono text-rose-300/80 overflow-hidden"
            >
              ✂️ -{trimStartSec.toFixed(1)}s
            </div>
          )}

          {/* Zone active conservée */}
          <div
            style={{
              left: `${startPercent}%`,
              width: `${Math.max(0, endPercent - startPercent)}%`,
            }}
            className="absolute top-0 bottom-0 bg-gradient-to-r from-purple-600/30 via-purple-500/35 to-purple-600/30 border-x-2 border-purple-400 shadow-inner flex items-center justify-center"
          >
            <span className="text-xs font-mono font-bold text-white bg-purple-900/60 px-2 py-0.5 rounded shadow">
              {actualDuration.toFixed(1)}s
            </span>
          </div>

          {/* Zone coupée à la fin */}
          {endPercent < 100 && (
            <div
              style={{
                left: `${endPercent}%`,
                width: `${100 - endPercent}%`,
              }}
              className="absolute right-0 top-0 bottom-0 bg-rose-950/40 border-l border-rose-500/50 flex items-center justify-center text-[10px] font-mono text-rose-300/80 overflow-hidden"
            >
              ✂️ -{trimEndSec.toFixed(1)}s
            </div>
          )}

          {/* Curseur de lecture vidéo actuel */}
          <div
            style={{ left: `${playheadPercent}%` }}
            className="absolute top-0 bottom-0 w-0.5 bg-yellow-400 z-10 pointer-events-none shadow-[0_0_8px_rgba(250,204,21,0.8)]"
          >
            <div className="w-2.5 h-2.5 rounded-full bg-yellow-400 -ml-1 -top-1 absolute" />
          </div>

          {/* Zone cliquable pour chercher dans la vidéo */}
          <div
            className="absolute inset-0 cursor-pointer opacity-0"
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const clickX = e.clientX - rect.left;
              const ratio = Math.max(0, Math.min(1, clickX / rect.width));
              const targetTime = ratio * clipRefDuration;
              onSeek(targetTime);
            }}
          />
        </div>

        <p className="text-[11px] text-muted-foreground text-center">
          Cliquez sur la barre pour caler la vidéo sur le moment exact à rogner.
        </p>
      </div>

      {/* Rognage au Curseur du Lecteur (1 clic) */}
      <div className="p-3.5 rounded-xl border border-purple-500/30 bg-purple-500/10 space-y-2.5">
        <span className="text-xs font-bold text-purple-200 block">
          ✂️ Rognage instantané avec le lecteur vidéo :
        </span>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          <button
            type="button"
            onClick={handleCutStartAtPlayhead}
            className="flex items-center justify-between px-3 py-2 rounded-lg bg-zinc-900/90 hover:bg-zinc-800 border border-purple-400/30 text-xs font-semibold text-white transition group"
          >
            <span className="flex items-center gap-1.5">
              <Scissors className="w-3.5 h-3.5 text-purple-400 group-hover:rotate-12 transition-transform" />
              <span>Couper le début ici</span>
            </span>
            <span className="font-mono text-[11px] text-purple-300 bg-purple-500/20 px-1.5 py-0.5 rounded">
              à {formatTime(videoCurrentTime)}
            </span>
          </button>

          <button
            type="button"
            onClick={handleCutEndAtPlayhead}
            className="flex items-center justify-between px-3 py-2 rounded-lg bg-zinc-900/90 hover:bg-zinc-800 border border-purple-400/30 text-xs font-semibold text-white transition group"
          >
            <span className="flex items-center gap-1.5">
              <Scissors className="w-3.5 h-3.5 text-purple-400 group-hover:rotate-12 transition-transform" />
              <span>Couper la fin ici</span>
            </span>
            <span className="font-mono text-[11px] text-purple-300 bg-purple-500/20 px-1.5 py-0.5 rounded">
              à {formatTime(videoCurrentTime)}
            </span>
          </button>
        </div>
      </div>

      {/* Boutons d'ajustement fin par secondes */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
        {/* Début du clip */}
        <div data-testid="trim-start-section" className="p-3 rounded-xl border border-border/80 bg-zinc-950/40 space-y-2.5">
          <div className="flex items-center justify-between">
            <label className="text-xs font-bold text-zinc-300 flex items-center gap-1.5">
              <ChevronRight className="w-3.5 h-3.5 text-purple-400" />
              <span>Début du clip</span>
            </label>
            <span className="text-[11px] font-mono text-muted-foreground">
              {trimStartSec > 0
                ? `+${trimStartSec.toFixed(1)}s rognées`
                : isExtendedStart
                ? `-${(baseStart - currentStart).toFixed(1)}s ajoutées`
                : "Point d'origine"}
            </span>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-muted-foreground w-20 shrink-0">Rogner (couper) :</span>
              <button
                type="button"
                onClick={() => adjustStart(0.5)}
                className="flex-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 py-1 text-xs font-mono font-medium text-white transition"
              >
                +0.5s
              </button>
              <button
                type="button"
                onClick={() => adjustStart(1.0)}
                className="flex-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 py-1 text-xs font-mono font-medium text-white transition"
              >
                +1.0s
              </button>
              <button
                type="button"
                onClick={() => adjustStart(2.0)}
                className="flex-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 py-1 text-xs font-mono font-medium text-white transition"
              >
                +2.0s
              </button>
            </div>

            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-muted-foreground w-20 shrink-0">Démarrer plus tôt :</span>
              <button
                type="button"
                onClick={() => adjustStart(-0.5)}
                className="flex-1 rounded-lg bg-secondary/80 hover:bg-secondary py-1 text-xs font-mono font-medium text-zinc-300 transition"
              >
                -0.5s
              </button>
              <button
                type="button"
                onClick={() => adjustStart(-1.0)}
                className="flex-1 rounded-lg bg-secondary/80 hover:bg-secondary py-1 text-xs font-mono font-medium text-zinc-300 transition"
              >
                -1.0s
              </button>
              <button
                type="button"
                onClick={() => adjustStart(-2.0)}
                className="flex-1 rounded-lg bg-secondary/80 hover:bg-secondary py-1 text-xs font-mono font-medium text-zinc-300 transition"
              >
                -2.0s
              </button>
            </div>
          </div>
        </div>

        {/* Fin du clip */}
        <div data-testid="trim-end-section" className="p-3 rounded-xl border border-border/80 bg-zinc-950/40 space-y-2.5">
          <div className="flex items-center justify-between">
            <label className="text-xs font-bold text-zinc-300 flex items-center gap-1.5">
              <ChevronLeft className="w-3.5 h-3.5 text-purple-400" />
              <span>Fin du clip</span>
            </label>
            <span className="text-[11px] font-mono text-muted-foreground">
              {trimEndSec > 0
                ? `-${trimEndSec.toFixed(1)}s rognées`
                : isExtendedEnd
                ? `+${(currentEnd - baseEnd).toFixed(1)}s ajoutées`
                : "Point d'origine"}
            </span>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-muted-foreground w-20 shrink-0">Rogner (couper) :</span>
              <button
                type="button"
                onClick={() => adjustEnd(-0.5)}
                className="flex-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 py-1 text-xs font-mono font-medium text-white transition"
              >
                -0.5s
              </button>
              <button
                type="button"
                onClick={() => adjustEnd(-1.0)}
                className="flex-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 py-1 text-xs font-mono font-medium text-white transition"
              >
                -1.0s
              </button>
              <button
                type="button"
                onClick={() => adjustEnd(-2.0)}
                className="flex-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 py-1 text-xs font-mono font-medium text-white transition"
              >
                -2.0s
              </button>
            </div>

            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-muted-foreground w-20 shrink-0">Prolonger :</span>
              <button
                type="button"
                onClick={() => adjustEnd(0.5)}
                className="flex-1 rounded-lg bg-secondary/80 hover:bg-secondary py-1 text-xs font-mono font-medium text-zinc-300 transition"
              >
                +0.5s
              </button>
              <button
                type="button"
                onClick={() => adjustEnd(1.0)}
                className="flex-1 rounded-lg bg-secondary/80 hover:bg-secondary py-1 text-xs font-mono font-medium text-zinc-300 transition"
              >
                +1.0s
              </button>
              <button
                type="button"
                onClick={() => adjustEnd(2.0)}
                className="flex-1 rounded-lg bg-secondary/80 hover:bg-secondary py-1 text-xs font-mono font-medium text-zinc-300 transition"
              >
                +2.0s
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Info technique discrète */}
      <div className="flex items-center justify-between text-[11px] text-muted-foreground/70 pt-1 border-t border-border/40">
        <span className="flex items-center gap-1">
          <Info className="w-3 h-3" />
          Timecodes vidéo source :
        </span>
        <span className="font-mono">
          {formatTime(currentStart)} → {formatTime(currentEnd)}
        </span>
      </div>
    </div>
  );
}
