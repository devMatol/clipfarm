import {
  Account,
  Clip,
  Project,
  Publication,
  PublishMetadata,
  ValidationResult,
  WordItem,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      Accept: "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let errorMsg = `Erreur ${res.status}`;
    try {
      const errJson = await res.json();
      if (typeof errJson.detail === "string") {
        errorMsg = errJson.detail;
      } else if (Array.isArray(errJson.detail)) {
        errorMsg = errJson.detail
          .map((e: any) =>
            typeof e === "object" ? e.msg || e.message || JSON.stringify(e) : String(e)
          )
          .join(" ; ");
      } else if (errJson.detail && typeof errJson.detail === "object") {
        errorMsg = JSON.stringify(errJson.detail);
      }
    } catch {
      // Ignorer si pas du json
    }
    throw new Error(errorMsg);
  }

  return res.json();
}

export const api = {
  getProjects: () => fetchApi<Project[]>("/projects"),
  getProject: (id: string) => fetchApi<Project>(`/projects/${id}`),
  deleteProject: (id: string) =>
    fetchApi<{ ok: boolean; message: string }>(`/projects/${id}`, {
      method: "DELETE",
    }),

  createProjectFromUrl: (data: {
    url: string;
    layout?: string;
    format?: string;
    cam?: { x: number; y: number; w: number; h: number } | null;
    captions?: string;
    max_clips?: number;
    min_clip_s?: number;
    max_clip_s?: number;
    llm?: string;
    skip_if_subtitles_present?: boolean;
  }) =>
    fetchApi<{ project: Project }>("/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  uploadProjectFile: async (formData: FormData) => {
    const res = await fetch(`${API_BASE}/projects/upload`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Erreur d'upload: ${res.status}`);
    }
    return res.json() as Promise<{ project: Project }>;
  },

  retryProject: (id: string) =>
    fetchApi<{ project: Project }>(`/projects/${id}/retry`, {
      method: "POST",
    }),

  setCam: (id: string, cam: { x: number; y: number; w: number; h: number }) =>
    fetchApi<{ project: Project; message: string }>(`/projects/${id}/set-cam`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cam),
    }),

  extractFrame: (id: string, time_s: number = 5.0) =>
    fetchApi<{ url: string }>(`/projects/${id}/extract-frame?time_s=${time_s}`, {
      method: "POST",
    }),

  getClip: (id: string) => fetchApi<Clip>(`/clips/${id}`),

  getClipWords: (id: string, start?: number, end?: number) => {
    const params = new URLSearchParams();
    if (start !== undefined) params.append("start", start.toString());
    if (end !== undefined) params.append("end", end.toString());
    const qs = params.toString() ? `?${params.toString()}` : "";
    return fetchApi<WordItem[]>(`/clips/${id}/words${qs}`);
  },

  regenerateClipWords: (id: string, mode: "reset" | "whisper" = "reset") =>
    fetchApi<WordItem[]>(`/clips/${id}/words/regenerate?mode=${mode}`, {
      method: "POST",
    }),

  updateClip: (
    id: string,
    data: {
      title?: string;
      start?: number;
      end?: number;
      words?: WordItem[];
    }
  ) =>
    fetchApi<Clip>(`/clips/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  rerenderClip: (
    id: string,
    data: {
      layout?: string;
      format?: string;
      cam?: { x: number; y: number; w: number; h: number } | null;
      captions?: string;
    }
  ) =>
    fetchApi<{ status: string; message: string; clip_id: string }>(`/clips/${id}/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  rerenderProject: (
    id: string,
    data: {
      clip_id?: string;
      layout?: string;
      format?: string;
      cam?: { x: number; y: number; w: number; h: number } | null;
      captions?: string;
    }
  ) =>
    fetchApi<{ status: string; message?: string }>(`/projects/${id}/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  // Module de publication & comptes
  getAccounts: () => fetchApi<Account[]>("/accounts"),

  getYouTubeConnectUrl: (redirectUri?: string) => {
    const callbackUri =
      redirectUri ||
      (typeof window !== "undefined"
        ? `${window.location.origin}/accounts/callback`
        : "http://localhost:3000/accounts/callback");
    return fetchApi<{ auth_url: string; state?: string }>(
      `/accounts/connect/youtube?redirect_uri=${encodeURIComponent(callbackUri)}`
    );
  },

  connectYouTubeCallback: (code: string, state?: string, redirectUri?: string) => {
    const callbackUri =
      redirectUri ||
      (typeof window !== "undefined"
        ? `${window.location.origin}/accounts/callback`
        : "http://localhost:3000/accounts/callback");
    return fetchApi<Account>("/accounts/connect/youtube/callback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, state, redirect_uri: callbackUri }),
    });
  },

  deleteAccount: (id: string) =>
    fetchApi<{ ok: boolean; message: string }>(`/accounts/${id}`, {
      method: "DELETE",
    }),

  createTestAccount: (platform: string = "youtube", name?: string) => {
    const qs = name ? `&name=${encodeURIComponent(name)}` : "";
    return fetchApi<Account>(`/accounts/test-account?platform=${platform}${qs}`, {
      method: "POST",
    });
  },

  generatePublishMetadata: (clipId: string, platform: string = "youtube") =>
    fetchApi<PublishMetadata>(`/clips/${clipId}/metadata?platform=${platform}`, {
      method: "POST",
    }),

  validatePublish: (
    clipId: string,
    payload: {
      account_id: string;
      platform: string;
      title: string;
      description?: string;
      tags?: string[];
      privacy?: string;
      made_for_kids?: boolean;
      category_id?: string;
      scheduled_at?: string | null;
      rights_confirmed?: boolean;
    }
  ) =>
    fetchApi<ValidationResult>(`/clips/${clipId}/validate-publish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  publishClip: (
    clipId: string,
    payload: {
      clip_id?: string;
      account_id: string;
      platform: string;
      title: string;
      description?: string;
      tags?: string[];
      privacy?: string;
      made_for_kids?: boolean;
      category_id?: string;
      scheduled_at?: string | null;
      publish_now?: boolean;
      rights_confirmed: boolean;
    }
  ) =>
    fetchApi<Publication>(`/clips/${clipId}/publish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clip_id: clipId, ...payload }),
    }),

  getPublications: (clipId?: string) =>
    fetchApi<Publication[]>(`/publications${clipId ? `?clip_id=${clipId}` : ""}`),

  getPublication: (id: string) => fetchApi<Publication>(`/publications/${id}`),

  mediaUrl: (path: string | undefined | null) => {
    if (!path) return "";
    if (path.startsWith("http")) return path;
    if (path.startsWith("/media")) return `${API_BASE}${path}`;
    return `${API_BASE}/media/${path}`;
  },
};
