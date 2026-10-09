"use client";

import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Clip, Account, PublishMetadata } from "@/lib/types";
import { YouTubeIcon } from "@/components/icons/YouTubeIcon";
import {
  X,
  Sparkles,
  Send,
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  ShieldAlert,
  Loader2,
  Check,
  PlusCircle,
  Calendar,
  Clock,
  Flame,
  Zap,
  Info,
} from "lucide-react";
import Link from "next/link";

interface PublishModalProps {
  clip: Clip;
  isOpen: boolean;
  onClose: () => void;
}

interface PredictedSlot {
  clip_id: string;
  platform: string;
  suggested_time: string;
  day_name: string;
  slot_name: string;
  predictive_score: number;
  algorithmic_reason: string;
  viral_title?: string;
  viral_description?: string;
  viral_tags?: string[];
}

export function PublishModal({ clip, isOpen, onClose }: PublishModalProps) {
  const queryClient = useQueryClient();

  const { data: accounts = [], isLoading: isAccountsLoading } = useQuery<Account[]>({
    queryKey: ["accounts"],
    queryFn: () => api.getAccounts(),
    enabled: isOpen,
  });

  // Mode de publication : IA Prédictive, Immédiat, ou Manuel
  const [publishMode, setPublishMode] = useState<"ai_schedule" | "now" | "manual">("ai_schedule");

  const [selectedAccountId, setSelectedAccountId] = useState<string>("");
  const [platform, setPlatform] = useState<string>("youtube");
  const [title, setTitle] = useState<string>(clip.title ? `${clip.title} #Shorts` : "Super Short #Shorts");
  const [description, setDescription] = useState<string>("");
  const [tagsStr, setTagsStr] = useState<string>("shorts,clipfarm");
  const [privacy, setPrivacy] = useState<string>("public");
  const [madeForKids, setMadeForKids] = useState<boolean>(false);
  const [categoryId, setCategoryId] = useState<string>("22");
  const [rightsConfirmed, setRightsConfirmed] = useState<boolean>(false);

  // État Planification IA
  const [predictedSlots, setPredictedSlots] = useState<PredictedSlot[]>([]);
  const [selectedSlotIndex, setSelectedSlotIndex] = useState<number>(0);
  const [isPredictingSlots, setIsPredictingSlots] = useState<boolean>(false);
  const [predictSummary, setPredictSummary] = useState<string>("");

  // État Planification Manuelle
  const [manualDateTime, setManualDateTime] = useState<string>("");

  // Étape confirmation
  const [isConfirming, setIsConfirming] = useState<boolean>(false);
  const [isGeneratingMetadata, setIsGeneratingMetadata] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successResult, setSuccessResult] = useState<{
    id: string;
    url?: string | null;
    status: string;
    scheduled_at?: string | null;
  } | null>(null);

  // Sélectionner le premier compte par défaut et synchroniser la plateforme
  useEffect(() => {
    if (accounts.length > 0) {
      const current = accounts.find((a) => a.id === selectedAccountId) || accounts[0];
      if (!selectedAccountId) {
        setSelectedAccountId(current.id);
      }
      if (current.platform !== platform) {
        setPlatform(current.platform);
        if (current.platform === "tiktok") {
          setTagsStr("tiktok,pourtoi,fyp,shorts");
          setTitle((prev) => prev.replace("#Shorts", "#TikTok"));
        } else if (current.platform === "youtube") {
          setTagsStr("shorts,clipfarm");
          setTitle((prev) => prev.replace("#TikTok", "#Shorts"));
        }
      }
    }
  }, [accounts, selectedAccountId, platform]);

  // Charger les créneaux IA à l'ouverture du modal
  useEffect(() => {
    if (isOpen) {
      setErrorMessage(null);
      setSuccessResult(null);
      setIsConfirming(false);
      setRightsConfirmed(false);

      // Initialiser date manuelle à demain 18h45
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      tomorrow.setHours(18, 45, 0, 0);
      setManualDateTime(tomorrow.toISOString().slice(0, 16));

      // Déclencher la prédiction IA pour ce clip
      loadAiPrediction();
    }
  }, [isOpen, clip.id]);

  const loadAiPrediction = async () => {
    try {
      setIsPredictingSlots(true);
      const res = await api.predictClipSlots(clip.id, platform);
      if (res.predictions && res.predictions.length > 0) {
        setPredictedSlots(res.predictions);
        setSelectedSlotIndex(0);
        setPredictSummary(res.summary || "");

        // Pré-remplir les métadonnées si l'IA en suggère
        const top = res.predictions[0];
        if (top.viral_title && (!title || title.includes("Super Short"))) {
          setTitle(top.viral_title);
        }
        if (top.viral_description && !description) {
          setDescription(top.viral_description);
        }
        if (top.viral_tags && top.viral_tags.length > 0) {
          setTagsStr(top.viral_tags.join(", "));
        }
      }
    } catch (err) {
      console.error("Impossible de récupérer la prédiction IA pour le clip:", err);
    } finally {
      setIsPredictingSlots(false);
    }
  };

  const handleGenerateMetadata = async () => {
    try {
      setIsGeneratingMetadata(true);
      setErrorMessage(null);
      const meta = await api.generatePublishMetadata(clip.id, platform);
      if (meta.title) setTitle(meta.title);
      if (meta.description) setDescription(meta.description);
      if (meta.tags && meta.tags.length > 0) setTagsStr(meta.tags.join(", "));
    } catch (err: any) {
      setErrorMessage("Échec génération métadonnées : " + err.message);
    } finally {
      setIsGeneratingMetadata(false);
    }
  };

  const currentSlot = predictedSlots[selectedSlotIndex];

  const publishMutation = useMutation({
    mutationFn: async () => {
      const tags = tagsStr
        .split(",")
        .map((t) => t.trim().replace(/^#/, ""))
        .filter(Boolean);

      const isImmediate = publishMode === "now";
      let scheduledAt: string | null = null;
      let predScore: number | undefined = undefined;
      let algoReason: string | undefined = undefined;

      if (publishMode === "ai_schedule" && currentSlot) {
        scheduledAt = currentSlot.suggested_time;
        predScore = currentSlot.predictive_score;
        algoReason = currentSlot.algorithmic_reason;
      } else if (publishMode === "manual" && manualDateTime) {
        scheduledAt = new Date(manualDateTime).toISOString();
      }

      return api.publishClip(clip.id, {
        clip_id: clip.id,
        account_id: selectedAccountId || (accounts.length > 0 ? accounts[0].id : ""),
        platform,
        title,
        description,
        tags,
        privacy,
        made_for_kids: madeForKids,
        category_id: categoryId,
        publish_now: isImmediate,
        scheduled_at: scheduledAt,
        predictive_score: predScore,
        algorithmic_reason: algoReason,
        rights_confirmed: rightsConfirmed,
      });
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["publications"] });
      queryClient.invalidateQueries({ queryKey: ["calendar"] });
      if (data.status === "failed") {
        setErrorMessage(data.error || "La plateforme a refusé la publication.");
      } else {
        setSuccessResult({
          id: data.id,
          url: data.url,
          status: data.status,
          scheduled_at: data.scheduled_at,
        });
      }
    },
    onError: (err: any) => {
      setErrorMessage(err.message || "Erreur lors de la publication.");
    },
  });

  if (!isOpen) return null;

  const selectedAccount = accounts.find((a) => a.id === selectedAccountId);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl max-h-[92vh] overflow-y-auto rounded-3xl border border-slate-800 bg-zinc-950 p-6 sm:p-8 shadow-2xl text-foreground">
        {/* Fermer */}
        <button
          onClick={onClose}
          className="absolute right-5 top-5 p-2 rounded-xl text-muted-foreground hover:text-white hover:bg-zinc-800 transition"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Titre Modal */}
        <div className="flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-purple-600 to-indigo-500 text-white flex items-center justify-center shadow-lg shadow-purple-900/30">
            <Calendar className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              Publication & Planification
              <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">
                IA Gemini
              </span>
            </h2>
            <p className="text-xs text-muted-foreground">
              Diffuse ton clip immédiatement ou planifie-le à l'horaire de pointe optimal calculé par l'IA.
            </p>
          </div>
        </div>

        {/* Résultat succès */}
        {successResult ? (
          <div className="mt-6 p-6 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 text-center space-y-4">
            <div className="w-12 h-12 mx-auto rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center shadow-lg shadow-emerald-900/20">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">
                {successResult.status === "published"
                  ? "Clip publié avec succès !"
                  : "Clip planifié avec succès dans le Calendrier !"}
              </h3>
              <p className="text-xs text-emerald-300 mt-1 max-w-md mx-auto">
                {successResult.status === "published"
                  ? "La vidéo a été nettoyée de ses métadonnées techniques et envoyée sur YouTube Shorts."
                  : `Le clip est programmé pour le ${
                      successResult.scheduled_at
                        ? new Date(successResult.scheduled_at).toLocaleString("fr-FR", {
                            weekday: "long",
                            day: "numeric",
                            month: "long",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "créneau choisi"
                    }. Il sera publié automatiquement.`}
              </p>
            </div>

            {successResult.url && (
              <div className="pt-2">
                <a
                  href={successResult.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition shadow-md shadow-emerald-900/30"
                >
                  <span>Voir le Short sur YouTube</span>
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
            )}

            <div className="pt-4 flex justify-center gap-3">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-xl border border-slate-800 text-xs font-semibold text-white hover:bg-zinc-800 transition"
              >
                Fermer
              </button>
              <Link
                href="/calendar"
                className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-xs font-semibold text-white transition shadow-md shadow-purple-900/30"
              >
                Ouvrir le Calendrier Prédictif
              </Link>
            </div>
          </div>
        ) : (
          <div className="mt-6 space-y-5">
            {errorMessage && (
              <div className="p-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 text-rose-200 text-xs flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold">Erreur de publication</p>
                  <p className="mt-0.5">{errorMessage}</p>
                </div>
              </div>
            )}

            {/* SÉLECTEUR DE MODE DE PUBLICATION */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 bg-zinc-900/80 p-1.5 rounded-2xl border border-slate-800">
              <button
                type="button"
                onClick={() => setPublishMode("ai_schedule")}
                className={`flex flex-col items-start p-3 rounded-xl text-left transition ${
                  publishMode === "ai_schedule"
                    ? "bg-purple-600 text-white shadow-lg shadow-purple-900/40 font-semibold"
                    : "text-zinc-400 hover:text-white hover:bg-zinc-800/60"
                }`}
              >
                <div className="flex items-center gap-1.5 text-xs font-bold">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Planifier par IA</span>
                </div>
                <span className={`text-[10px] mt-0.5 ${publishMode === "ai_schedule" ? "text-purple-200" : "text-zinc-500"}`}>
                  Pic d'audience optimal
                </span>
              </button>

              <button
                type="button"
                onClick={() => setPublishMode("now")}
                className={`flex flex-col items-start p-3 rounded-xl text-left transition ${
                  publishMode === "now"
                    ? "bg-purple-600 text-white shadow-lg shadow-purple-900/40 font-semibold"
                    : "text-zinc-400 hover:text-white hover:bg-zinc-800/60"
                }`}
              >
                <div className="flex items-center gap-1.5 text-xs font-bold">
                  <Zap className="w-3.5 h-3.5" />
                  <span>Publier direct</span>
                </div>
                <span className={`text-[10px] mt-0.5 ${publishMode === "now" ? "text-purple-200" : "text-zinc-500"}`}>
                  Envoi immédiat
                </span>
              </button>

              <button
                type="button"
                onClick={() => setPublishMode("manual")}
                className={`flex flex-col items-start p-3 rounded-xl text-left transition ${
                  publishMode === "manual"
                    ? "bg-purple-600 text-white shadow-lg shadow-purple-900/40 font-semibold"
                    : "text-zinc-400 hover:text-white hover:bg-zinc-800/60"
                }`}
              >
                <div className="flex items-center gap-1.5 text-xs font-bold">
                  <Clock className="w-3.5 h-3.5" />
                  <span>Manuel</span>
                </div>
                <span className={`text-[10px] mt-0.5 ${publishMode === "manual" ? "text-purple-200" : "text-zinc-500"}`}>
                  Choisir date et heure
                </span>
              </button>
            </div>

            {/* ENCART SPÉCIFIQUE AU MODE IA PRÉDICTIF */}
            {publishMode === "ai_schedule" && (
              <div className="p-4 rounded-2xl bg-purple-950/20 border border-purple-500/30 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-purple-300 flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                    Créneau Stratégique Recommandé par Gemini
                  </span>
                  <button
                    type="button"
                    onClick={loadAiPrediction}
                    disabled={isPredictingSlots}
                    className="text-[11px] text-purple-400 hover:text-purple-200 font-semibold flex items-center gap-1 transition"
                  >
                    {isPredictingSlots ? <Loader2 className="w-3 h-3 animate-spin" /> : "Recalculer"}
                  </button>
                </div>

                {isPredictingSlots ? (
                  <div className="py-6 text-center text-xs text-purple-300/80 animate-pulse flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-purple-400" />
                    <span>Analyse des pics d'audience et calcul de rétention...</span>
                  </div>
                ) : currentSlot ? (
                  <div className="space-y-2 text-xs">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 rounded-xl bg-zinc-950/80 border border-purple-500/20">
                      <div>
                        <div className="font-bold text-white text-sm">
                          📅 {new Date(currentSlot.suggested_time).toLocaleDateString("fr-FR", {
                            weekday: "long",
                            day: "numeric",
                            month: "long",
                          })}{" "}
                          à {new Date(currentSlot.suggested_time).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
                        </div>
                        <div className="text-[11px] text-purple-300 mt-0.5 font-medium">
                          {currentSlot.slot_name}
                        </div>
                      </div>
                      <span className="px-2.5 py-1 rounded-full bg-amber-500/20 text-amber-300 font-bold text-xs border border-amber-500/30 w-fit">
                        🔥 Score IA {currentSlot.predictive_score}%
                      </span>
                    </div>

                    <p className="text-[11px] text-zinc-300 leading-relaxed bg-zinc-900/60 p-2.5 rounded-xl border border-slate-800">
                      <strong className="text-purple-300">Raisonnement : </strong>
                      {currentSlot.algorithmic_reason}
                    </p>

                    {/* Sélecteur de créneaux alternatifs si disponibles */}
                    {predictedSlots.length > 1 && (
                      <div className="flex items-center gap-2 pt-1 text-[11px]">
                        <span className="text-zinc-400">Autres options :</span>
                        {predictedSlots.map((s, idx) => (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => setSelectedSlotIndex(idx)}
                            className={`px-2 py-0.5 rounded-lg border text-[10px] font-semibold transition ${
                              selectedSlotIndex === idx
                                ? "bg-purple-600 text-white border-purple-500"
                                : "bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-white"
                            }`}
                          >
                            Option {idx + 1} ({s.day_name})
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-xs text-zinc-400 py-2">
                    Aucun créneau spécifique calculé. Le clip sera programmé au prochain pic d'audience disponible.
                  </div>
                )}
              </div>
            )}

            {/* ENCART SPÉCIFIQUE AU MODE MANUEL */}
            {publishMode === "manual" && (
              <div className="p-4 rounded-2xl bg-zinc-900/80 border border-slate-800 space-y-2">
                <label className="block text-xs font-semibold text-zinc-300">
                  Date et heure de publication souhaitée (heure de Paris)
                </label>
                <input
                  type="datetime-local"
                  value={manualDateTime}
                  onChange={(e) => setManualDateTime(e.target.value)}
                  className="w-full rounded-xl border border-slate-800 bg-zinc-950 px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-purple-500"
                />
                <p className="text-[10px] text-zinc-500">
                  Le clip sera sauvegardé dans le Calendrier et diffusé automatiquement à l'heure indiquée.
                </p>
              </div>
            )}

            {/* Vérification des comptes disponibles */}
            {isAccountsLoading ? (
              <div className="p-6 text-center text-xs text-muted-foreground animate-pulse">
                Chargement des comptes connectés...
              </div>
            ) : accounts.length === 0 ? (
              <div className="p-6 rounded-2xl border border-dashed border-border/80 bg-zinc-900/40 text-center space-y-3">
                <p className="text-sm font-semibold text-white">Aucun compte connecté</p>
                <p className="text-xs text-muted-foreground max-w-md mx-auto">
                  Tu dois connecter ta chaîne YouTube ou ton compte TikTok (via Postiz) dans l&apos;onglet Comptes avant de pouvoir publier.
                </p>
                <Link
                  href="/accounts"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold transition shadow-md shadow-purple-900/30"
                >
                  <PlusCircle className="w-4 h-4" />
                  <span>Aller à la page des comptes</span>
                </Link>
              </div>
            ) : !isConfirming ? (
              /* FORMULAIRE DE MÉTADONNÉES */
              <div className="space-y-4">
                {/* Choix du compte */}
                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1.5 flex items-center justify-between">
                    <span>Compte de destination</span>
                    <span className="text-[11px] font-normal text-purple-400 capitalize">
                      Plateforme : {platform === "youtube" ? "YouTube Shorts" : platform === "tiktok" ? "TikTok (Postiz)" : platform}
                    </span>
                  </label>
                  <select
                    value={selectedAccountId}
                    onChange={(e) => setSelectedAccountId(e.target.value)}
                    className="w-full rounded-xl border border-slate-800 bg-zinc-900 px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-purple-500"
                  >
                    {accounts.map((acc) => (
                      <option key={acc.id} value={acc.id}>
                        {acc.name} ({acc.platform === "youtube" ? "YouTube" : acc.platform === "tiktok" ? "TikTok via Postiz" : acc.platform})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Bouton IA Métadonnées */}
                <div className="flex justify-between items-center pt-1">
                  <span className="text-xs font-semibold text-zinc-300">Contenu du Short</span>
                  <button
                    type="button"
                    onClick={handleGenerateMetadata}
                    disabled={isGeneratingMetadata}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border border-purple-500/30 text-xs font-semibold transition disabled:opacity-50"
                  >
                    {isGeneratingMetadata ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Génération IA...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                        <span>Générer titre & description virale</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Titre */}
                <div>
                  <div className="flex justify-between text-xs text-muted-foreground mb-1">
                    <span>Titre viral (max 100 caractères)</span>
                    <span className={title.length > 100 ? "text-rose-400 font-bold" : ""}>
                      {title.length} / 100
                    </span>
                  </div>
                  <input
                    type="text"
                    value={title}
                    maxLength={100}
                    onChange={(e) => setTitle(e.target.value)}
                    className="w-full rounded-xl border border-slate-800 bg-zinc-900 px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-purple-500"
                    placeholder="Titre accrocheur #Shorts"
                  />
                </div>

                {/* Description */}
                <div>
                  <div className="flex justify-between text-xs text-muted-foreground mb-1">
                    <span>Description & call-to-action</span>
                    <span>{description.length} / 5000</span>
                  </div>
                  <textarea
                    rows={3}
                    value={description}
                    maxLength={5000}
                    onChange={(e) => setDescription(e.target.value)}
                    className="w-full rounded-xl border border-slate-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:outline-none focus:ring-1 focus:ring-purple-500"
                    placeholder="Description du clip, hashtags, question pour susciter les commentaires..."
                  />
                </div>

                {/* Tags */}
                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">
                    Mots-clés / Tags (séparés par des virgules)
                  </label>
                  <input
                    type="text"
                    value={tagsStr}
                    onChange={(e) => setTagsStr(e.target.value)}
                    className="w-full rounded-xl border border-slate-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:outline-none focus:ring-1 focus:ring-purple-500"
                    placeholder="shorts, gaming, humour, clip"
                  />
                </div>

                {/* Options YouTube */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                  <div>
                    <label className="block text-xs font-semibold text-zinc-300 mb-1">
                      Visibilité
                    </label>
                    <select
                      value={privacy}
                      onChange={(e) => setPrivacy(e.target.value)}
                      className="w-full rounded-xl border border-slate-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:outline-none"
                    >
                      <option value="public">Public</option>
                      <option value="unlisted">Non répertorié</option>
                      <option value="private">Privé</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-zinc-300 mb-1">
                      Catégorie YouTube
                    </label>
                    <select
                      value={categoryId}
                      onChange={(e) => setCategoryId(e.target.value)}
                      className="w-full rounded-xl border border-slate-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:outline-none"
                    >
                      <option value="22">Personnes & blogs</option>
                      <option value="20">Jeux vidéo (Gaming)</option>
                      <option value="24">Divertissement</option>
                      <option value="23">Humour</option>
                      <option value="27">Éducation</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-zinc-300 mb-1">
                      Conçu pour les enfants
                    </label>
                    <select
                      value={madeForKids ? "true" : "false"}
                      onChange={(e) => setMadeForKids(e.target.value === "true")}
                      className="w-full rounded-xl border border-slate-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:outline-none"
                    >
                      <option value="false">Non (standard)</option>
                      <option value="true">Oui</option>
                    </select>
                  </div>
                </div>

                {/* Certification Droits */}
                <div className="p-4 rounded-2xl border border-purple-500/30 bg-purple-950/20 flex items-start gap-3 mt-4">
                  <input
                    type="checkbox"
                    id="rights_confirm"
                    checked={rightsConfirmed}
                    onChange={(e) => setRightsConfirmed(e.target.checked)}
                    className="mt-1 h-4 w-4 rounded border-border text-purple-600 focus:ring-purple-500 shrink-0 cursor-pointer"
                  />
                  <label htmlFor="rights_confirm" className="text-xs text-zinc-200 cursor-pointer">
                    <span className="font-semibold text-white block">
                      Certification des droits de diffusion (Obligatoire)
                    </span>
                    Je certifie détenir les droits d&apos;exploitation et de diffusion sur ce contenu et autorise
                    son traitement et téléversement.
                  </label>
                </div>

                {/* Bouton Suivant */}
                <div className="flex justify-end gap-3 pt-4 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={onClose}
                    className="px-4 py-2 rounded-xl border border-slate-800 text-xs font-semibold text-white hover:bg-zinc-800 transition"
                  >
                    Annuler
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (!rightsConfirmed) {
                        alert("Vous devez cocher la certification des droits avant de continuer.");
                        return;
                      }
                      if (!title.trim()) {
                        alert("Veuillez renseigner un titre pour le Short.");
                        return;
                      }
                      setIsConfirming(true);
                    }}
                    disabled={!rightsConfirmed}
                    className="px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-xs font-semibold text-white shadow-lg shadow-purple-900/40 disabled:opacity-40 transition"
                  >
                    {publishMode === "ai_schedule"
                      ? "Vérifier & Planifier avec l'IA"
                      : publishMode === "manual"
                      ? "Vérifier & Planifier"
                      : "Vérifier & Publier"}
                  </button>
                </div>
              </div>
            ) : (
              /* ÉTAPE DE CONFIRMATION AVANT EXÉCUTION */
              <div className="space-y-5">
                <div className="p-4 rounded-2xl border border-amber-500/30 bg-amber-500/10 text-amber-200 text-xs flex items-start gap-3">
                  <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold text-amber-300">Récapitulatif avant confirmation</p>
                    <p className="mt-0.5">
                      {publishMode === "now"
                        ? "Le fichier vidéo sera assaini et publié immédiatement sur YouTube Shorts."
                        : `Le clip sera programmé dans le Calendrier Prédictif pour être publié à la date indiquée.`}
                    </p>
                  </div>
                </div>

                <div className="p-4 rounded-2xl border border-slate-800 bg-zinc-900/80 space-y-2.5 text-xs">
                  <div className="flex justify-between border-b border-slate-800 pb-2">
                    <span className="text-muted-foreground">Mode choisi :</span>
                    <span className="font-bold text-purple-400">
                      {publishMode === "ai_schedule"
                        ? "✨ Planification IA Prédictive"
                        : publishMode === "manual"
                        ? "📅 Planification Manuelle"
                        : "⚡ Publication Immédiate"}
                    </span>
                  </div>

                  {publishMode !== "now" && (
                    <div className="flex justify-between border-b border-slate-800 pb-2">
                      <span className="text-muted-foreground">Créneau programmé :</span>
                      <span className="font-mono text-emerald-400 font-semibold">
                        {publishMode === "ai_schedule" && currentSlot
                          ? new Date(currentSlot.suggested_time).toLocaleString("fr-FR")
                          : manualDateTime
                          ? new Date(manualDateTime).toLocaleString("fr-FR")
                          : "Non défini"}
                      </span>
                    </div>
                  )}

                  <div className="flex justify-between border-b border-slate-800 pb-2">
                    <span className="text-muted-foreground">Chaîne de destination :</span>
                    <span className="font-semibold text-white">{selectedAccount?.name}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-800 pb-2">
                    <span className="text-muted-foreground">Titre du Short :</span>
                    <span className="font-semibold text-white truncate max-w-xs">{title}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-800 pb-2">
                    <span className="text-muted-foreground">Visibilité :</span>
                    <span className="font-mono text-purple-400 uppercase font-semibold">{privacy}</span>
                  </div>
                  <div className="flex justify-between border-b border-slate-800 pb-2">
                    <span className="text-muted-foreground">Durée du clip :</span>
                    <span className="text-white">{(clip.end - clip.start).toFixed(1)} s</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Droits confirmés :</span>
                    <span className="text-emerald-400 font-semibold">Oui (Détenus)</span>
                  </div>
                </div>

                {/* Actions finales */}
                <div className="flex justify-between gap-3 pt-4 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => setIsConfirming(false)}
                    disabled={publishMutation.isPending}
                    className="px-4 py-2 rounded-xl border border-slate-800 text-xs font-semibold text-white hover:bg-zinc-800 transition disabled:opacity-40"
                  >
                    ← Modifier
                  </button>

                  <button
                    type="button"
                    onClick={() => publishMutation.mutate()}
                    disabled={publishMutation.isPending}
                    className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-xs font-semibold text-white shadow-lg shadow-purple-900/40 disabled:opacity-50 transition"
                  >
                    {publishMutation.isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>
                          {publishMode === "now" ? "Téléversement en cours..." : "Programmation en cours..."}
                        </span>
                      </>
                    ) : (
                      <>
                        {publishMode === "now" ? <Send className="w-4 h-4" /> : <Calendar className="w-4 h-4" />}
                        <span>
                          {publishMode === "now"
                            ? "Confirmer et Publier maintenant"
                            : "Confirmer la Planification"}
                        </span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
