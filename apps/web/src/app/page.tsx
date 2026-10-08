"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { PlusCircle, Video, Clock, CheckCircle2, AlertCircle, Loader2, ArrowRight, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { Project, ProjectStatus } from "@/lib/types";

function getStatusBadge(status: ProjectStatus, progress: number, step: string) {
  switch (status) {
    case "ready":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-400 border border-emerald-500/20">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Prêt
        </span>
      );
    case "failed":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-500/10 px-2.5 py-1 text-xs font-medium text-rose-400 border border-rose-500/20">
          <AlertCircle className="h-3.5 w-3.5" />
          Échec
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-400 border border-amber-500/20">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          {step} ({Math.round(progress * 100)}%)
        </span>
      );
  }
}

export default function HomePage() {
  const queryClient = useQueryClient();
  const { data: projects = [], isLoading, error } = useQuery<Project[]>({
    queryKey: ["projects"],
    queryFn: api.getProjects,
    refetchInterval: (query) => {
      // Re-fetch toutes les 3s si au moins un projet est en cours
      const hasActive = query.state.data?.some((p) => !["ready", "failed"].includes(p.status));
      return hasActive ? 3000 : 15000;
    },
  });

  return (
    <div className="space-y-8">
      {/* Hero header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border/60 pb-6">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white">Vos Projets</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Générez des clips verticaux optimisés avec IA et sous-titres en local.
          </p>
        </div>
        <Link
          href="/projects/new"
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-purple-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-purple-600/25 hover:bg-purple-500 active:scale-95 transition"
        >
          <PlusCircle className="h-4 w-4" />
          Nouveau projet
        </Link>
      </div>

      {/* Liste des projets */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin text-purple-400" />
          <p className="mt-3 text-sm">Chargement de vos projets...</p>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-destructive/50 bg-destructive/10 p-6 text-center text-rose-300">
          <AlertCircle className="mx-auto h-8 w-8 text-rose-400 mb-2" />
          <p className="font-semibold">Impossible de joindre l'API ClipFarm</p>
          <p className="text-xs text-rose-400/80 mt-1">Vérifiez que le serveur FastAPI est bien démarré sur le port 8000.</p>
        </div>
      ) : projects.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/80 bg-card/40 p-12 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Video className="h-7 w-7" />
          </div>
          <h2 className="mt-4 text-lg font-semibold text-white">Aucun projet pour le moment</h2>
          <p className="mt-1 text-sm text-muted-foreground max-w-sm mx-auto">
            Commencez par importer une vidéo ou collez un lien YouTube pour extraire automatiquement les meilleurs clips.
          </p>
          <div className="mt-6">
            <Link
              href="/projects/new"
              className="inline-flex items-center gap-2 rounded-xl bg-purple-600 px-4 py-2.5 text-sm font-semibold text-white shadow-md hover:bg-purple-500 transition"
            >
              <PlusCircle className="h-4 w-4" />
              Créer un projet
            </Link>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {projects.map((proj) => {
            const sourceDisplay = proj.source_url || (proj.source_path ? proj.source_path.split(/[\\/]/).pop() : proj.id);
            const dateStr = new Date(proj.created_at).toLocaleDateString("fr-FR", {
              day: "numeric",
              month: "short",
              hour: "2-digit",
              minute: "2-digit",
            });

            return (
              <Link
                key={proj.id}
                href={`/projects/${proj.id}`}
                className="group relative flex flex-col justify-between rounded-xl border border-border/60 bg-card/70 p-5 shadow-sm hover:border-purple-500/40 hover:bg-card transition duration-200"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-mono text-xs text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                      #{proj.id}
                    </span>
                    {getStatusBadge(proj.status, proj.progress, proj.step)}
                  </div>

                  <h3 className="mt-3 font-semibold text-white line-clamp-2 group-hover:text-purple-300 transition" title={sourceDisplay || ""}>
                    {sourceDisplay}
                  </h3>

                  {/* Barre de progression si actif */}
                  {!["ready", "failed"].includes(proj.status) && (
                    <div className="mt-4">
                      <div className="flex justify-between text-xs text-muted-foreground mb-1">
                        <span>{proj.step}</span>
                        <span>{Math.round(proj.progress * 100)}%</span>
                      </div>
                      <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-purple-500 to-indigo-400 transition-all duration-300"
                          style={{ width: `${Math.round(proj.progress * 100)}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>

                <div className="mt-6 flex items-center justify-between border-t border-border/40 pt-3 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5" />
                    {dateStr}
                  </span>
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      title="Supprimer ce projet"
                      onClick={async (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        if (confirm(`Êtes-vous sûr de vouloir supprimer définitivement le projet #${proj.id} et tous ses clips ?`)) {
                          try {
                            await api.deleteProject(proj.id);
                            queryClient.invalidateQueries({ queryKey: ["projects"] });
                          } catch (err: any) {
                            alert(err.message || "Erreur lors de la suppression");
                          }
                        }
                      }}
                      className="p-1 text-muted-foreground hover:text-rose-400 rounded hover:bg-rose-500/10 transition"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                    <div className="flex items-center gap-1 font-medium text-white group-hover:text-purple-400 transition">
                      <span>{proj.clips_count ?? (proj.clips ? proj.clips.length : 0)} clips</span>
                      <ArrowRight className="h-3.5 w-3.5 transition transform group-hover:translate-x-0.5" />
                    </div>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
