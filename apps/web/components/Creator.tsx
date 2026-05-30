"use client";

import { useMemo, useState } from "react";
import {
  createProject,
  exportProject,
  generateImage,
  generateVideo,
  generateVoice,
  getProject,
  toAssetUrl,
} from "@/app/api";
import type { GenerationJob, JobType, MediaAsset, MediaType, ProjectDetail } from "@/app/types";

const pollIntervalMs = 2000;

const defaultPrompts = {
  imagePrompt: "A cinematic close-up of a golden retriever astronaut on Mars, warm sunset light",
  motionPrompt: "Slow camera push-in, dust drifting through the orange sky, subtle head movement",
  narration: "Some stories begin with one small step. Others begin with a very good dog.",
};

export function Creator() {
  const [imagePrompt, setImagePrompt] = useState(defaultPrompts.imagePrompt);
  const [motionPrompt, setMotionPrompt] = useState(defaultPrompts.motionPrompt);
  const [narration, setNarration] = useState(defaultPrompts.narration);
  const [aspectRatio, setAspectRatio] = useState("9:16");
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const assetsByType = useMemo(() => {
    const assets = project?.media_assets ?? [];
    return {
      image: newestAsset(assets, "generated_image"),
      video: newestAsset(assets, "generated_video"),
      audio: newestAsset(assets, "generated_audio"),
      final: newestAsset(assets, "final_video"),
    };
  }, [project]);

  async function handleGenerate() {
    setError(null);
    setIsGenerating(true);

    try {
      const createdProject = await createProject({
        title: imagePrompt.slice(0, 48) || "Untitled video",
        aspect_ratio: aspectRatio,
      });

      await generateImage(createdProject.id, { prompt: imagePrompt });
      const image = await waitForAsset(createdProject.id, "image_generation", "generated_image");

      await generateVideo(createdProject.id, {
        source_image_asset_id: image.id,
        motion_prompt: motionPrompt,
        duration_seconds: 5,
      });
      const video = await waitForAsset(createdProject.id, "image_to_video", "generated_video", 180);

      await generateVoice(createdProject.id, {
        script: narration,
        voice_preset_id: "kokoro-af-heart",
      });
      const audio = await waitForAsset(createdProject.id, "tts", "generated_audio");

      await exportProject(createdProject.id, {
        generated_video_asset_id: video.id,
        audio_asset_id: audio.id,
        captions_enabled: true,
      });
      await waitForAsset(createdProject.id, "final_export", "final_video");
    } catch (generationError) {
      setError(generationError instanceof Error ? generationError.message : "Generation failed");
    } finally {
      setIsGenerating(false);
    }
  }

  async function refreshProject(projectId: string) {
    const detail = await getProject(projectId);
    setProject(detail);
    return detail;
  }

  async function waitForAsset(
    projectId: string,
    jobType: JobType,
    mediaType: MediaType,
    maxAttempts = 60,
  ) {
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      const detail = await refreshProject(projectId);
      const job = findJob(detail, jobType);
      if (job?.status === "failed") {
        throw new Error(job.error_message ?? `${jobType} failed`);
      }
      const asset = newestAsset(detail.media_assets, mediaType);
      if (job?.status === "succeeded" && asset) {
        return asset;
      }
      await delay(pollIntervalMs);
    }

    throw new Error(`Timed out waiting for ${mediaType}`);
  }

  return (
    <section className="grid">
      <div className="card">
        <form className="form">
          <label className="field">
            <span>Image prompt</span>
            <textarea
              name="imagePrompt"
              onChange={(event) => setImagePrompt(event.target.value)}
              value={imagePrompt}
            />
          </label>

          <label className="field">
            <span>Motion prompt</span>
            <textarea
              name="motionPrompt"
              onChange={(event) => setMotionPrompt(event.target.value)}
              value={motionPrompt}
            />
          </label>

          <label className="field">
            <span>Narration</span>
            <textarea
              name="narration"
              onChange={(event) => setNarration(event.target.value)}
              value={narration}
            />
          </label>

          <label className="field">
            <span>Aspect ratio</span>
            <select
              name="aspectRatio"
              onChange={(event) => setAspectRatio(event.target.value)}
              value={aspectRatio}
            >
              <option>9:16</option>
              <option>1:1</option>
              <option>16:9</option>
            </select>
          </label>

          <button
            className="button"
            disabled={isGenerating}
            onClick={handleGenerate}
            type="button"
          >
            {isGenerating ? "Generating video..." : "Generate MVP video"}
          </button>

          {error ? <p className="error">{error}</p> : null}
        </form>
      </div>

      <aside className="card preview">
        <div className="video-frame">
          {assetsByType.image?.storage_url.startsWith("/") ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img alt="Generated source" className="generated-image" src={toAssetUrl(assetsByType.image.storage_url)} />
          ) : (
            <div>
              <h2>{assetsByType.final ? "Final MP4 ready" : "Preview placeholder"}</h2>
              <p>
                {assetsByType.final
                  ? assetsByType.final.storage_url
                  : "Run the local API to create mock image, video, voice, and export assets."}
              </p>
            </div>
          )}
        </div>

        <ul className="status-list">
          <StatusItem job={findJob(project, "image_generation")} label="Image" provider="OpenAI Images" />
          <StatusItem job={findJob(project, "image_to_video")} label="Motion" provider="Runway" />
          <StatusItem job={findJob(project, "tts")} label="Voice" provider="Kokoro" />
          <StatusItem job={findJob(project, "final_export")} label="Export" provider="FFmpeg" />
        </ul>
      </aside>
    </section>
  );
}

function StatusItem({
  job,
  label,
  provider,
}: {
  job?: GenerationJob;
  label: string;
  provider: string;
}) {
  return (
    <li>
      <div>
        <strong>{label}</strong>
        <div>{provider}</div>
      </div>
      <span className={`pill ${job?.status ?? "queued"}`}>{job?.status ?? "queued"}</span>
    </li>
  );
}

function findJob(project: ProjectDetail | null, jobType: GenerationJob["job_type"]) {
  return project?.jobs.find((job) => job.job_type === jobType);
}

function newestAsset(assets: MediaAsset[], type: MediaAsset["type"]) {
  return assets.filter((asset) => asset.type === type).at(-1);
}

function delay(durationMs: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, durationMs);
  });
}
