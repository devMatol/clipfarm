"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Account } from "@/lib/types";
import { YouTubeIcon } from "@/components/icons/YouTubeIcon";
import {
  Trash2,
  ExternalLink,
  ShieldCheck,
  RefreshCw,
  PlusCircle,
  AlertCircle,
  CheckCircle2,
  Clock,
  FlaskConical,
  Info,
} from "lucide-react";

export default function AccountsPage() {
  const queryClient = useQueryClient();
  const [connecting, setConnecting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showConfigHelp, setShowConfigHelp] = useState(false);

  const { data: accounts, isLoading, error } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => api.getAccounts(),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteAccount(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
    },
    onError: (err: any) => {
      alert("Erreur lors de la déconnexion : " + err.message);
    },
  });

  const createTestMutation = useMutation({
    mutationFn: (platform: string) =>
      api.createTestAccount(platform, `Chaîne Démo (${platform === "youtube" ? "YouTube" : platform})`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      setErrorMsg(null);
    },
    onError: (err: any) => {
      setErrorMsg(err.message || "Erreur création compte test");
    },
  });

  const handleConnectYouTube = async () => {
    try {
      setConnecting(true);
      setErrorMsg(null);
      const res = await api.getYouTubeConnectUrl();
      if (res.auth_url) {
        window.location.href = res.auth_url;
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Impossible de démarrer la connexion YouTube.");
      setConnecting(false);
    }
  };

  const getStatusBadge = (status: Account["status"]) => {
    switch (status) {
      case "connected":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Connecté
          </span>
        );
      case "expiring_soon":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Clock className="w-3.5 h-3.5" />
            Expire bientôt
          </span>
        );
      case "expired":
      case "revoked":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertCircle className="w-3.5 h-3.5" />
            À reconnecter
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-8">
      {/* En-tête */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white">Comptes & Réseaux Sociaux</h1>
        <p className="mt-2 text-sm text-muted-foreground max-w-3xl leading-relaxed">
          Gère tes comptes de publication pour YouTube, TikTok et Instagram. Tes jetons d&apos;authentification
          sont chiffrés en local (AES-128-CBC Fernet) et ne quittent jamais ton ordinateur.
        </p>
      </div>

      {errorMsg && (
        <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-200 text-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Erreur de connexion</p>
              <p className="mt-0.5 text-xs text-rose-300">{errorMsg}</p>
              {errorMsg.toLowerCase().includes("client_id") && (
                <p className="mt-2 text-xs text-rose-200/90 leading-relaxed">
                  Pour connecter un vrai compte, configurez <code>YOUTUBE_CLIENT_ID</code> et{" "}
                  <code>YOUTUBE_CLIENT_SECRET</code> dans votre fichier <code>.env</code>. Vous pouvez
                  aussi créer un compte de test ci-contre pour tester l&apos;application sans attendre.
                </p>
              )}
            </div>
          </div>
          <button
            onClick={() => createTestMutation.mutate("youtube")}
            disabled={createTestMutation.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shrink-0 transition"
          >
            <FlaskConical className="w-3.5 h-3.5" />
            <span>Créer un compte de test</span>
          </button>
        </div>
      )}

      {/* Liste des comptes connectés */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <span>Comptes connectés</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">
            {accounts?.length || 0}
          </span>
        </h2>

        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground border border-border/40 rounded-xl bg-card/40 animate-pulse">
            Chargement des comptes...
          </div>
        ) : accounts && accounts.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {accounts.map((acc) => (
              <div
                key={acc.id}
                className="p-5 rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm flex items-center justify-between gap-4 transition hover:border-border"
              >
                <div className="flex items-center gap-3.5 min-w-0">
                  {acc.avatar_url ? (
                    <img
                      src={acc.avatar_url}
                      alt={acc.name}
                      className="w-12 h-12 rounded-full border border-border shrink-0 object-cover"
                    />
                  ) : (
                    <div className="w-12 h-12 rounded-full bg-red-600/20 text-red-400 flex items-center justify-center shrink-0 border border-red-500/30">
                      <YouTubeIcon className="w-6 h-6" />
                    </div>
                  )}

                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-white truncate text-base">{acc.name}</h3>
                      {getStatusBadge(acc.status)}
                    </div>
                    <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                      <span className="uppercase font-mono tracking-wider text-purple-400">
                        {acc.platform}
                      </span>
                      <span>•</span>
                      <span>ID: {acc.platform_account_id}</span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => {
                    if (confirm(`Déconnecter le compte "${acc.name}" ?`)) {
                      deleteMutation.mutate(acc.id);
                    }
                  }}
                  disabled={deleteMutation.isPending}
                  className="p-2.5 rounded-lg border border-border/60 text-muted-foreground hover:text-rose-400 hover:border-rose-500/30 hover:bg-rose-500/10 transition shrink-0"
                  title="Déconnecter ce compte"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-8 text-center text-muted-foreground border border-dashed border-border/60 rounded-xl bg-card/20">
            Aucun compte connecté pour l&apos;instant. Connecte un compte ci-dessous pour commencer à publier.
          </div>
        )}
      </section>

      {/* Ajouter un compte */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-white">Ajouter un compte</h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Carte YouTube */}
          <div className="p-6 rounded-xl border border-border/60 bg-gradient-to-b from-card/80 to-card/40 flex flex-col justify-between gap-6 transition hover:border-red-500/30">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-lg bg-red-600/10 border border-red-500/20 text-red-400 flex items-center justify-center">
                <YouTubeIcon className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-semibold text-white text-base">YouTube Shorts</h3>
                <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                  Publication automatique de Shorts (jusqu&apos;à 3 minutes, 9:16 ou 1:1) sur ta chaîne YouTube avec balises et visibilité.
                </p>
              </div>
            </div>

            <div className="space-y-2">
              <button
                onClick={handleConnectYouTube}
                disabled={connecting}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-red-600 hover:bg-red-500 text-white font-medium text-sm transition active:scale-95 disabled:opacity-50"
              >
                {connecting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Connexion...</span>
                  </>
                ) : (
                  <>
                    <PlusCircle className="w-4 h-4" />
                    <span>Connecter YouTube (OAuth)</span>
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={() => createTestMutation.mutate("youtube")}
                disabled={createTestMutation.isPending}
                className="w-full flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg border border-border/80 text-muted-foreground hover:text-white hover:bg-zinc-800 text-xs font-medium transition"
              >
                <FlaskConical className="w-3.5 h-3.5 text-purple-400" />
                <span>Ajouter un compte Démo (Test local)</span>
              </button>
            </div>
          </div>

          {/* Carte TikTok (Phase 6b) */}
          <div className="p-6 rounded-xl border border-border/40 bg-card/20 flex flex-col justify-between gap-6 opacity-75">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-lg bg-zinc-800 border border-border/40 text-zinc-400 flex items-center justify-center font-bold text-xs">
                TT
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-white text-base">TikTok</h3>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400 border border-zinc-700">
                    Étape suivante
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                  Content Posting API officielle (Direct Post) avec gestion du consentement musique et interactions.
                </p>
              </div>
            </div>

            <button
              disabled
              className="w-full py-2.5 px-4 rounded-lg bg-zinc-800 text-zinc-500 font-medium text-sm cursor-not-allowed"
            >
              Disponible à l&apos;étape (b)
            </button>
          </div>

          {/* Carte Instagram (Phase 6b) */}
          <div className="p-6 rounded-xl border border-border/40 bg-card/20 flex flex-col justify-between gap-6 opacity-75">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-lg bg-zinc-800 border border-border/40 text-zinc-400 flex items-center justify-center font-bold text-xs">
                IG
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-white text-base">Instagram Reels</h3>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400 border border-zinc-700">
                    Étape suivante
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                  Meta Graph API pour Reels avec conteneurs vidéo et partage dans le fil principal.
                </p>
              </div>
            </div>

            <button
              disabled
              className="w-full py-2.5 px-4 rounded-lg bg-zinc-800 text-zinc-500 font-medium text-sm cursor-not-allowed"
            >
              Disponible à l&apos;étape (b)
            </button>
          </div>
        </div>
      </section>

      {/* Encadré sécurité & confidentialité */}
      <div className="p-5 rounded-xl border border-purple-500/20 bg-purple-950/10 text-xs text-purple-200/80 flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-purple-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="font-semibold text-purple-300">Confidentialité et sécurité locale stricte</p>
          <p className="leading-relaxed">
            ClipFarm est une application 100% locale. Vos jetons OAuth (Access & Refresh tokens) sont
            stockés avec un chiffrement symétrique Fernet (AES-128-CBC) dérivé de votre clé locale.
            Les métadonnées privées (GPS, nom de machine) sont automatiquement purgées de vos vidéos
            avant tout envoi. Rien n&apos;est publié sans votre accord explicite.
          </p>
        </div>
      </div>
    </div>
  );
}
