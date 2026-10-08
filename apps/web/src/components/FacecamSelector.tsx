"use client";

import React, { useState, useRef, useEffect } from "react";
import { Crop, Move, Check } from "lucide-react";

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface FacecamSelectorProps {
  imageUrl?: string;
  initialRect?: Rect;
  onChange: (rect: Rect) => void;
}

export function FacecamSelector({
  imageUrl,
  initialRect = { x: 0.7, y: 0.08, w: 0.25, h: 0.25 },
  onChange,
}: FacecamSelectorProps) {
  const [rect, setRect] = useState<Rect>(initialRect);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => {
    onChange(rect);
  }, [rect, onChange]);

  const handlePreset = (preset: "top-right" | "top-left" | "bottom-right" | "bottom-left") => {
    let newRect = { ...rect };
    if (preset === "top-right") newRect = { x: 0.72, y: 0.05, w: 0.25, h: 0.25 };
    if (preset === "top-left") newRect = { x: 0.03, y: 0.05, w: 0.25, h: 0.25 };
    if (preset === "bottom-right") newRect = { x: 0.72, y: 0.7, w: 0.25, h: 0.25 };
    if (preset === "bottom-left") newRect = { x: 0.03, y: 0.7, w: 0.25, h: 0.25 };
    setRect(newRect);
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const bounds = containerRef.current.getBoundingClientRect();
    const clickX = (e.clientX - bounds.left) / bounds.width;
    const clickY = (e.clientY - bounds.top) / bounds.height;

    // Début d'un nouveau tracé ou déplacement
    setIsDragging(true);
    setDragStart({ x: clickX, y: clickY });
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDragging || !dragStart || !containerRef.current) return;
    const bounds = containerRef.current.getBoundingClientRect();
    const curX = Math.max(0, Math.min(1, (e.clientX - bounds.left) / bounds.width));
    const curY = Math.max(0, Math.min(1, (e.clientY - bounds.top) / bounds.height));

    const x = Math.min(dragStart.x, curX);
    const y = Math.min(dragStart.y, curY);
    const w = Math.max(0.05, Math.abs(curX - dragStart.x));
    const h = Math.max(0.05, Math.abs(curY - dragStart.y));

    setRect({
      x: Number(x.toFixed(3)),
      y: Number(y.toFixed(3)),
      w: Number(w.toFixed(3)),
      h: Number(h.toFixed(3)),
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    setDragStart(null);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
          <Crop className="h-3.5 w-3.5 text-purple-400" />
          Zone Facecam (glissez pour tracer le rectangle)
        </label>
        <div className="flex gap-1.5 text-xs">
          <button
            type="button"
            onClick={() => handlePreset("top-right")}
            className="rounded bg-secondary/80 px-2 py-0.5 text-xs text-muted-foreground hover:text-white transition"
          >
            Haut Droite
          </button>
          <button
            type="button"
            onClick={() => handlePreset("top-left")}
            className="rounded bg-secondary/80 px-2 py-0.5 text-xs text-muted-foreground hover:text-white transition"
          >
            Haut Gauche
          </button>
          <button
            type="button"
            onClick={() => handlePreset("bottom-right")}
            className="rounded bg-secondary/80 px-2 py-0.5 text-xs text-muted-foreground hover:text-white transition"
          >
            Bas Droite
          </button>
        </div>
      </div>

      <div
        ref={containerRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        className="relative aspect-video w-full overflow-hidden rounded-xl border border-purple-500/30 bg-neutral-950 shadow-inner select-none cursor-crosshair group"
      >
        {imageUrl ? (
          <img src={imageUrl} alt="Aperçu vidéo" className="h-full w-full object-contain pointer-events-none" />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground text-xs p-4 text-center">
            <Move className="h-6 w-6 mb-2 text-purple-400 opacity-60" />
            <span>Zone d'aperçu 16:9 du flux vidéo.</span>
            <span className="text-[10px] text-muted-foreground/80 mt-1">
              Tracé interactif actif : cliquez et glissez pour cadrer la caméra.
            </span>
          </div>
        )}

        {/* Rectangle de sélection Facecam */}
        <div
          className="absolute border-2 border-purple-500 bg-purple-500/25 shadow-lg flex items-center justify-center transition-all duration-75 pointer-events-none"
          style={{
            left: `${rect.x * 100}%`,
            top: `${rect.y * 100}%`,
            width: `${rect.w * 100}%`,
            height: `${rect.h * 100}%`,
          }}
        >
          <span className="bg-purple-900/90 text-purple-200 text-[10px] font-bold px-1.5 py-0.5 rounded shadow border border-purple-400/40">
            Facecam ({Math.round(rect.w * 100)}% x {Math.round(rect.h * 100)}%)
          </span>
        </div>
      </div>

      <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground px-1">
        <span>X: {rect.x.toFixed(2)} | Y: {rect.y.toFixed(2)}</span>
        <span>L: {rect.w.toFixed(2)} | H: {rect.h.toFixed(2)}</span>
      </div>
    </div>
  );
}
