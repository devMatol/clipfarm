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
  List,
  Grid3X3,
  PanelLeftClose,
  PanelLeftOpen,
  Eye,
  Copy,
  Check,
} from "lucide-react";

interface CalendarEvent {
  id: string;
  clip_id: string;
  project_id: string | null;
  project_title: string | null;
  clip_title: string | null;
  clip_hook: string | null;
  clip_duration: number;
  thumbnail_url?: string | null;
  video_url?: string | null;
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
  thumbnail_url?: string | null;
  video_url?: string | null;
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

const PEAK_HOURS: Record<number, { label: string; time: string; badge: string }> = {
  0: { label: "Pause Déjeuner", time: "12:30", badge: "🥪" },
  1: { label: "Fin de Journée", time: "18:15", badge: "🎯" },
  2: { label: "Grand Pic Mercredi", time: "18:30", badge: "🚀" },
  3: { label: "Haute Rétention", time: "18:30", badge: "📈" },
  4: { label: "Début Weekend", time: "19:00", badge: "🎉" },
  5: { label: "Samedi Détente", time: "18:45", badge: "🎮" },
  6: { label: "Grand Record Hebdo", time: "18:45", badge: "👑" },
};

const FRENCH_DAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"];

export default function CalendarPage() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [unscheduled, setUnscheduled] = useState<UnscheduledClip[]>([]);
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [weekOffset, setWeekOffset] = useState(0);
  const [platformFilter, setPlatformFilter] = useState("all");
  const [viewMode, setViewMode] = useState<"calendar" | "list">("calendar");
  const [showQueue, setShowQueue] = useState(true);

  // Modals
  const [predictModalOpen, setPredictModalOpen] = useState(false);
  const [predictLoading, setPredictLoading] = useState(false);
  const [predictions, setPredictions] = useState<PredictionItem[]>([]);
  const [predictionSummary, setPredictionSummary] = useState("");
  const [selectedClipIds, setSelectedClipIds] = useState<string[]>([]);
  const [targetPlatform, setTargetPlatform] = useState("youtube");
  const [targetAccountId, setTargetAccountId] = useState("");
  const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [applying, setApplying] = useState(false);

  // Modal Détails / Raisonnement
  const [detailModalEvent, setDetailModalEvent] = useState<CalendarEvent | null>(null);
  const [copiedText, setCopiedText] = useState(false);

  // Modal Replanification
  const [rescheduleEvent, setRescheduleEvent] = useState<CalendarEvent | null>(null);
  const [rescheduleDateTime, setRescheduleDateTime] = useState("");
  const [rescheduling, setRescheduling] = useState(false);

  // Publication en cours
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

  const getWeekDates = (offset: number) => {
    const now = new Date();
    const currentDay = now.getDay();
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

  const filteredEvents = events.filter((e) => {
    if (platformFilter !== "all" && e.platform !== platformFilter) return false;
    return true;
  });

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

  const handleCopyText = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(true);
    setTimeout(() => setCopiedText(false), 2000);
  };

  return (
    <div className="w-full space-y-6">
        {/* HEADER PRINCIPAL */}
        <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-4 bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl p-5 rounded-2xl shadow-xl">
          <div className="flex items-center gap-3.5">
            <div className="h-11 w-11 rounded-2xl bg-gradient-to-tr from-purple-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-purple-900/40 shrink-0">
              <CalendarIcon className="h-6 w-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
                  Calendrier de Publication Prédictif
                </h1>
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20 flex items-center gap-1 shadow-sm">
                  <Sparkles className="h-3 w-3" /> IA Gemini 2.5 Flash
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Optimisation algorithmique basée sur les heures de pointe en France (pics d'audience, rétention maximale et hook rate).
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            {/* Compteurs de synthèse */}
            <div className="hidden sm:flex items-center gap-2 text-xs mr-2">
              <span className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 font-semibold">
                <Clock className="h-3.5 w-3.5" /> {scheduledCount} planifiés
              </span>
              <span className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-semibold">
                <CheckCircle2 className="h-3.5 w-3.5" /> {publishedCount} publiés
              </span>
              <span className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400 font-semibold">
                <Layers className="h-3.5 w-3.5" /> {unscheduled.length} prêts
              </span>
            </div>

            {/* Bouton Toggle File d'attente */}
            <button
              onClick={() => setShowQueue(!showQueue)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold border transition ${
                showQueue
                  ? "bg-slate-800 text-purple-300 border-purple-500/40"
                  : "bg-slate-900 text-slate-300 border-slate-800 hover:bg-slate-800"
              }`}
              title={showQueue ? "Masquer la file d'attente" : "Afficher la file d'attente"}
            >
              {showQueue ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
              <span>File ({unscheduled.length})</span>
            </button>

            {/* Bouton IA Prédictive */}
            <button
              onClick={() => {
                setSelectedClipIds(unscheduled.map((c) => c.id));
                setPredictions([]);
                setPredictModalOpen(true);
              }}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-500 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold text-xs shadow-lg shadow-purple-900/40 transition active:scale-95"
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>Planifier avec l'IA</span>
            </button>

            <button
              onClick={loadData}
              className="p-2 rounded-xl bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition"
              title="Rafraîchir"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* BARRE D'OUTILS ET NAVIGATION SEMAINE */}
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-slate-900/40 border border-slate-800/80 p-2.5 rounded-2xl">
          {/* Navigation semaine */}
          <div className="flex items-center gap-2">
            <div className="flex items-center bg-slate-900 border border-slate-800 rounded-xl p-1">
              <button
                onClick={() => setWeekOffset((prev) => prev - 1)}
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
                title="Semaine précédente"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                onClick={() => setWeekOffset(0)}
                className="px-3 py-1 text-xs font-semibold rounded-lg hover:bg-slate-800 text-slate-300 hover:text-white transition"
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
            </div>

            <span className="text-xs font-bold text-slate-200 px-3 py-1.5 rounded-xl bg-slate-900/80 border border-slate-800">
              {formatDateShort(weekStart)} — {formatDateShort(weekEnd)}
            </span>
          </div>

          {/* Filtres Plateforme & Sélecteur de Vue */}
          <div className="flex items-center justify-between md:justify-end gap-3">
            {/* Filtre Plateformes */}
            <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 rounded-xl p-1">
              {[
                { id: "all", label: "Tout" },
                { id: "youtube", label: "🔴 Shorts" },
                { id: "tiktok", label: "🎵 TikTok" },
                { id: "instagram", label: "📸 Reels" },
              ].map((p) => (
                <button
                  key={p.id}
                  onClick={() => setPlatformFilter(p.id)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
                    platformFilter === p.id
                      ? "bg-purple-600 text-white shadow-sm font-semibold"
                      : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>

            {/* Switch Vue Calendrier vs Liste */}
            <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 rounded-xl p-1">
              <button
                onClick={() => setViewMode("calendar")}
                className={`flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-medium transition ${
                  viewMode === "calendar"
                    ? "bg-purple-600 text-white font-semibold shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
                title="Vue grille hebdomadaire"
              >
                <Grid3X3 className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Semaine</span>
              </button>
              <button
                onClick={() => setViewMode("list")}
                className={`flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-medium transition ${
                  viewMode === "list"
                    ? "bg-purple-600 text-white font-semibold shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
                title="Vue flux chronologique"
              >
                <List className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Flux</span>
              </button>
            </div>
          </div>
        </div>

        {/* CONTENU PRINCIPAL : LAYOUT FLEXIBLE */}
        <div className="flex flex-col lg:flex-row gap-5 items-start">
          {/* PANNEAU LATÉRAL : FILE D'ATTENTE DES CLIPS PRÊTS */}
          {showQueue && (
            <div className="w-full lg:w-80 shrink-0 bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl rounded-2xl p-4 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center gap-2">
                  <Layers className="h-4 w-4 text-purple-400" />
                  <h2 className="text-xs font-bold text-white uppercase tracking-wider">
                    File d'attente ({unscheduled.length})
                  </h2>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20">
                  Prêts
                </span>
              </div>

              {unscheduled.length === 0 ? (
                <div className="py-12 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl">
                  Tous vos clips sont programmés ! 🎉
                </div>
              ) : (
                <div className="space-y-3 max-h-[750px] overflow-y-auto pr-1">
                  {unscheduled.map((clip) => {
                    const hookScore = (clip.scores && clip.scores.hook) || 8.0;
                    return (
                      <div
                        key={clip.id}
                        className="p-3 rounded-xl bg-slate-950/80 border border-slate-800/90 hover:border-purple-500/40 transition group space-y-2.5 shadow-sm"
                      >
                        {/* Miniature si disponible */}
                        {clip.thumbnail_url && (
                          <div className="relative aspect-video rounded-lg overflow-hidden bg-slate-900 border border-slate-800">
                            <img
                              src={clip.thumbnail_url}
                              alt={clip.title}
                              className="w-full h-full object-cover group-hover:scale-105 transition duration-300"
                            />
                            <span className="absolute bottom-1 right-1 px-1.5 py-0.5 rounded bg-black/80 text-[9px] font-mono font-bold text-white">
                              {clip.duration}s
                            </span>
                          </div>
                        )}

                        <div className="min-w-0">
                          <h3 className="text-xs font-bold text-white line-clamp-1" title={clip.title}>
                            {clip.title || `Clip #${clip.index}`}
                          </h3>
                          <p className="text-[11px] text-slate-400 line-clamp-1 mt-0.5" title={clip.hook}>
                            🎯 {clip.hook || "Accroche captivante"}
                          </p>
                        </div>

                        <div className="flex items-center justify-between text-[11px] pt-1.5 border-t border-slate-800/60">
                          <span className="text-amber-400 font-semibold flex items-center gap-1 text-[10px]">
                            <Flame className="h-3 w-3" /> Potentiel {hookScore}/10
                          </span>
                          <button
                            onClick={() => handleSuggestSingle(clip.id)}
                            className="px-2 py-1 rounded-lg bg-purple-600/20 hover:bg-purple-600/40 text-purple-300 hover:text-white text-[10px] font-semibold flex items-center gap-1 border border-purple-500/30 transition"
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
          )}

          {/* CALENDRIER / FLUX PRINCIPAL */}
          <div className="flex-1 min-w-0 w-full">
            {viewMode === "calendar" ? (
              /* VUE SEMAINE (7 COLONNES) */
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-7 gap-3">
                {weekDays.map((dayDate, idx) => {
                  const dayIndex = idx;
                  const dayEvents = filteredEvents.filter((ev) =>
                    isSameDay(dayDate, ev.scheduled_at || ev.published_at)
                  );
                  const today = isToday(dayDate);
                  const peak = PEAK_HOURS[dayIndex];

                  return (
                    <div
                      key={idx}
                      className={`rounded-2xl border flex flex-col min-h-[620px] transition shadow-md ${
                        today
                          ? "bg-slate-900/90 border-purple-500/60 ring-1 ring-purple-500/40"
                          : "bg-slate-900/40 border-slate-800/80 hover:border-slate-700"
                      }`}
                    >
                      {/* EN-TÊTE DU JOUR */}
                      <div className={`p-3 border-b ${today ? "border-purple-500/30 bg-purple-950/20" : "border-slate-800/80 bg-slate-900/60"} rounded-t-2xl`}>
                        <div className="flex items-center justify-between">
                          <div>
                            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                              {FRENCH_DAYS[dayIndex]}
                            </span>
                            <div className="text-lg font-black text-white leading-none mt-0.5">
                              {dayDate.getDate()}
                            </div>
                          </div>
                          {today ? (
                            <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/40 flex items-center gap-1">
                              <span className="h-1.5 w-1.5 rounded-full bg-purple-400 animate-pulse" />
                              Aujourd'hui
                            </span>
                          ) : (
                            dayEvents.length > 0 && (
                              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-300">
                                {dayEvents.length}
                              </span>
                            )
                          )}
                        </div>

                        {/* Indication discrète du pic d'audience du jour */}
                        {peak && (
                          <div className="mt-2 text-[10px] font-medium text-purple-300/80 flex items-center justify-between bg-slate-950/60 px-2 py-1 rounded-lg border border-slate-800/60">
                            <span className="truncate">{peak.badge} {peak.label}</span>
                            <span className="font-mono font-bold text-white shrink-0 ml-1">{peak.time}</span>
                          </div>
                        )}
                      </div>

                      {/* ÉVÉNEMENTS DU JOUR */}
                      <div className="p-2.5 flex-1 space-y-3 overflow-y-auto">
                        {dayEvents.length === 0 ? (
                          <div className="h-44 flex flex-col items-center justify-center text-center p-3 text-[11px] text-slate-600 border border-dashed border-slate-800/60 rounded-xl">
                            <span>Aucun clip</span>
                            <span className="text-[10px] text-slate-700 mt-1">Créneau libre</span>
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
                                className={`rounded-xl border p-2.5 space-y-2 transition shadow-lg group hover:border-purple-500/50 ${
                                  isPublished
                                    ? "bg-emerald-950/20 border-emerald-500/30"
                                    : isUploading
                                    ? "bg-blue-950/20 border-blue-500/30 animate-pulse"
                                    : isFailed
                                    ? "bg-rose-950/20 border-rose-500/30"
                                    : "bg-slate-950/90 border-slate-800/90"
                                }`}
                              >
                                {/* Ligne supérieure : Plateforme + Heure + Score */}
                                <div className="flex items-center justify-between text-[10px]">
                                  <span className="font-bold flex items-center gap-1">
                                    {ev.platform === "youtube" ? (
                                      <span className="text-red-400">🔴 Shorts</span>
                                    ) : ev.platform === "tiktok" ? (
                                      <span className="text-cyan-400">🎵 TikTok</span>
                                    ) : (
                                      <span className="text-pink-400">📸 Reels</span>
                                    )}
                                  </span>

                                  <div className="flex items-center gap-1.5">
                                    <span className="font-mono text-white font-bold bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">
                                      {timeStr}
                                    </span>
                                    <span
                                      className="font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.5 rounded"
                                      title={`Score prédictif algorithmique : ${predScore}%`}
                                    >
                                      🔥 {predScore}%
                                    </span>
                                  </div>
                                </div>

                                {/* Aperçu Miniature si présente */}
                                {ev.thumbnail_url && (
                                  <div
                                    onClick={() => setDetailModalEvent(ev)}
                                    className="relative aspect-video rounded-lg overflow-hidden bg-slate-900 border border-slate-800/80 cursor-pointer"
                                  >
                                    <img
                                      src={ev.thumbnail_url}
                                      alt={ev.metadata?.title || ev.clip_title || "Clip"}
                                      className="w-full h-full object-cover group-hover:scale-105 transition duration-300"
                                    />
                                    <div className="absolute inset-0 bg-black/30 group-hover:bg-black/10 transition flex items-center justify-center">
                                      <Play className="h-6 w-6 text-white/90 drop-shadow-md" />
                                    </div>
                                    <span className="absolute bottom-1 right-1 px-1.5 py-0.2 rounded bg-black/80 text-[9px] font-mono font-bold text-white">
                                      {ev.clip_duration}s
                                    </span>
                                  </div>
                                )}

                                {/* Titre du clip */}
                                <div>
                                  <h4
                                    onClick={() => setDetailModalEvent(ev)}
                                    className="text-xs font-bold text-white line-clamp-2 leading-snug cursor-pointer hover:text-purple-300 transition"
                                    title={ev.metadata?.title || ev.clip_title || "Clip"}
                                  >
                                    {ev.metadata?.title || ev.clip_title || "Clip"}
                                  </h4>
                                  {ev.account_name && (
                                    <p className="text-[10px] text-slate-400 mt-0.5 truncate">
                                      👤 {ev.account_name}
                                    </p>
                                  )}
                                </div>

                                {/* Actions rapides */}
                                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px]">
                                  {isPublished ? (
                                    <a
                                      href={ev.url || "#"}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="text-emerald-400 hover:underline flex items-center gap-1 font-semibold text-[10px]"
                                    >
                                      <CheckCircle2 className="h-3 w-3" /> En ligne
                                      <ExternalLink className="h-2.5 w-2.5" />
                                    </a>
                                  ) : isUploading ? (
                                    <span className="text-blue-400 font-medium text-[10px]">Publication...</span>
                                  ) : (
                                    <>
                                      <button
                                        onClick={() => handlePublishNow(ev.id)}
                                        disabled={publishingId === ev.id}
                                        className="text-amber-400 hover:text-amber-300 font-semibold flex items-center gap-1 text-[10px]"
                                        title="Publier immédiatement"
                                      >
                                        <Send className="h-3 w-3" /> Publier
                                      </button>
                                      <div className="flex items-center gap-1 text-slate-400">
                                        <button
                                          onClick={() => {
                                            setRescheduleEvent(ev);
                                            setRescheduleDateTime(
                                              ev.scheduled_at ? new Date(ev.scheduled_at).toISOString().slice(0, 16) : ""
                                            );
                                          }}
                                          className="hover:text-white p-1 rounded hover:bg-slate-800 transition"
                                          title="Replanifier"
                                        >
                                          <Clock className="h-3 w-3" />
                                        </button>
                                        <button
                                          onClick={() => handleDeletePub(ev.id)}
                                          className="hover:text-rose-400 p-1 rounded hover:bg-slate-800 transition"
                                          title="Supprimer"
                                        >
                                          <Trash2 className="h-3 w-3" />
                                        </button>
                                      </div>
                                    </>
                                  )}
                                </div>
                              </div>
                            );
                          })
                        )}

                        {/* Dropzone d'invitation à planifier au pic */}
                        {peak && (
                          <button
                            onClick={() => {
                              setSelectedClipIds(unscheduled.map((c) => c.id));
                              setPredictModalOpen(true);
                            }}
                            className="w-full py-2.5 px-2 rounded-xl border border-dashed border-slate-800 hover:border-purple-500/50 text-[10px] font-semibold text-slate-400 hover:text-purple-300 transition flex items-center justify-center gap-1 bg-slate-950/30 group"
                          >
                            <Sparkles className="h-3 w-3 text-purple-400 group-hover:scale-110 transition" />
                            <span>+ Planifier ({peak.time})</span>
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              /* VUE FLUX CHRONOLOGIQUE (AGENDA NOTION/BUFFER STYLE) */
              <div className="space-y-4">
                {filteredEvents.length === 0 ? (
                  <div className="p-12 text-center text-slate-500 bg-slate-900/40 border border-slate-800 rounded-2xl">
                    Aucune publication programmée pour l'instant.
                  </div>
                ) : (
                  filteredEvents.map((ev) => {
                    const dt = new Date(ev.scheduled_at || ev.published_at || "");
                    const dateFormatted = dt.toLocaleDateString("fr-FR", {
                      weekday: "long",
                      day: "numeric",
                      month: "long",
                    });
                    const timeStr = dt.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
                    const isPublished = ev.status === "published";
                    const predScore = ev.metadata?.predictive_score || 92;

                    return (
                      <div
                        key={ev.id}
                        className="p-4 rounded-2xl bg-slate-900/70 border border-slate-800 hover:border-purple-500/40 transition flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-xl"
                      >
                        <div className="flex items-start gap-4 flex-1 min-w-0">
                          {/* Miniature Vidéo */}
                          {ev.thumbnail_url ? (
                            <div
                              onClick={() => setDetailModalEvent(ev)}
                              className="relative w-36 aspect-video rounded-xl overflow-hidden bg-slate-950 border border-slate-800 shrink-0 cursor-pointer group"
                            >
                              <img
                                src={ev.thumbnail_url}
                                alt={ev.metadata?.title || ev.clip_title || "Clip"}
                                className="w-full h-full object-cover group-hover:scale-105 transition duration-300"
                              />
                              <div className="absolute inset-0 bg-black/20 flex items-center justify-center group-hover:bg-black/10 transition">
                                <Play className="h-6 w-6 text-white drop-shadow-md" />
                              </div>
                              <span className="absolute bottom-1 right-1 px-1.5 py-0.5 rounded bg-black/80 text-[9px] font-mono font-bold text-white">
                                {ev.clip_duration}s
                              </span>
                            </div>
                          ) : (
                            <div className="h-20 w-32 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center shrink-0 text-slate-600">
                              <Video className="h-6 w-6" />
                            </div>
                          )}

                          {/* Infos Titre / Description */}
                          <div className="space-y-1 min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-800 text-purple-300 border border-purple-500/20">
                                {ev.platform === "youtube" ? "🔴 YouTube Shorts" : "🎵 TikTok"}
                              </span>
                              <span className="text-xs text-purple-400 font-semibold">
                                📅 {dateFormatted} à {timeStr}
                              </span>
                              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                🔥 Score IA {predScore}%
                              </span>
                            </div>

                            <h3
                              onClick={() => setDetailModalEvent(ev)}
                              className="text-sm sm:text-base font-bold text-white hover:text-purple-300 cursor-pointer transition line-clamp-1"
                            >
                              {ev.metadata?.title || ev.clip_title}
                            </h3>

                            <p className="text-xs text-slate-400 line-clamp-2">
                              {ev.metadata?.description || ev.clip_hook}
                            </p>

                            {ev.metadata?.algorithmic_reason && (
                              <p className="text-[11px] text-purple-300/80 bg-purple-950/20 border border-purple-500/20 px-2.5 py-1 rounded-lg line-clamp-1">
                                🧠 {ev.metadata.algorithmic_reason}
                              </p>
                            )}
                          </div>
                        </div>

                        {/* Actions à droite */}
                        <div className="flex items-center gap-2 self-end md:self-center shrink-0">
                          {isPublished ? (
                            <a
                              href={ev.url || "#"}
                              target="_blank"
                              rel="noreferrer"
                              className="px-4 py-2 rounded-xl bg-emerald-600/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-600/30 text-xs font-semibold flex items-center gap-1.5 transition"
                            >
                              <CheckCircle2 className="h-3.5 w-3.5" /> Voir la vidéo
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          ) : (
                            <>
                              <button
                                onClick={() => handlePublishNow(ev.id)}
                                disabled={publishingId === ev.id}
                                className="px-4 py-2 rounded-xl bg-amber-500/20 border border-amber-500/30 text-amber-300 hover:bg-amber-500/30 text-xs font-semibold flex items-center gap-1.5 transition"
                              >
                                <Send className="h-3.5 w-3.5" /> Publier maintenant
                              </button>
                              <button
                                onClick={() => {
                                  setRescheduleEvent(ev);
                                  setRescheduleDateTime(
                                    ev.scheduled_at ? new Date(ev.scheduled_at).toISOString().slice(0, 16) : ""
                                  );
                                }}
                                className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                                title="Replanifier"
                              >
                                <Clock className="h-4 w-4" />
                              </button>
                              <button
                                onClick={() => handleDeletePub(ev.id)}
                                className="p-2 rounded-xl bg-slate-800 hover:bg-rose-950/40 hover:text-rose-400 text-slate-400 transition"
                                title="Supprimer"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
        </div>

      {/* MODAL DÉTAILS D'UN ÉVÉNEMENT & ANALYSE ALGORITHMIQUE */}
      {detailModalEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-2xl w-full p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between border-b border-slate-800 pb-4">
              <div>
                <span className="text-xs font-bold text-purple-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5" /> Détails de Publication & Renseignement Algorithmique
                </span>
                <h3 className="text-lg font-bold text-white mt-1">
                  {detailModalEvent.metadata?.title || detailModalEvent.clip_title}
                </h3>
              </div>
              <button
                onClick={() => setDetailModalEvent(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg"
              >
                ✕
              </button>
            </div>

            {/* Lecteur / Miniature Vidéo */}
            {detailModalEvent.video_url ? (
              <div className="rounded-2xl overflow-hidden bg-black border border-slate-800 max-h-72 flex items-center justify-center">
                <video
                  src={detailModalEvent.video_url}
                  controls
                  className="max-h-72 w-auto object-contain"
                />
              </div>
            ) : detailModalEvent.thumbnail_url ? (
              <div className="rounded-2xl overflow-hidden bg-black border border-slate-800 max-h-60 flex items-center justify-center">
                <img
                  src={detailModalEvent.thumbnail_url}
                  alt="Aperçu"
                  className="max-h-60 w-auto object-contain"
                />
              </div>
            ) : null}

            {/* Description & Tags */}
            <div className="space-y-3 text-xs">
              <div>
                <span className="text-slate-400 font-semibold block mb-1">Description générée :</span>
                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800/80 text-slate-200 whitespace-pre-line leading-relaxed">
                  {detailModalEvent.metadata?.description || "Aucune description"}
                </div>
              </div>

              {detailModalEvent.metadata?.tags && detailModalEvent.metadata.tags.length > 0 && (
                <div>
                  <span className="text-slate-400 font-semibold block mb-1">Tags & Mots-clés :</span>
                  <div className="flex flex-wrap gap-1.5">
                    {detailModalEvent.metadata.tags.map((t, i) => (
                      <span key={i} className="px-2 py-0.5 rounded-lg bg-slate-800 text-slate-300 text-[10px]">
                        #{t}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Analyse de l'algorithme */}
              <div className="p-4 rounded-2xl bg-purple-950/20 border border-purple-500/30 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-purple-300 flex items-center gap-1.5">
                    <Sparkles className="h-4 w-4" /> Raisonnement Algorithmique Gemini
                  </span>
                  <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-bold border border-amber-500/30">
                    Score {detailModalEvent.metadata?.predictive_score || 92}%
                  </span>
                </div>
                <p className="text-slate-300 leading-relaxed text-xs">
                  {detailModalEvent.metadata?.algorithmic_reason || "Créneau sélectionné en fonction des pics de consommation vidéo de l'audience."}
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
              <button
                onClick={() => setDetailModalEvent(null)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-white transition"
              >
                Fermer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL PLANIFICATION IA PRÉDICTIVE */}
      {predictModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
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

      {/* MODAL REPLANIFIER */}
      {rescheduleEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
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
