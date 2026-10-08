"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Calendar as CalendarIcon,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  Clock,
  Play,
  CheckCircle2,
  AlertTriangle,
  Flame,
  ExternalLink,
  Trash2,
  CalendarCheck,
  Send,
  Info,
  Layers,
  ArrowRight,
  RefreshCw,
  Video,
} from "lucide-react";

interface CalendarEvent {
  id: string;
  clip_id: string;
  project_id: string | null;
  project_title: string | null;
  clip_title: string | null;
  clip_hook: string | null;
  clip_duration: number;
  platform: string;
  account_id: string;
  account_name: string;
  account_avatar: string | null;
  scheduled_at: string | null;
  published_at: string | null;
  status: string;
  url: string | null;
  external_id: string | null;
  error: string | null;
  metadata: {
    title?: string;
    description?: string;
    tags?: string[];
    privacy?: string;
    predictive_score?: number;
    algorithmic_reason?: string;
  };
  created_at: string | null;
}

interface UnscheduledClip {
  id: string;
  index: number;
  project_id: string;
  project_title: string;
  title: string;
  hook: string;
  duration: number;
  start: number;
  end: number;
  scores: Record<string, any>;
  file_path: string;
  created_at: string;
}

interface AccountItem {
  id: string;
  platform: string;
  name: string;
  avatar_url: string | null;
  status: string;
}

interface PredictionItem {
  clip_id: string;
  clip_title: string;
  hook: string;
  platform: string;
  suggested_time: string;
  day_name: string;
  slot_name: string;
  predictive_score: number;
  algorithmic_reason: string;
  viral_title: string;
  viral_description: string;
  viral_tags: string[];
}

const PEAK_HOURS: Record<number, { label: string; time: string; badge: string }[]> = {
  0: [{ label: "Déjeuner Express", time: "12h30", badge: "🥪" }, { label: "Décompression Soir", time: "18h15", badge: "🌆" }],
  1: [{ label: "Pause Midi", time: "12h30", badge: "🥪" }, { label: "Pic d'Attention", time: "18h15", badge: "🎯" }],
  2: [
    { label: "Pic Jeunesse / Étudiants", time: "14h30", badge: "⚡" },
    { label: "Grand Pic Mercredi", time: "18h30", badge: "🚀" },
  ],
  3: [{ label: "Midi Mobile", time: "12h30", badge: "🥪" }, { label: "Haute Rétention", time: "18h30", badge: "📈" }],
  4: [
    { label: "Pause Déjeuner", time: "12h30", badge: "🥪" },
    { label: "Début Weekend Pop-culture", time: "19h00", badge: "🎉" },
  ],
  5: [
    { label: "Samedi Midi Chill", time: "12h15", badge: "🍔" },
    { label: "Soirée Détente", time: "18h45", badge: "🎮" },
  ],
  6: [
    { label: "Midi Avant-Première", time: "12h00", badge: "☀️" },
    { label: "👑 GRAND RECORD HEBDO", time: "18h45", badge: "🔥" },
    { label: "Prime Rétention Canapé", time: "20h30", badge: "🛋️" },
  ],
};

const FRENCH_DAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"];

export default function CalendarPage() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [unscheduled, setUnscheduled] = useState<UnscheduledClip[]>([]);
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [weekOffset, setWeekOffset] = useState(0);
  const [platformFilter, setPlatformFilter] = useState("all");

  // Modal IA Prédictive
  const [predictModalOpen, setPredictModalOpen] = useState(false);
  const [predictLoading, setPredictLoading] = useState(false);
  const [predictions, setPredictions] = useState<PredictionItem[]>([]);
  const [predictionSummary, setPredictionSummary] = useState("");
  const [selectedClipIds, setSelectedClipIds] = useState<string[]>([]);
  const [targetPlatform, setTargetPlatform] = useState("youtube");
  const [targetAccountId, setTargetAccountId] = useState("");
  const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [applying, setApplying] = useState(false);

  // Modal Explication Raisonnement IA
  const [reasonModalEvent, setReasonModalEvent] = useState<CalendarEvent | null>(null);

  // Modal Replanification
  const [rescheduleEvent, setRescheduleEvent] = useState<CalendarEvent | null>(null);
  const [rescheduleDateTime, setRescheduleDateTime] = useState("");
  const [rescheduling, setRescheduling] = useState(false);

  // Action directe de publication
  const [publishingId, setPublishingId] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const [eventsRes, unscheduledRes, accountsRes] = await Promise.all([
        fetch("http://localhost:8000/calendar/events"),
        fetch("http://localhost:8000/scheduling/unscheduled-clips"),
        fetch("http://localhost:8000/accounts"),
      ]);

      if (eventsRes.ok) setEvents(await eventsRes.json());
      if (unscheduledRes.ok) {
        const uclips = await unscheduledRes.json();
        setUnscheduled(uclips);
        setSelectedClipIds(uclips.map((c: UnscheduledClip) => c.id));
      }
      if (accountsRes.ok) {
        const accs = await accountsRes.json();
        setAccounts(accs);
        if (accs.length > 0 && !targetAccountId) {
          setTargetAccountId(accs[0].id);
        }
      }
    } catch (e) {
      console.error("Erreur de chargement du calendrier:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Calcul des jours de la semaine courante (du Lundi au Dimanche)
  const getWeekDates = (offset: number) => {
    const now = new Date();
    const currentDay = now.getDay(); // 0 = Dimanche, 1 = Lundi
    const distanceToMonday = (currentDay + 6) % 7;
    const monday = new Date(now);
    monday.setDate(now.getDate() - distanceToMonday + offset * 7);
    monday.setHours(0, 0, 0, 0);

    const days = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(monday);
      d.setDate(monday.getDate() + i);
      days.push(d);
    }
    return days;
  };

  const weekDays = getWeekDates(weekOffset);
  const weekStart = weekDays[0];
  const weekEnd = weekDays[6];

  const formatDateShort = (d: Date) => {
    return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
  };

  const isToday = (d: Date) => {
    const today = new Date();
    return (
      d.getDate() === today.getDate() &&
      d.getMonth() === today.getMonth() &&
      d.getFullYear() === today.getFullYear()
    );
  };

  const isSameDay = (d1: Date, d2String: string | null) => {
    if (!d2String) return false;
    const d2 = new Date(d2String);
    return (
      d1.getDate() === d2.getDate() &&
      d1.getMonth() === d2.getMonth() &&
      d1.getFullYear() === d2.getFullYear()
    );
  };

  // Filtrage des événements
  const filteredEvents = events.filter((e) => {
    if (platformFilter !== "all" && e.platform !== platformFilter) return false;
    return true;
  });

  // Déclencher la prédiction par IA
  const handleRunAiPrediction = async () => {
    setPredictLoading(true);
    setPredictions([]);
    try {
      const res = await fetch("http://localhost:8000/scheduling/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          clip_ids: selectedClipIds.length > 0 ? selectedClipIds : undefined,
          platforms: [targetPlatform],
          days_ahead: 7,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setPredictions(data.predictions || []);
        setPredictionSummary(data.summary || "");
      } else {
        alert("Erreur lors de la prédiction IA.");
      }
    } catch (err) {
      console.error(err);
      alert("Impossible de joindre le serveur pour la prédiction.");
    } finally {
      setPredictLoading(false);
    }
  };

  // Appliquer le calendrier prédit
  const handleApplySchedule = async () => {
    if (!rightsConfirmed) {
      alert("Vous devez certifier détenir les droits d'exploitation avant de planifier.");
      return;
    }
    if (predictions.length === 0) return;

    setApplying(true);
    try {
      const items = predictions.map((p) => ({
        clip_id: p.clip_id,
        account_id: targetAccountId || undefined,
        platform: p.platform || targetPlatform,
        scheduled_at: p.suggested_time,
        title: p.viral_title || p.clip_title,
        description: p.viral_description || "",
        tags: p.viral_tags || [],
        privacy: "public",
        rights_confirmed: true,
        predictive_score: p.predictive_score,
        algorithmic_reason: p.algorithmic_reason,
      }));

      const res = await fetch("http://localhost:8000/scheduling/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items }),
      });

      if (res.ok) {
        setPredictModalOpen(false);
        setPredictions([]);
        await loadData();
      } else {
        const err = await res.json();
        alert(err.detail || "Erreur lors de l'application de la planification.");
      }
    } catch (e) {
      console.error(e);
      alert("Erreur réseau lors de la planification.");
    } finally {
      setApplying(false);
    }
  };

  // Replanifier un clip individuel
  const handleRescheduleSubmit = async () => {
    if (!rescheduleEvent || !rescheduleDateTime) return;
    setRescheduling(true);
    try {
      const res = await fetch(`http://localhost:8000/publications/${rescheduleEvent.id}/reschedule`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scheduled_at: new Date(rescheduleDateTime).toISOString() }),
      });
      if (res.ok) {
        setRescheduleEvent(null);
        await loadData();
      } else {
        alert("Erreur lors de la replanification.");
      }
    } catch (e) {
      console.error(e);
      alert("Erreur réseau.");
    } finally {
      setRescheduling(false);
    }
  };

  // Publier immédiatement
  const handlePublishNow = async (pubId: string) => {
    if (!confirm("Voulez-vous publier ce clip immédiatement ?")) return;
    setPublishingId(pubId);
    try {
      const res = await fetch(`http://localhost:8000/publications/${pubId}/publish-now`, {
        method: "POST",
      });
      if (res.ok) {
        await loadData();
      } else {
        const err = await res.json();
        alert(err.detail || "Erreur lors de la publication.");
      }
    } catch (e) {
      console.error(e);
      alert("Erreur lors de la publication.");
    } finally {
      setPublishingId(null);
    }
  };

  // Supprimer une publication
  const handleDeletePub = async (pubId: string) => {
    if (!confirm("Supprimer cette programmation ?")) return;
    try {
      const res = await fetch(`http://localhost:8000/publications/${pubId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        await loadData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Suggérer créneau pour un seul clip
  const handleSuggestSingle = async (clipId: string) => {
    try {
      const res = await fetch(`http://localhost:8000/clips/${clipId}/predict-slots`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        if (data.predictions && data.predictions.length > 0) {
          setPredictions(data.predictions);
          setPredictionSummary(data.summary || "");
          setSelectedClipIds([clipId]);
          setPredictModalOpen(true);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const scheduledCount = events.filter((e) => e.status === "scheduled").length;
  const publishedCount = events.filter((e) => e.status === "published").length;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-8">
      {/* En-tête de la page */}
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-purple-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-purple-900/30">
                <CalendarIcon className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                  Calendrier de Publication Prédictif
                  <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20 flex items-center gap-1">
                    <Sparkles className="h-3 w-3" /> IA Gemini
                  </span>
                </h1>
                <p className="text-sm text-slate-400">
                  Planification algorithmique intelligente calculée sur les pics d'engagement et la rétention d'audience.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                setSelectedClipIds(unscheduled.map((c) => c.id));
                setPredictions([]);
                setPredictModalOpen(true);
              }}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-500 hover:from-purple-500 hover:to-indigo-500 text-white font-medium shadow-lg shadow-purple-900/40 transition active:scale-95"
            >
              <Sparkles className="h-4 w-4" />
              <span>Planification IA Prédictive</span>
            </button>
            <button
              onClick={loadData}
              className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition"
              title="Rafraîchir"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Barre de navigation & filtres */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
          {/* Navigation semaine */}
          <div className="flex items-center gap-2 bg-slate-900/80 border border-slate-800 rounded-xl p-1.5 w-fit">
            <button
              onClick={() => setWeekOffset((prev) => prev - 1)}
              className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
              title="Semaine précédente"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              onClick={() => setWeekOffset(0)}
              className="px-3 py-1 text-xs font-medium rounded-lg hover:bg-slate-800 text-slate-300 hover:text-white transition"
            >
              Aujourd'hui
            </button>
            <button
              onClick={() => setWeekOffset((prev) => prev + 1)}
              className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
              title="Semaine suivante"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
            <span className="text-xs font-semibold text-slate-300 px-3">
              {formatDateShort(weekStart)} — {formatDateShort(weekEnd)}
            </span>
          </div>

          {/* Filtres de plateforme */}
          <div className="flex items-center gap-1.5 bg-slate-900/80 border border-slate-800 rounded-xl p-1 justify-center">
            {["all", "youtube", "tiktok", "instagram"].map((p) => (
              <button
                key={p}
                onClick={() => setPlatformFilter(p)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  platformFilter === p
                    ? "bg-purple-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                }`}
              >
                {p === "all" ? "Toutes" : p === "youtube" ? "YouTube Shorts" : p === "tiktok" ? "TikTok" : "Instagram"}
              </button>
            ))}
          </div>

          {/* Statistiques rapides */}
          <div className="flex items-center gap-3 justify-end text-xs">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 font-medium">
              <Clock className="h-3.5 w-3.5" />
              <span>{scheduledCount} planifiés</span>
            </div>
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-medium">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>{publishedCount} publiés</span>
            </div>
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-400 font-medium">
              <Layers className="h-3.5 w-3.5" />
              <span>{unscheduled.length} en attente</span>
            </div>
          </div>
        </div>

        {/* Grille principale : File d'attente à gauche + Vue Semaine à droite */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Colonne latérale : File d'attente des clips prêts */}
          <div className="lg:col-span-1 space-y-4">
            <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <Layers className="h-4 w-4 text-purple-400" />
                  File d'attente IA
                </h2>
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-semibold">
                  {unscheduled.length} prêts
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Clips montés et prêts, en attente d'attribution d'un créneau stratégique.
              </p>

              {unscheduled.length === 0 ? (
                <div className="py-8 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl">
                  Tous les clips sont programmés ou publiés ! 🎉
                </div>
              ) : (
                <div className="space-y-3 max-h-[700px] overflow-y-auto pr-1">
                  {unscheduled.map((clip) => {
                    const hookScore = (clip.scores && clip.scores.hook) || 8.0;
                    return (
                      <div
                        key={clip.id}
                        className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 hover:border-purple-500/40 transition group space-y-2.5"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <h3 className="text-xs font-semibold text-white truncate" title={clip.title}>
                              {clip.title || `Clip #${clip.index}`}
                            </h3>
                            <p className="text-[11px] text-slate-400 truncate mt-0.5" title={clip.hook}>
                              🎯 {clip.hook || "Accroche captivante"}
                            </p>
                          </div>
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20 whitespace-nowrap">
                            {clip.duration}s
                          </span>
                        </div>

                        <div className="flex items-center justify-between text-[11px] pt-1 border-t border-slate-800/60">
                          <span className="text-amber-400 font-medium flex items-center gap-1">
                            <Flame className="h-3 w-3" /> Potentiel {hookScore}/10
                          </span>
                          <button
                            onClick={() => handleSuggestSingle(clip.id)}
                            className="text-purple-400 hover:text-purple-300 font-medium flex items-center gap-1 transition"
                            title="Lancer l'analyse prédictive pour ce clip"
                          >
                            <Sparkles className="h-3 w-3" /> Suggérer
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Calendrier Semaine (7 Colonnes) */}
          <div className="lg:col-span-3">
            <div className="grid grid-cols-1 md:grid-cols-7 gap-3">
              {weekDays.map((dayDate, idx) => {
                const dayIndex = idx; // 0 = Lundi, 6 = Dimanche
                const dayEvents = filteredEvents.filter((ev) => isSameDay(dayDate, ev.scheduled_at || ev.published_at));
                const today = isToday(dayDate);
                const peaks = PEAK_HOURS[dayIndex] || [];

                return (
                  <div
                    key={idx}
                    className={`rounded-2xl border p-3 flex flex-col min-h-[580px] transition ${
                      today
                        ? "bg-purple-950/20 border-purple-500/40 shadow-md shadow-purple-900/10"
                        : "bg-slate-900/50 border-slate-800/80 hover:border-slate-700/80"
                    }`}
                  >
                    {/* Entête du jour */}
                    <div className="border-b border-slate-800 pb-2 mb-2 flex items-center justify-between">
                      <div>
                        <span className="text-xs font-bold text-slate-300">{FRENCH_DAYS[dayIndex]}</span>
                        <div className="text-sm font-extrabold text-white">{dayDate.getDate()}</div>
                      </div>
                      {today && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/40">
                          Aujourd'hui
                        </span>
                      )}
                    </div>

                    {/* Indicateurs de Pics Algorithmiques */}
                    <div className="space-y-1 mb-3">
                      {peaks.map((p, pIdx) => (
                        <div
                          key={pIdx}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800/50 text-slate-400 border border-slate-800 flex items-center justify-between"
                          title={`Créneau algorithmique optimal : ${p.label}`}
                        >
                          <span className="truncate">
                            {p.badge} {p.time}
                          </span>
                        </div>
                      ))}
                    </div>

                    {/* Liste des cartes publiées ou planifiées du jour */}
                    <div className="flex-1 space-y-2.5 overflow-y-auto">
                      {dayEvents.length === 0 ? (
                        <div className="h-full flex items-center justify-center text-center p-3 text-[11px] text-slate-600 border border-dashed border-slate-800/60 rounded-xl">
                          Aucun clip
                        </div>
                      ) : (
                        dayEvents.map((ev) => {
                          const dateObj = new Date(ev.scheduled_at || ev.published_at || "");
                          const timeStr = dateObj.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
                          const isPublished = ev.status === "published";
                          const isUploading = ev.status === "uploading";
                          const isFailed = ev.status === "failed";
                          const predScore = ev.metadata?.predictive_score || 92;

                          return (
                            <div
                              key={ev.id}
                              className={`p-2.5 rounded-xl border text-xs space-y-2 transition shadow-sm ${
                                isPublished
                                  ? "bg-emerald-950/30 border-emerald-500/30 text-emerald-200"
                                  : isUploading
                                  ? "bg-blue-950/30 border-blue-500/30 text-blue-200 animate-pulse"
                                  : isFailed
                                  ? "bg-rose-950/30 border-rose-500/30 text-rose-200"
                                  : "bg-slate-950/80 border-slate-800 text-slate-200 hover:border-purple-500/50"
                              }`}
                            >
                              {/* Ligne Plateforme & Heure */}
                              <div className="flex items-center justify-between">
                                <span className="font-bold flex items-center gap-1 text-[11px]">
                                  {ev.platform === "youtube" ? (
                                    <span className="text-red-400">🔴 Shorts</span>
                                  ) : ev.platform === "tiktok" ? (
                                    <span className="text-cyan-400">🎵 TikTok</span>
                                  ) : (
                                    <span className="text-pink-400">📸 Reels</span>
                                  )}
                                </span>
                                <span className="font-mono text-[11px] bg-slate-900 px-1.5 py-0.5 rounded text-white font-semibold">
                                  {timeStr}
                                </span>
                              </div>

                              {/* Titre & Hook */}
                              <div>
                                <h4 className="font-semibold text-white line-clamp-2 leading-tight" title={ev.metadata?.title || ev.clip_title || "Clip"}>
                                  {ev.metadata?.title || ev.clip_title || "Clip"}
                                </h4>
                                {ev.clip_hook && (
                                  <p className="text-[10px] text-slate-400 line-clamp-1 mt-0.5">
                                    "{ev.clip_hook}"
                                  </p>
                                )}
                              </div>

                              {/* Badge Score Prédictif IA */}
                              {ev.metadata?.algorithmic_reason && (
                                <button
                                  onClick={() => setReasonModalEvent(ev)}
                                  className="w-full text-[10px] font-semibold px-2 py-1 rounded bg-purple-500/10 text-purple-300 hover:bg-purple-500/20 border border-purple-500/20 flex items-center justify-between transition"
                                >
                                  <span className="flex items-center gap-1">
                                    <Sparkles className="h-3 w-3 text-purple-400" /> Score IA {predScore}%
                                  </span>
                                  <Info className="h-3 w-3" />
                                </button>
                              )}

                              {/* Statut & Actions */}
                              <div className="pt-1.5 border-t border-slate-800/80 flex items-center justify-between text-[11px]">
                                {isPublished ? (
                                  <a
                                    href={ev.url || "#"}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="text-emerald-400 hover:underline flex items-center gap-1 font-semibold"
                                  >
                                    <CheckCircle2 className="h-3 w-3" /> Voir
                                    <ExternalLink className="h-2.5 w-2.5" />
                                  </a>
                                ) : isUploading ? (
                                  <span className="text-blue-400 font-medium">Envoi...</span>
                                ) : (
                                  <div className="flex items-center gap-1.5 w-full justify-between">
                                    <button
                                      onClick={() => handlePublishNow(ev.id)}
                                      disabled={publishingId === ev.id}
                                      className="text-amber-400 hover:text-amber-300 font-medium flex items-center gap-1"
                                      title="Publier immédiatement sans attendre"
                                    >
                                      <Send className="h-3 w-3" /> Envoyer
                                    </button>
                                    <div className="flex items-center gap-1">
                                      <button
                                        onClick={() => {
                                          setRescheduleEvent(ev);
                                          setRescheduleDateTime(
                                            ev.scheduled_at ? new Date(ev.scheduled_at).toISOString().slice(0, 16) : ""
                                          );
                                        }}
                                        className="text-slate-400 hover:text-white p-1"
                                        title="Déplacer / Replanifier"
                                      >
                                        <Clock className="h-3 w-3" />
                                      </button>
                                      <button
                                        onClick={() => handleDeletePub(ev.id)}
                                        className="text-slate-400 hover:text-rose-400 p-1"
                                        title="Supprimer"
                                      >
                                        <Trash2 className="h-3 w-3" />
                                      </button>
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* MODAL PLANIFICATION IA PRÉDICTIVE */}
      {predictModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-3xl w-full p-6 shadow-2xl space-y-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-purple-400" />
                  Planificateur Prédictif IA Gemini
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Gemini étudie le ton, l'accroche, la durée et la rétention de vos clips pour les assigner aux meilleurs créneaux algorithmiques sans collision.
                </p>
              </div>
              <button
                onClick={() => setPredictModalOpen(false)}
                className="text-slate-400 hover:text-white text-lg p-1"
              >
                ✕
              </button>
            </div>

            {/* Étape 1 : Paramètres */}
            {predictions.length === 0 && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                      Plateforme cible
                    </label>
                    <select
                      value={targetPlatform}
                      onChange={(e) => setTargetPlatform(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white"
                    >
                      <option value="youtube">YouTube Shorts</option>
                      <option value="tiktok">TikTok</option>
                      <option value="instagram">Instagram Reels</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                      Compte de publication
                    </label>
                    <select
                      value={targetAccountId}
                      onChange={(e) => setTargetAccountId(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white"
                    >
                      {accounts.map((acc) => (
                        <option key={acc.id} value={acc.id}>
                          {acc.name} ({acc.platform})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-xs font-semibold text-slate-300">
                      Clips à intégrer dans la planification ({selectedClipIds.length}/{unscheduled.length})
                    </label>
                    <button
                      onClick={() => {
                        if (selectedClipIds.length === unscheduled.length) setSelectedClipIds([]);
                        else setSelectedClipIds(unscheduled.map((c) => c.id));
                      }}
                      className="text-[11px] text-purple-400 hover:underline"
                    >
                      {selectedClipIds.length === unscheduled.length ? "Tout désélectionner" : "Tout sélectionner"}
                    </button>
                  </div>

                  <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                    {unscheduled.map((clip) => (
                      <label
                        key={clip.id}
                        className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800/80 hover:border-slate-700 cursor-pointer text-xs"
                      >
                        <div className="flex items-center gap-2.5">
                          <input
                            type="checkbox"
                            checked={selectedClipIds.includes(clip.id)}
                            onChange={(e) => {
                              if (e.target.checked) setSelectedClipIds([...selectedClipIds, clip.id]);
                              else setSelectedClipIds(selectedClipIds.filter((id) => id !== clip.id));
                            }}
                            className="rounded border-slate-700 text-purple-600 focus:ring-purple-500"
                          />
                          <div>
                            <span className="font-semibold text-white block">{clip.title}</span>
                            <span className="text-[10px] text-slate-400">"{clip.hook}"</span>
                          </div>
                        </div>
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                          {clip.duration}s
                        </span>
                      </label>
                    ))}
                  </div>
                </div>

                <div className="pt-4 flex justify-end">
                  <button
                    onClick={handleRunAiPrediction}
                    disabled={predictLoading || selectedClipIds.length === 0}
                    className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold text-xs shadow-lg shadow-purple-900/40 transition disabled:opacity-50"
                  >
                    {predictLoading ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin" />
                        <span>Analyse algorithmique en cours...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4" />
                        <span>Calculer la planification optimale</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* Étape 2 : Résultats de la prédiction */}
            {predictions.length > 0 && (
              <div className="space-y-4">
                {predictionSummary && (
                  <div className="p-3.5 rounded-xl bg-purple-950/30 border border-purple-500/30 text-purple-200 text-xs">
                    <span className="font-bold flex items-center gap-1.5 mb-1">
                      <Sparkles className="h-3.5 w-3.5" /> Recommandation Stratégique Gemini :
                    </span>
                    {predictionSummary}
                  </div>
                )}

                <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
                  {predictions.map((p, idx) => {
                    const dt = new Date(p.suggested_time);
                    const dateFormatted = dt.toLocaleDateString("fr-FR", {
                      weekday: "long",
                      day: "numeric",
                      month: "long",
                    });
                    const timeFormatted = dt.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });

                    return (
                      <div
                        key={idx}
                        className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2 text-xs"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <span className="font-bold text-white text-sm block">
                              {p.viral_title || p.clip_title}
                            </span>
                            <span className="text-[11px] text-purple-400 font-medium">
                              📅 {dateFormatted} à {timeFormatted} — {p.slot_name}
                            </span>
                          </div>
                          <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold text-xs whitespace-nowrap">
                            Score IA {p.predictive_score}%
                          </span>
                        </div>

                        <p className="text-[11px] text-slate-300 leading-relaxed bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/80">
                          <strong className="text-purple-300">Raisonnement algorithmique : </strong>
                          {p.algorithmic_reason}
                        </p>
                      </div>
                    );
                  })}
                </div>

                {/* Validation obligatoire des droits */}
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer text-xs">
                    <input
                      type="checkbox"
                      checked={rightsConfirmed}
                      onChange={(e) => setRightsConfirmed(e.target.checked)}
                      className="rounded border-slate-700 text-purple-600 focus:ring-purple-500"
                    />
                    <span className="font-semibold text-slate-200">
                      J'atteste détenir les droits d'exploitation et de diffusion sur l'ensemble de ces clips (Requis)
                    </span>
                  </label>
                </div>

                <div className="flex items-center justify-between pt-2">
                  <button
                    onClick={() => setPredictions([])}
                    className="text-xs text-slate-400 hover:text-white"
                  >
                    ← Modifier la sélection
                  </button>
                  <button
                    onClick={handleApplySchedule}
                    disabled={!rightsConfirmed || applying}
                    className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow-lg shadow-emerald-900/40 transition disabled:opacity-50"
                  >
                    {applying ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin" />
                        <span>Enregistrement...</span>
                      </>
                    ) : (
                      <>
                        <CalendarCheck className="h-4 w-4" />
                        <span>Valider et Programmer ({predictions.length} clips)</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* MODAL EXPLICATION RAISONNEMENT ALGORITHMIQUE */}
      {reasonModalEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-start justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-purple-400" />
                Pourquoi ce créneau ?
              </h3>
              <button
                onClick={() => setReasonModalEvent(null)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <span className="text-slate-400 block mb-0.5">Titre du clip :</span>
                <span className="font-semibold text-white">
                  {reasonModalEvent.metadata?.title || reasonModalEvent.clip_title}
                </span>
              </div>

              <div>
                <span className="text-slate-400 block mb-0.5">Date et heure programmée :</span>
                <span className="font-mono text-purple-300">
                  {reasonModalEvent.scheduled_at && new Date(reasonModalEvent.scheduled_at).toLocaleString("fr-FR")}
                </span>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-purple-300">Analyse de l'IA :</span>
                  <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/20">
                    Score {reasonModalEvent.metadata?.predictive_score || 92}%
                  </span>
                </div>
                <p className="text-slate-200 leading-relaxed">
                  {reasonModalEvent.metadata?.algorithmic_reason || "Créneau à forte audience statistique."}
                </p>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setReasonModalEvent(null)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-white transition"
              >
                Fermer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL REPLANIFIER */}
      {rescheduleEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-start justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Clock className="h-4 w-4 text-purple-400" />
                Déplacer la publication
              </h3>
              <button
                onClick={() => setRescheduleEvent(null)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <p className="text-slate-400">
                Modifier la date et l'heure pour le clip :{" "}
                <strong className="text-white">
                  {rescheduleEvent.metadata?.title || rescheduleEvent.clip_title}
                </strong>
              </p>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">
                  Nouvelle date & heure (Europe/Paris)
                </label>
                <input
                  type="datetime-local"
                  value={rescheduleDateTime}
                  onChange={(e) => setRescheduleDateTime(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white text-xs"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setRescheduleEvent(null)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 transition"
              >
                Annuler
              </button>
              <button
                onClick={handleRescheduleSubmit}
                disabled={rescheduling || !rescheduleDateTime}
                className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-xs font-semibold text-white transition disabled:opacity-50"
              >
                {rescheduling ? "Modification..." : "Confirmer"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
