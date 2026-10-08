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
} from "lucide-react";
import Link from "next/link";

interface PublishModalProps {
  clip: Clip;
  isOpen: boolean;
  onClose: () => void;
}

export function PublishModal({ clip, isOpen, onClose }: PublishModalProps) {
  const queryClient = useQueryClient();

  const { data: accounts = [], isLoading: isAccountsLoading } = useQuery<Account[]>({
    queryKey: ["accounts"],
    queryFn: () => api.getAccounts(),
    enabled: isOpen,
  });

  const [selectedAccountId, setSelectedAccountId] = useState<string>("");
  const [platform, setPlatform] = useState<string>("youtube");
  const [title, setTitle] = useState<string>(clip.title ? `${clip.title} #Shorts` : "Super Short #Shorts");
  const [description, setDescription] = useState<string>("");
  const [tagsStr, setTagsStr] = useState<string>("shorts,clipfarm");
  const [privacy, setPrivacy] = useState<string>("unlisted");
  const [madeForKids, setMadeForKids] = useState<boolean>(false);
  const [categoryId, setCategoryId] = useState<string>("22"); // People & Blogs
  const [rightsConfirmed, setRightsConfirmed] = useState<boolean>(false);

  // Étape confirmation
  const [isConfirming, setIsConfirming] = useState<boolean>(false);
  const [isGeneratingMetadata, setIsGeneratingMetadata] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successResult, setSuccessResult] = useState<{ id: string; url?: string | null } | null>(null);

  // Sélectionner le premier compte par défaut
  useEffect(() => {
    if (accounts.length > 0 && !selectedAccountId) {
      setSelectedAccountId(accounts[0].id);
    }
  }, [accounts, selectedAccountId]);

  // Réinitialiser les messages d'erreur à l'ouverture
  useEffect(() => {
    if (isOpen) {
      setErrorMessage(null);
      setSuccessResult(null);
      setIsConfirming(false);
      setRightsConfirmed(false);
    }
  }, [isOpen]);

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

  const publishMutation = useMutation({
    mutationFn: async () => {
      const tags = tagsStr
        .split(",")
        .map((t) => t.trim().replace(/^#/, ""))
        .filter(Boolean);

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
        publish_now: true,
        rights_confirmed: rightsConfirmed,
      });
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["publications"] });
      if (data.status === "failed") {
        setErrorMessage(data.error || "La plateforme a refusé la publication.");
      } else {
        setSuccessResult({ id: data.id, url: data.url });
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
      <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl border border-border/80 bg-zinc-950 p-6 sm:p-8 shadow-2xl text-foreground">
        {/* Fermer */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 p-2 rounded-lg text-muted-foreground hover:text-white hover:bg-zinc-800 transition"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Titre Modal */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-red-600/20 text-red-400 flex items-center justify-center border border-red-500/30">
            <YouTubeIcon className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Publier sur YouTube Shorts</h2>
            <p className="text-xs text-muted-foreground">
              Envoi direct et sécurisé depuis ton PC vers YouTube Data API
            </p>
          </div>
        </div>

        {/* Résultat succès */}
        {successResult ? (
          <div className="mt-6 p-6 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-center space-y-4">
            <div className="w-12 h-12 mx-auto rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">Clip publié avec succès !</h3>
              <p className="text-xs text-emerald-300 mt-1">
                La vidéo a été nettoyée de ses métadonnées techniques et envoyée sur YouTube Shorts.
              </p>
            </div>

            {successResult.url && (
              <div className="pt-2">
                <a
                  href={successResult.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition"
                >
                  <span>Voir le Short sur YouTube</span>
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
            )}

            <div className="pt-4 flex justify-center gap-3">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-lg border border-border text-xs font-semibold text-white hover:bg-zinc-800 transition"
              >
                Fermer
              </button>
              <Link
                href="/publications"
                className="px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-xs font-semibold text-white transition"
              >
                Voir l&apos;historique des publications
              </Link>
            </div>
          </div>
        ) : (
          <div className="mt-6 space-y-6">
            {errorMessage && (
              <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-200 text-xs flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold">Erreur de publication</p>
                  <p className="mt-0.5">{errorMessage}</p>
                </div>
              </div>
            )}

            {/* Vérification des comptes disponibles */}
            {isAccountsLoading ? (
              <div className="p-6 text-center text-xs text-muted-foreground animate-pulse">
                Chargement des comptes connectés...
              </div>
            ) : accounts.length === 0 ? (
              <div className="p-6 rounded-xl border border-dashed border-border/80 bg-zinc-900/40 text-center space-y-3">
                <p className="text-sm font-semibold text-white">Aucun compte YouTube connecté</p>
                <p className="text-xs text-muted-foreground max-w-md mx-auto">
                  Tu dois connecter ta chaîne YouTube dans l&apos;onglet Comptes avant de pouvoir publier.
                </p>
                <Link
                  href="/accounts"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold transition"
                >
                  <PlusCircle className="w-4 h-4" />
                  <span>Aller à la page des comptes</span>
                </Link>
              </div>
            ) : !isConfirming ? (
              /* Étape 1 : Formulaire de métadonnées */
              <div className="space-y-4">
                {/* Choix du compte */}
                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1.5">
                    Compte cible
                  </label>
                  <select
                    value={selectedAccountId}
                    onChange={(e) => setSelectedAccountId(e.target.value)}
                    className="w-full rounded-xl border border-border bg-zinc-900 px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-purple-500"
                  >
                    {accounts.map((acc) => (
                      <option key={acc.id} value={acc.id}>
                        {acc.name} ({acc.platform})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Bouton IA Métadonnées */}
                <div className="flex justify-between items-center pt-1">
                  <span className="text-xs font-semibold text-zinc-300">Métadonnées YouTube</span>
                  <button
                    type="button"
                    onClick={handleGenerateMetadata}
                    disabled={isGeneratingMetadata}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border border-purple-500/30 text-xs font-semibold transition disabled:opacity-50"
                  >
                    {isGeneratingMetadata ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Génération IA...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                        <span>Générer titre & description par IA</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Titre */}
                <div>
                  <div className="flex justify-between text-xs text-muted-foreground mb-1">
                    <span>Titre (max 100 caractères, #Shorts recommandé)</span>
                    <span className={title.length > 100 ? "text-rose-400 font-bold" : ""}>
                      {title.length} / 100
                    </span>
                  </div>
                  <input
                    type="text"
                    value={title}
                    maxLength={100}
                    onChange={(e) => setTitle(e.target.value)}
                    className="w-full rounded-xl border border-border bg-zinc-900 px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-purple-500"
                    placeholder="Titre accrocheur #Shorts"
                  />
                </div>

                {/* Description */}
                <div>
                  <div className="flex justify-between text-xs text-muted-foreground mb-1">
                    <span>Description & mentions</span>
                    <span>{description.length} / 5000</span>
                  </div>
                  <textarea
                    rows={3}
                    value={description}
                    maxLength={5000}
                    onChange={(e) => setDescription(e.target.value)}
                    className="w-full rounded-xl border border-border bg-zinc-900 px-3 py-2 text-xs text-white focus:outline-none focus:ring-1 focus:ring-purple-500"
                    placeholder="Description du clip, hashtags, liens..."
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
                    className="w-full rounded-xl border border-border bg-zinc-900 px-3 py-2 text-xs text-white focus:outline-none focus:ring-1 focus:ring-purple-500"
                    placeholder="gaming, gta6, twitch, drôle"
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
                      className="w-full rounded-xl border border-border bg-zinc-900 px-3 py-2 text-xs text-white focus:outline-none"
                    >
                      <option value="unlisted">Non répertorié (recommandé pour test)</option>
                      <option value="private">Privé</option>
                      <option value="public">Public</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-zinc-300 mb-1">
                      Catégorie YouTube
                    </label>
                    <select
                      value={categoryId}
                      onChange={(e) => setCategoryId(e.target.value)}
                      className="w-full rounded-xl border border-border bg-zinc-900 px-3 py-2 text-xs text-white focus:outline-none"
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
                      className="w-full rounded-xl border border-border bg-zinc-900 px-3 py-2 text-xs text-white focus:outline-none"
                    >
                      <option value="false">Non (standard)</option>
                      <option value="true">Oui</option>
                    </select>
                  </div>
                </div>

                {/* Case obligatoire Droits */}
                <div className="p-4 rounded-xl border border-purple-500/30 bg-purple-950/20 flex items-start gap-3 mt-4">
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
                    son téléversement vers YouTube.
                  </label>
                </div>

                {/* Actions */}
                <div className="flex justify-end gap-3 pt-4 border-t border-border/60">
                  <button
                    type="button"
                    onClick={onClose}
                    className="px-4 py-2 rounded-xl border border-border text-xs font-semibold text-white hover:bg-zinc-800 transition"
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
                    className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-xs font-semibold text-white shadow-md disabled:opacity-40 transition"
                  >
                    Vérifier & Récapituler
                  </button>
                </div>
              </div>
            ) : (
              /* Étape 2 : Confirmation obligatoire avant envoi */
              <div className="space-y-5">
                <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-200 text-xs flex items-start gap-3">
                  <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold text-amber-300">Confirmation explicite avant envoi</p>
                    <p className="mt-0.5">
                      Veuillez vérifier les informations ci-dessous. Le fichier vidéo sera assaini
                      (métadonnées purgées) et envoyé à la chaîne YouTube sélectionnée.
                    </p>
                  </div>
                </div>

                <div className="p-4 rounded-xl border border-border bg-zinc-900/60 space-y-2 text-xs">
                  <div className="flex justify-between border-b border-border/40 pb-2">
                    <span className="text-muted-foreground">Chaîne de destination :</span>
                    <span className="font-semibold text-white">{selectedAccount?.name}</span>
                  </div>
                  <div className="flex justify-between border-b border-border/40 pb-2">
                    <span className="text-muted-foreground">Titre du Short :</span>
                    <span className="font-semibold text-white truncate max-w-xs">{title}</span>
                  </div>
                  <div className="flex justify-between border-b border-border/40 pb-2">
                    <span className="text-muted-foreground">Visibilité :</span>
                    <span className="font-mono text-purple-400 uppercase font-semibold">{privacy}</span>
                  </div>
                  <div className="flex justify-between border-b border-border/40 pb-2">
                    <span className="text-muted-foreground">Durée du clip :</span>
                    <span className="text-white">{(clip.end - clip.start).toFixed(1)} s</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Droits confirmés :</span>
                    <span className="text-emerald-400 font-semibold">Oui (Détenus)</span>
                  </div>
                </div>

                {/* Actions finales */}
                <div className="flex justify-between gap-3 pt-4 border-t border-border/60">
                  <button
                    type="button"
                    onClick={() => setIsConfirming(false)}
                    disabled={publishMutation.isPending}
                    className="px-4 py-2 rounded-xl border border-border text-xs font-semibold text-white hover:bg-zinc-800 transition"
                  >
                    Modifier
                  </button>
                  <button
                    type="button"
                    onClick={() => publishMutation.mutate()}
                    disabled={publishMutation.isPending}
                    className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-xs font-semibold text-white shadow-lg shadow-red-600/30 transition disabled:opacity-50"
                  >
                    {publishMutation.isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Téléversement vers YouTube...</span>
                      </>
                    ) : (
                      <>
                        <Send className="w-4 h-4" />
                        <span>Confirmer et Publier maintenant</span>
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
