export type ProjectStatus =
  | "queued"
  | "ingesting"
  | "awaiting_cam"
  | "transcribing"
  | "analysing"
  | "detecting"
  | "rendering"
  | "ready"
  | "failed";

export interface ClipScore {
  hook?: number;
  emotion?: number;
  payoff?: number;
  standalone?: number;
  [key: string]: number | undefined;
}

export interface Clip {
  id: string;
  project_id: string;
  index: number;
  start: number;
  end: number;
  title: string;
  hook: string;
  reason: string;
  scores: ClipScore;
  final_score: number;
  layout: {
    name?: string;
    fmt?: string;
    cam?: { x: number; y: number; w: number; h: number } | null;
    [key: string]: any;
  };
  captions?: {
    preset?: string;
    [key: string]: any;
  } | null;
  file_path: string;
  video_url?: string;
  status: string;
  created_at: string;
}

export interface ProjectSettings {
  layout?: string;
  format?: string;
  cam?: { x: number; y: number; w: number; h: number } | null;
  captions?: string;
  max_clips?: number;
  min_clip_s?: number;
  max_clip_s?: number;
  llm?: string;
  skip_if_subtitles_present?: boolean;
  ai_clips_count?: number;
  ai_fallback_reason?: string;
}

export interface Project {
  id: string;
  source_url?: string | null;
  source_path?: string | null;
  status: ProjectStatus;
  progress: number;
  step: string;
  duration?: number | null;
  settings_json: ProjectSettings;
  error?: string | null;
  created_at: string;
  detected_cam?: [number, number, number, number] | null;
  cam_timeline?: any[] | null;
  clips?: Clip[];
  clips_count?: number;
}

export interface WordItem {
  text: string;
  start: number;
  end: number;
  prob?: number;
}

export interface ProgressEvent {
  project_id: string;
  step: string;
  progress: number;
  message: string;
  status: ProjectStatus;
  error?: string | null;
}

export interface Account {
  id: string;
  platform: "youtube" | "tiktok" | "instagram" | "postiz";
  platform_account_id: string;
  name: string;
  avatar_url?: string | null;
  status: "connected" | "expiring_soon" | "expired" | "revoked";
  created_at: string;
  updated_at: string;
}

export interface Publication {
  id: string;
  clip_id: string;
  account_id: string;
  platform: string;
  metadata_json: Record<string, any>;
  scheduled_at?: string | null;
  status: "draft" | "scheduled" | "uploading" | "processing" | "published" | "failed";
  external_id?: string | null;
  url?: string | null;
  error?: string | null;
  attempts: number;
  rights_confirmed: boolean;
  published_at?: string | null;
  created_at: string;
}

export interface PublishMetadata {
  title: string;
  description: string;
  tags: string[];
  hashtags_str?: string;
  category_id?: string;
  made_for_kids?: boolean;
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}
