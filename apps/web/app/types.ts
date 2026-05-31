export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "canceled";

export type JobType = "image_generation" | "image_to_video" | "tts" | "lip_sync" | "final_export";

export type MediaType =
  | "uploaded_image"
  | "generated_image"
  | "generated_video"
  | "lip_synced_video"
  | "generated_audio"
  | "final_video";

export type Project = {
  id: string;
  title: string;
  status: "draft" | "generating" | "ready" | "failed";
  aspect_ratio: string;
  created_at: string;
  updated_at: string;
};

export type MediaAsset = {
  id: string;
  project_id: string;
  type: MediaType;
  provider: string;
  storage_url: string;
  mime_type: string;
  duration_seconds?: number | null;
  width?: number | null;
  height?: number | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type GenerationJob = {
  id: string;
  project_id: string;
  job_type: JobType;
  status: JobStatus;
  provider: string;
  provider_job_id?: string | null;
  input: Record<string, unknown>;
  output_asset_id?: string | null;
  error_message?: string | null;
  attempts: number;
  created_at: string;
  updated_at: string;
};

export type ProjectDetail = Project & {
  media_assets: MediaAsset[];
  jobs: GenerationJob[];
};
