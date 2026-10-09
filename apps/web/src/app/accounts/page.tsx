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
  Sparkles,
  KeyRound,
  Check,
} from "lucide-react";

export default function AccountsPage() {
  const queryClient = useQueryClient();
  const [connectingYouTube, setConnectingYouTube] = useState(false);
  const [connectingTikTok, setConnectingTikTok] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [showConfigGuide, setShowConfigGuide] = useState(false);

  const { data: accounts, isLoading } = useQuery({
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

  const handleConnectYouTube = async () => {
    try {
      setConnectingYouTube(true);
      setErrorMsg(null);
      const res = await api.getYouTubeConnectUrl();
      if (res.auth_url) {
        window.location.href = res.auth_url;
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Impossible de démarrer la connexion YouTube.");
      setConnectingYouTube(false);
    }
  };

  const handleConnectTikTok = async () => {
    try {
      setConnectingTikTok(true);
      setErrorMsg(null);
      const res = await api.getTikTokConnectUrl();
      if (res.auth_url) {
        window.location.href = res.auth_url;
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Impossible de démarrer la connexion TikTok.");
      setConnectingTikTok(false);
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
    <div className="space-y-8 max-w-6xl">
      {/* En-tête */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
            <span>Comptes & Réseaux Sociaux</span>
          </h1>
          <p className="mt-2 text-sm text-muted-foreground max-w-3xl leading-relaxed">
            Connecte directement tes comptes YouTube Shorts et TikTok. 100% gratuit, sans abonnement tiers ni intermédiaire.
            Tes jetons d&apos;authentification sont chiffrés localement (AES-128-CBC) et restent sur ta machine.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setShowConfigGuide(!showConfigGuide)}
          className="px-3.5 py-2 rounded-xl border border-border/80 bg-zinc-900/60 text-zinc-300 hover:text-white hover:border-zinc-700 text-xs font-semibold flex items-center gap-2 self-start shrink-0 transition"
        >
          <KeyRound className="w-4 h-4 text-purple-400" />
          <span>{showConfigGuide ? "Masquer la config" : "Comment configurer les clés gratuites"}</span>
        </button>
      </div>

      {/* Guide configuration gratuite (accordéon) */}
      {showConfigGuide && (
        <div className="p-5 rounded-2xl bg-zinc-950/80 border border-purple-500/20 text-xs text-zinc-300 space-y-4 animate-in fade-in">
          <div className="flex items-center gap-2 text-purple-300 font-bold text-sm">
            <Sparkles className="w-4 h-4 text-purple-400" />
            <span>Guide d&apos;obtention des clés API gratuites</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-zinc-900/70 border border-zinc-800 space-y-2">
              <div className="flex items-center gap-2 font-bold text-red-400">
                <YouTubeIcon className="w-4 h-4" />
                <span>YouTube Data API v3 (Gratuit)</span>
              </div>
              <p className="text-zinc-400 text-[11px] leading-relaxed">
                1. Va sur <a href="https://console.cloud.google.com" target="_blank" rel="noreferrer" className="text-purple-400 underline">Google Cloud Console</a>.<br />
                2. Active l&apos;API <strong>YouTube Data API v3</strong>.<br />
                3. Crée des identifiants OAuth Client ID (Application Web).<br />
                4. Ajoute l&apos;URI de redirection : <code>http://localhost:3000/accounts/callback</code>.<br />
                5. Renseigne dans le fichier <code>.env</code> :<br />
                <code className="text-zinc-200">GOOGLE_CLIENT_ID=...</code><br />
                <code className="text-zinc-200">GOOGLE_CLIENT_SECRET=...</code>
              </p>
            </div>

            <div className="p-4 rounded-xl bg-zinc-900/70 border border-zinc-800 space-y-2">
              <div className="flex items-center gap-2 font-bold text-cyan-400">
                <TikTokIcon className="w-4 h-4" />
                <span>TikTok Content Posting API (Gratuit)</span>
              </div>
              <p className="text-zinc-400 text-[11px] leading-relaxed">
                1. Va sur <a href="https://developers.tiktok.com" target="_blank" rel="noreferrer" className="text-cyan-400 underline">TikTok for Developers</a>.<br />
                2. Crée une application gratuite et active <strong>Content Posting API</strong>.<br />
                3. Ajoute l&apos;URI de redirection : <code>http://localhost:3000/accounts/callback</code>.<br />
                4. Renseigne dans le fichier <code>.env</code> :<br />
                <code className="text-zinc-200">TIKTOK_CLIENT_KEY=...</code><br />
                <code className="text-zinc-200">TIKTOK_CLIENT_SECRET=...</code><br />
                <em>(Pour tester sans clé, utilise simplement le bouton « Ajouter un compte Démo » ci-dessous !)</em>
              </p>
            </div>
          </div>
        </div>
      )}

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
        <h2 className="text-lg font-semibold text-white">Ajouter un compte (100% Gratuit)</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Carte YouTube Shorts */}
          <div className="p-6 rounded-2xl border border-red-500/20 bg-gradient-to-b from-red-950/10 to-card/40 flex flex-col justify-between gap-6 transition hover:border-red-500/40">
            <div className="space-y-3">
              <div className="w-12 h-12 rounded-xl bg-red-600/10 border border-red-500/20 text-red-400 flex items-center justify-center">
                <YouTubeIcon className="w-7 h-7" />
              </div>
              <div>
                <h3 className="font-bold text-white text-lg">YouTube Shorts</h3>
                <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                  Publication directe sur ta chaîne YouTube avec balises #Shorts, choix de visibilité (Public / Non répertorié / Privé) et validation stricte.
                </p>
              </div>
            </div>

            <div className="space-y-2">
              <button
                onClick={handleConnectYouTube}
                disabled={connectingYouTube}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-red-600 hover:bg-red-500 text-white font-semibold text-sm transition active:scale-95 disabled:opacity-50 shadow-lg shadow-red-900/20"
              >
                {connectingYouTube ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Connexion YouTube...</span>
                  </>
                ) : (
                  <>
                    <PlusCircle className="w-4 h-4" />
                    <span>Connecter YouTube (OAuth Officiel)</span>
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={() => createTestMutation.mutate("youtube")}
                disabled={createTestMutation.isPending}
                className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl border border-border/80 text-muted-foreground hover:text-white hover:bg-zinc-800 text-xs font-medium transition"
              >
                <FlaskConical className="w-3.5 h-3.5 text-purple-400" />
                <span>Ajouter un compte Démo YouTube (Test local)</span>
              </button>
            </div>
          </div>

          {/* Carte TikTok Direct */}
          <div className="p-6 rounded-2xl border border-cyan-500/30 bg-gradient-to-b from-cyan-950/20 to-card/40 flex flex-col justify-between gap-6 transition hover:border-cyan-500/60 shadow-lg shadow-cyan-950/20">
            <div className="space-y-3">
              <div className="w-12 h-12 rounded-xl bg-cyan-600/10 border border-cyan-500/20 text-cyan-400 flex items-center justify-center">
                <TikTokIcon className="w-7 h-7" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-white text-lg">TikTok</h3>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/30">
                    Direct & Gratuit
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                  Connexion directe via l&apos;API officielle TikTok Content Posting. 100% gratuit, sans passerelle payante. Téléversement binaire direct et planification dans le calendrier.
                </p>
              </div>
            </div>

            <div className="space-y-2">
              <button
                onClick={handleConnectTikTok}
                disabled={connectingTikTok}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-sm transition active:scale-95 disabled:opacity-50 shadow-lg shadow-cyan-900/30"
              >
                {connectingTikTok ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Connexion TikTok...</span>
                  </>
                ) : (
                  <>
                    <PlusCircle className="w-4 h-4" />
                    <span>Connecter TikTok (OAuth Direct)</span>
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={() => createTestMutation.mutate("tiktok")}
                disabled={createTestMutation.isPending}
                className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl border border-border/80 text-muted-foreground hover:text-white hover:bg-zinc-800 text-xs font-medium transition"
              >
                <FlaskConical className="w-3.5 h-3.5 text-cyan-400" />
                <span>Ajouter un compte Démo TikTok (Test local)</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Encadré sécurité & architecture */}
      <div className="p-5 rounded-xl border border-purple-500/20 bg-purple-950/10 text-xs text-purple-200/80 flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-purple-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="font-semibold text-purple-300">Architecture 100% Locale &amp; Données Protégées</p>
          <p className="leading-relaxed">
            ClipFarm communique directement avec les serveurs officiels de YouTube et TikTok depuis ton ordinateur.
            Aucun intermédiaire ni abonnement payant. Tes jetons d&apos;accès OAuth sont chiffrés en local (AES-128-CBC)
            avec ta clé secrète, et tes vidéos sont automatiquement nettoyées de leurs métadonnées personnelles (GPS, modèle caméra) avant toute publication.
          </p>
        </div>
      </div>
    </div>
  );
}
