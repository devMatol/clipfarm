"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Account } from "@/lib/types";
import { YouTubeIcon } from "@/components/icons/YouTubeIcon";
import { TikTokIcon } from "@/components/icons/TikTokIcon";
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
  Server,
  Share2,
  Sparkles,
} from "lucide-react";

export default function AccountsPage() {
  const queryClient = useQueryClient();
  const [connecting, setConnecting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [showPostizGuide, setShowPostizGuide] = useState(false);

  const { data: accounts, isLoading } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => api.getAccounts(),
  });

  const { data: postizStatus, refetch: refetchPostizStatus } = useQuery({
    queryKey: ["postizStatus"],
    queryFn: () => api.getPostizStatus(),
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
    mutationFn: (platform: string) => {
      const defaultName =
        platform === "youtube"
          ? "Chaîne Démo (YouTube)"
          : platform === "tiktok"
          ? "TikTok Démo (@clipfarm_test)"
          : `Compte Démo (${platform})`;
      return api.createTestAccount(platform, defaultName);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      setErrorMsg(null);
      setSuccessMsg("Compte de test créé avec succès !");
      setTimeout(() => setSuccessMsg(null), 3000);
    },
    onError: (err: any) => {
      setErrorMsg(err.message || "Erreur création compte test");
    },
  });

  const syncPostizMutation = useMutation({
    mutationFn: () => api.syncPostiz(),
    onSuccess: (synced) => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      refetchPostizStatus();
      setErrorMsg(null);
      if (synced.length === 0) {
        setSuccessMsg("Postiz synchronisé : aucun nouveau canal détecté.");
      } else {
        setSuccessMsg(`Succès : ${synced.length} canal(aux) synchronisé(s) depuis Postiz !`);
      }
      setTimeout(() => setSuccessMsg(null), 4000);
    },
    onError: (err: any) => {
      setErrorMsg("Échec de la synchronisation Postiz : " + (err.message || String(err)));
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

  const hasTikTokAccount = accounts?.some((a) => a.platform === "tiktok");

  return (
    <div className="space-y-8 max-w-6xl">
      {/* En-tête */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
          <span>Comptes & Réseaux Sociaux</span>
        </h1>
        <p className="mt-2 text-sm text-muted-foreground max-w-3xl leading-relaxed">
          Gère tes comptes de publication pour YouTube Shorts, TikTok et Instagram. Tes jetons d&apos;authentification
          sont chiffrés en local (AES-128-CBC Fernet) et ne quittent jamais ton ordinateur.
        </p>
      </div>

      {/* Messages de statut / feedback */}
      {errorMsg && (
        <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-200 text-sm flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-semibold">Erreur</p>
            <p className="mt-0.5 text-xs text-rose-300">{errorMsg}</p>
          </div>
        </div>
      )}

      {successMsg && (
        <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-200 text-sm flex items-center gap-3 animate-in fade-in">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
          <p className="font-medium text-xs sm:text-sm">{successMsg}</p>
        </div>
      )}

      {/* BANNIÈRE HUB POSTIZ (Intégration Intelligente) */}
      <div className="p-5 rounded-2xl border border-cyan-500/30 bg-gradient-to-r from-cyan-950/20 via-zinc-950/40 to-purple-950/20 backdrop-blur-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 flex items-center justify-center shrink-0">
              <Share2 className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-white text-base">Passerelle Postiz (TikTok, Instagram, Multi-réseaux)</h3>
                {postizStatus?.reachable && postizStatus?.authenticated ? (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    🟢 Actif & Connecté
                  </span>
                ) : postizStatus?.reachable ? (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    🟡 Service en ligne (Clé API requise)
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-zinc-800 text-zinc-400 border border-zinc-700">
                    ⚪ Service autonome optionnel
                  </span>
                )}
              </div>
              <p className="text-xs text-zinc-400 mt-0.5 leading-relaxed">
                Postiz permet de relier TikTok sans complexité de développement ni audit bloquant.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => setShowPostizGuide(!showPostizGuide)}
              className="px-3 py-1.5 rounded-lg border border-border/70 bg-zinc-900/60 text-zinc-300 hover:text-white text-xs font-semibold flex items-center gap-1.5 transition"
            >
              <Info className="w-3.5 h-3.5 text-cyan-400" />
              <span>{showPostizGuide ? "Masquer le guide" : "Comment lancer Postiz"}</span>
            </button>
            <button
              type="button"
              onClick={() => syncPostizMutation.mutate()}
              disabled={syncPostizMutation.isPending}
              className="px-3.5 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-lg shadow-cyan-900/30 transition disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${syncPostizMutation.isPending ? "animate-spin" : ""}`} />
              <span>Synchroniser les canaux Postiz</span>
            </button>
          </div>
        </div>

        {/* Guide déploiement Postiz accordéon */}
        {showPostizGuide && (
          <div className="p-4 rounded-xl bg-zinc-950/80 border border-cyan-500/20 text-xs text-zinc-300 space-y-3 animate-in fade-in">
            <p className="font-semibold text-cyan-300 flex items-center gap-1.5">
              <Server className="w-4 h-4" />
              Démarrer Postiz en local en 1 commande :
            </p>
            <div className="p-2.5 rounded-lg bg-zinc-900 font-mono text-[11px] text-zinc-200 border border-zinc-800 select-all">
              docker compose -f infra/postiz/docker-compose.yml up -d
            </div>
            <ol className="list-decimal list-inside space-y-1 text-zinc-400 text-[11px]">
              <li>
                Ouvrez <a href="http://localhost:4200" target="_blank" rel="noreferrer" className="text-cyan-400 underline font-mono">http://localhost:4200</a> et créez votre profil.
              </li>
              <li>
                Allez dans <strong>Integrations</strong> pour relier votre compte TikTok (ou Instagram).
              </li>
              <li>
                Dans <strong>Settings &gt; API</strong>, copiez votre clé API et ajoutez dans <code>.env</code> : <code>POSTIZ_API_KEY=votre_cle</code>.
              </li>
              <li>
                Revenez ici et cliquez sur <strong>Synchroniser les canaux Postiz</strong> !
              </li>
            </ol>
          </div>
        )}
      </div>

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
                  ) : acc.platform === "tiktok" ? (
                    <div className="w-12 h-12 rounded-full bg-cyan-600/20 text-cyan-400 flex items-center justify-center shrink-0 border border-cyan-500/30">
                      <TikTokIcon className="w-6 h-6" />
                    </div>
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
                      <span className="truncate">ID: {acc.platform_account_id}</span>
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
            Aucun compte connecté pour l&apos;instant. Connecte un compte ci-dessous ou ajoute un compte de test pour commencer.
          </div>
        )}
      </section>

      {/* Ajouter un compte */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-white">Ajouter un compte</h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Carte YouTube Shorts */}
          <div className="p-6 rounded-xl border border-border/60 bg-gradient-to-b from-card/80 to-card/40 flex flex-col justify-between gap-6 transition hover:border-red-500/30">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-lg bg-red-600/10 border border-red-500/20 text-red-400 flex items-center justify-center">
                <YouTubeIcon className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-semibold text-white text-base">YouTube Shorts</h3>
                <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                  Publication et programmation directe sur ta chaîne YouTube avec balises #Shorts et choix de visibilité.
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

          {/* Carte TikTok (via Postiz) */}
          <div className="p-6 rounded-xl border border-cyan-500/30 bg-gradient-to-b from-cyan-950/20 to-card/40 flex flex-col justify-between gap-6 transition hover:border-cyan-500/60 shadow-lg shadow-cyan-950/20">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-lg bg-cyan-600/10 border border-cyan-500/20 text-cyan-400 flex items-center justify-center">
                <TikTokIcon className="w-6 h-6" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-white text-base">TikTok</h3>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/30">
                    Via Postiz
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                  Publication et programmation automatique vers TikTok. Gère le consentement, les hashtags viraux (#PourToi) et l&apos;audience.
                </p>
              </div>
            </div>

            <div className="space-y-2">
              <a
                href="http://localhost:4200/integrations"
                target="_blank"
                rel="noreferrer"
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-medium text-sm transition active:scale-95"
              >
                <ExternalLink className="w-4 h-4" />
                <span>Connecter TikTok dans Postiz</span>
              </a>
              <button
                type="button"
                onClick={() => createTestMutation.mutate("tiktok")}
                disabled={createTestMutation.isPending}
                className="w-full flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg border border-border/80 text-muted-foreground hover:text-white hover:bg-zinc-800 text-xs font-medium transition"
              >
                <FlaskConical className="w-3.5 h-3.5 text-cyan-400" />
                <span>Ajouter un compte Démo TikTok</span>
              </button>
            </div>
          </div>

          {/* Carte Instagram Reels (via Postiz) */}
          <div className="p-6 rounded-xl border border-border/60 bg-gradient-to-b from-card/80 to-card/40 flex flex-col justify-between gap-6 transition hover:border-pink-500/30">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-lg bg-pink-600/10 border border-pink-500/20 text-pink-400 flex items-center justify-center font-bold text-xs">
                IG
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-white text-base">Instagram Reels</h3>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-pink-500/10 text-pink-400 border border-pink-500/20">
                    Via Postiz
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                  Meta Graph API via Postiz pour Reels avec conteneurs vidéo et partage dans le fil principal.
                </p>
              </div>
            </div>

            <div className="space-y-2">
              <a
                href="http://localhost:4200/integrations"
                target="_blank"
                rel="noreferrer"
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-white font-medium text-sm transition"
              >
                <ExternalLink className="w-4 h-4" />
                <span>Connecter Instagram dans Postiz</span>
              </a>
              <button
                type="button"
                onClick={() => createTestMutation.mutate("instagram")}
                disabled={createTestMutation.isPending}
                className="w-full flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg border border-border/80 text-muted-foreground hover:text-white hover:bg-zinc-800 text-xs font-medium transition"
              >
                <FlaskConical className="w-3.5 h-3.5 text-pink-400" />
                <span>Ajouter un compte Démo Instagram</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Encadré sécurité & architecture */}
      <div className="p-5 rounded-xl border border-purple-500/20 bg-purple-950/10 text-xs text-purple-200/80 flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-purple-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="font-semibold text-purple-300">Architecture locale &amp; isolation stricte</p>
          <p className="leading-relaxed">
            ClipFarm communique avec Postiz exclusivement par son API REST locale. Aucun code externe AGPL n&apos;est
            intégré au moteur. Vos jetons restent chiffrés en AES-128-CBC sur votre machine, et vos vidéos sont
            automatiquement nettoyées de leurs métadonnées sensibles (GPS, auteur) avant tout upload.
          </p>
        </div>
      </div>
    </div>
  );
}
