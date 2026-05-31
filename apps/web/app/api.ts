import type { GenerationJob, MediaAsset, Project, ProjectDetail } from "./types";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function toAssetUrl(storageUrl: string) {
  if (storageUrl.startsWith("/")) {
    return `${apiBaseUrl}${storageUrl}`;
  }
  return storageUrl;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export function createProject(input: { title: string; aspect_ratio: string }) {
  return request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getProject(projectId: string) {
  return request<ProjectDetail>(`/projects/${projectId}`);
}

export function generateImage(
  projectId: string,
  input: {
    prompt: string;
    style?: string;
    negative_prompt?: string;
    reference_image_asset_id?: string;
  },
) {
  return request<GenerationJob>(`/projects/${projectId}/generate-image`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function uploadReferenceImage(projectId: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${apiBaseUrl}/projects/${projectId}/reference-image`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Reference image upload failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<{ asset: MediaAsset }>;
}

export function generateVideo(
  projectId: string,
  input: { source_image_asset_id: string; motion_prompt: string; duration_seconds: number },
) {
  return request<GenerationJob>(`/projects/${projectId}/generate-video`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function generateVoice(
  projectId: string,
  input: { script: string; voice_preset_id: string },
) {
  return request<GenerationJob>(`/projects/${projectId}/generate-voice`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function lipSync(
  projectId: string,
  input: { generated_video_asset_id: string; audio_asset_id: string; bbox_shift?: number },
) {
  return request<GenerationJob>(`/projects/${projectId}/lip-sync`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function exportProject(
  projectId: string,
  input: { generated_video_asset_id: string; audio_asset_id: string; captions_enabled: boolean },
) {
  return request<GenerationJob>(`/projects/${projectId}/export`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}
