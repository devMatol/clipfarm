"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Publication } from "@/lib/types";
import { YouTubeIcon } from "@/components/icons/YouTubeIcon";
import {
  ExternalLink,
  AlertCircle,
  CheckCircle2,
  Clock,
  RefreshCw,
  Send,
} from "lucide-react";
import Link from "next/link";

export default function PublicationsPage() {
  const [filter, setFilter] = useState<string>("all");

  const { data: publications, isLoading } = useQuery({
    queryKey: ["publications"],
    queryFn: () => api.getPublications(),
    refetchInterval: 5000,
  });

  const filteredPubs = (publications || []).filter((p) => {
    if (filter === "all") return true;
    return p.status === filter;
  });

  const getStatusBadge = (status: Publication["status"]) => {
    switch (status) {
      case "published":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Publié
          </span>
        );
      case "uploading":
      case "processing":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            Envoi en cours
          </span>
        );
      case "scheduled":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Clock className="w-3.5 h-3.5" />
            Planifié
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertCircle className="w-3.5 h-3.5" />
            Échec
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-zinc-500/10 text-zinc-400 border border-zinc-500/20">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-8">
      {/* En-tête */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Publications</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Historique et suivi de vos publications sur les réseaux sociaux.
          </p>
        </div>

        {/* Filtres */}
        <div className="flex items-center gap-2 p-1 rounded-lg bg-card/60 border border-border/60">
          {[
            { id: "all", label: "Tous" },
            { id: "published", label: "Publiés" },
            { id: "uploading", label: "En cours" },
            { id: "scheduled", label: "Planifiés" },
            { id: "failed", label: "Échecs" },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setFilter(item.id)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition ${
                filter === item.id
                  ? "bg-purple-600 text-white shadow-sm"
                  : "text-muted-foreground hover:text-white"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="p-12 text-center text-muted-foreground border border-border/40 rounded-xl bg-card/40 animate-pulse">
          Chargement de l&apos;historique des publications...
        </div>
      ) : filteredPubs.length > 0 ? (
        <div className="space-y-3">
          {filteredPubs.map((pub) => {
            const title = pub.metadata_json?.title || `Clip ${pub.clip_id}`;
            return (
              <div
                key={pub.id}
                className="p-5 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm flex flex-col md:flex-row md:items-center justify-between gap-4 transition hover:border-border"
              >
                <div className="flex items-start gap-4 min-w-0">
                  <div className="w-10 h-10 rounded-lg bg-red-600/10 border border-red-500/20 text-red-400 flex items-center justify-center shrink-0 mt-0.5">
                    <YouTubeIcon className="w-5 h-5" />
                  </div>

                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold text-white truncate max-w-md">{title}</h3>
                      {getStatusBadge(pub.status)}
                    </div>

                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="uppercase font-mono text-purple-400">{pub.platform}</span>
                      <span>•</span>
                      <Link
                        href={`/clips/${pub.clip_id}`}
                        className="hover:underline text-zinc-400"
                      >
                        Clip #{pub.clip_id}
                      </Link>
                      <span>•</span>
                      <span>{new Date(pub.created_at).toLocaleString("fr-FR")}</span>
                    </div>

                    {pub.error && (
                      <p className="mt-2 text-xs text-rose-300 bg-rose-500/10 border border-rose-500/20 p-2 rounded-lg">
                        <strong>Erreur :</strong> {pub.error}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  {pub.url && (
                    <a
                      href={pub.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30 text-xs font-semibold transition"
                    >
                      <span>Voir le Short</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="p-12 text-center text-muted-foreground border border-dashed border-border/60 rounded-xl bg-card/20 space-y-3">
          <Send className="w-8 h-8 mx-auto text-zinc-500" />
          <p className="text-sm">Aucune publication trouvée pour ce filtre.</p>
          <p className="text-xs text-muted-foreground">
            Ouvrez un clip depuis un projet pour le publier directement sur YouTube Shorts.
          </p>
        </div>
      )}
    </div>
  );
}
