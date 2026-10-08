"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { RefreshCw, CheckCircle2, AlertCircle } from "lucide-react";
import Link from "next/link";

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const error = searchParams.get("error");

    if (error) {
      setStatus("error");
      setErrorMsg(`Autorisation refusée ou annulée : ${error}`);
      return;
    }

    if (!code) {
      setStatus("error");
      setErrorMsg("Aucun code d'autorisation reçu dans l'URL.");
      return;
    }

    // Appel API pour finaliser l'échange de jetons et enregistrer le compte
    api
      .connectYouTubeCallback(code, state || undefined)
      .then((account) => {
        setStatus("success");
        setTimeout(() => {
          router.push("/accounts");
        }, 1500);
      })
      .catch((err: any) => {
        setStatus("error");
        setErrorMsg(err.message || "Erreur lors de l'enregistrement du compte.");
      });
  }, [searchParams, router]);

  return (
    <div className="max-w-md mx-auto my-16 p-8 rounded-2xl border border-border/60 bg-card/60 backdrop-blur-md text-center shadow-xl">
      {status === "loading" && (
        <div className="space-y-4">
          <div className="w-12 h-12 mx-auto rounded-full bg-purple-500/10 text-purple-400 flex items-center justify-center">
            <RefreshCw className="w-6 h-6 animate-spin" />
          </div>
          <h2 className="text-xl font-bold text-white">Connexion du compte en cours...</h2>
          <p className="text-xs text-muted-foreground">
            Échange sécurisé des jetons OAuth avec YouTube Data API et chiffrement local.
          </p>
        </div>
      )}

      {status === "success" && (
        <div className="space-y-4">
          <div className="w-12 h-12 mx-auto rounded-full bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-bold text-white">Compte connecté avec succès !</h2>
          <p className="text-xs text-muted-foreground">
            Redirection vers la page des comptes...
          </p>
        </div>
      )}

      {status === "error" && (
        <div className="space-y-5">
          <div className="w-12 h-12 mx-auto rounded-full bg-rose-500/10 text-rose-400 flex items-center justify-center">
            <AlertCircle className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-bold text-white">Échec de la connexion</h2>
          <p className="text-xs text-rose-300 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-left">
            {errorMsg}
          </p>
          <div>
            <Link
              href="/accounts"
              className="inline-flex items-center justify-center px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold transition"
            >
              Retourner aux comptes
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AccountsCallbackPage() {
  return (
    <Suspense fallback={<div className="p-12 text-center text-muted-foreground">Chargement...</div>}>
      <CallbackContent />
    </Suspense>
  );
}
