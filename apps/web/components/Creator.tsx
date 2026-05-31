"use client";

import { useEffect, useMemo, useState } from "react";
import {
  createProject,
  exportProject,
  generateImage,
  generateVideo,
  generateVoice,
  getProject,
  lipSync,
  toAssetUrl,
  uploadReferenceImage,
} from "@/app/api";
import type { GenerationJob, MediaAsset, MediaType, ProjectDetail } from "@/app/types";

const pollIntervalMs = 2000;

const defaultPrompts = {
  imagePrompt: "A cinematic close-up of a golden retriever astronaut on Mars, warm sunset light",
  negativePrompt: "",
  motionPrompt: "Slow camera push-in, dust drifting through the orange sky, subtle head movement",
  narration: "Some stories begin with one small step. Others begin with a very good dog.",
  style: "Cinematic",
};

export function Creator() {
  const [imagePrompt, setImagePrompt] = useState(defaultPrompts.imagePrompt);
  const [negativePrompt, setNegativePrompt] = useState(defaultPrompts.negativePrompt);
  const [motionPrompt, setMotionPrompt] = useState(defaultPrompts.motionPrompt);
  const [narration, setNarration] = useState(defaultPrompts.narration);
  const [style, setStyle] = useState(defaultPrompts.style);
  const [aspectRatio, setAspectRatio] = useState("9:16");
  const [imageOptionCount, setImageOptionCount] = useState(3);
  const [referenceImageFile, setReferenceImageFile] = useState<File | null>(null);
  const [referenceImagePreviewUrl, setReferenceImagePreviewUrl] = useState<string | null>(null);
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [selectedImageId, setSelectedImageId] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const imageOptions = useMemo(
    () => (project?.media_assets ?? []).filter((asset) => asset.type === "generated_image"),
    [project],
  );
  const selectedImage = useMemo(
    () => imageOptions.find((asset) => asset.id === selectedImageId) ?? null,
    [imageOptions, selectedImageId],
  );

  const assetsByType = useMemo(() => {
    const assets = project?.media_assets ?? [];
    return {
      image: selectedImage ?? newestAsset(assets, "generated_image"),
      video: newestAsset(assets, "generated_video"),
      lipSyncedVideo: newestAsset(assets, "lip_synced_video"),
      audio: newestAsset(assets, "generated_audio"),
      final: newestAsset(assets, "final_video"),
    };
  }, [project, selectedImage]);

  useEffect(() => {
    return () => {
      if (referenceImagePreviewUrl) {
        URL.revokeObjectURL(referenceImagePreviewUrl);
      }
    };
  }, [referenceImagePreviewUrl]);

  async function handleGenerateImageOptions() {
    setError(null);
    setProject(null);
    setSelectedImageId(null);
    setIsGenerating(true);

    try {
      const createdProject = await createProject({
        title: imagePrompt.slice(0, 48) || "Untitled video",
        aspect_ratio: aspectRatio,
      });

      setProject({ ...createdProject, media_assets: [], jobs: [] });

      const referenceImage = referenceImageFile
        ? await uploadReferenceImage(createdProject.id, referenceImageFile)
        : null;

      const generatedImages: MediaAsset[] = [];
      for (let index = 0; index < imageOptionCount; index += 1) {
        const job = await generateImage(createdProject.id, {
          prompt: imagePrompt,
          negative_prompt: negativePrompt || undefined,
          reference_image_asset_id: referenceImage?.asset.id,
          style: style === "Auto" ? undefined : style,
        });
        const image = await waitForJobAsset(createdProject.id, job.id, "generated_image");
        generatedImages.push(image);
        if (index === 0) {
          setSelectedImageId(image.id);
        }
      }

      setSelectedImageId(generatedImages.at(0)?.id ?? null);
    } catch (generationError) {
      setError(
        generationError instanceof Error ? generationError.message : "Image generation failed",
      );
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleGenerateVideo() {
    if (!project || !selectedImage) {
      setError("Select an image option before generating video.");
      return;
    }

    setError(null);
    setIsGenerating(true);

    try {
      const activeProject = project;

      const videoJob = await generateVideo(activeProject.id, {
        source_image_asset_id: selectedImage.id,
        motion_prompt: motionPrompt,
        duration_seconds: 5,
      });
      const video = await waitForJobAsset(
        activeProject.id,
        videoJob.id,
        "generated_video",
        180,
      );

      const voiceJob = await generateVoice(activeProject.id, {
        script: narration,
        voice_preset_id: "kokoro-af-heart",
      });
      const audio = await waitForJobAsset(activeProject.id, voiceJob.id, "generated_audio");

      const lipSyncJob = await lipSync(activeProject.id, {
        generated_video_asset_id: video.id,
        audio_asset_id: audio.id,
      });
      const lipSyncedVideo = await waitForJobAsset(
        activeProject.id,
        lipSyncJob.id,
        "lip_synced_video",
      );

      const exportJob = await exportProject(activeProject.id, {
        generated_video_asset_id: lipSyncedVideo.id,
        audio_asset_id: audio.id,
        captions_enabled: true,
      });
      await waitForJobAsset(activeProject.id, exportJob.id, "final_video");
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

  function handleReferenceImageChange(file: File | null) {
    setReferenceImageFile(file);
    if (referenceImagePreviewUrl) {
      URL.revokeObjectURL(referenceImagePreviewUrl);
    }
    setReferenceImagePreviewUrl(file ? URL.createObjectURL(file) : null);
  }

  async function waitForJobAsset(
    projectId: string,
    jobId: string,
    mediaType: MediaType,
    maxAttempts = 60,
  ) {
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      const detail = await refreshProject(projectId);
      const job = detail.jobs.find((candidate) => candidate.id === jobId);
      if (job?.status === "failed") {
        throw new Error(job.error_message ?? `${job.job_type} failed`);
      }
      const asset = detail.media_assets.find((candidate) => candidate.id === job?.output_asset_id);
      if (job?.status === "succeeded" && asset?.type === mediaType) {
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
            <span>Reference image</span>
            <input
              accept="image/png,image/jpeg,image/webp"
              name="referenceImage"
              onChange={(event) => handleReferenceImageChange(event.target.files?.[0] ?? null)}
              type="file"
            />
          </label>

          {referenceImagePreviewUrl ? (
            <div className="reference-preview">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img alt="Reference" src={referenceImagePreviewUrl} />
              <button
                className="button secondary"
                onClick={() => handleReferenceImageChange(null)}
                type="button"
              >
                Clear reference
              </button>
            </div>
          ) : null}

          <label className="field">
            <span>Style</span>
            <select name="style" onChange={(event) => setStyle(event.target.value)} value={style}>
              <option>Auto</option>
              <option>Cinematic</option>
              <option>Photographic</option>
              <option>Design</option>
              <option>Animation</option>
              <option>Realistic</option>
            </select>
          </label>

          <label className="field">
            <span>Negative prompt</span>
            <textarea
              name="negativePrompt"
              onChange={(event) => setNegativePrompt(event.target.value)}
              placeholder="Things to avoid, e.g. extra fingers, text, watermark"
              value={negativePrompt}
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

          <label className="field">
            <span>Image options</span>
            <select
              name="imageOptionCount"
              onChange={(event) => setImageOptionCount(Number(event.target.value))}
              value={imageOptionCount}
            >
              <option value={1}>1 option</option>
              <option value={2}>2 options</option>
              <option value={3}>3 options</option>
              <option value={4}>4 options</option>
            </select>
          </label>

          <div className="button-row">
            <button
              className="button"
              disabled={isGenerating}
              onClick={handleGenerateImageOptions}
              type="button"
            >
              {isGenerating ? "Generating..." : "Generate/regenerate image options"}
            </button>

            <button
              className="button secondary"
              disabled={isGenerating || !selectedImage}
              onClick={handleGenerateVideo}
              type="button"
            >
              Generate video from selected image
            </button>
          </div>

          {imageOptions.length > 0 ? (
            <div className="image-options">
              {imageOptions.map((image, index) => (
                <button
                  className={`image-option ${image.id === selectedImageId ? "selected" : ""}`}
                  key={image.id}
                  onClick={() => setSelectedImageId(image.id)}
                  type="button"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img alt={`Generated option ${index + 1}`} src={toAssetUrl(image.storage_url)} />
                  <span>{image.id === selectedImageId ? "Selected" : `Option ${index + 1}`}</span>
                </button>
              ))}
            </div>
          ) : null}

          {error ? <p className="error">{error}</p> : null}
        </form>
      </div>

      <aside className="card preview">
        <div className="video-frame">
          {assetsByType.final?.storage_url.startsWith("/") ? (
            <video className="generated-video" controls src={toAssetUrl(assetsByType.final.storage_url)} />
          ) : assetsByType.lipSyncedVideo?.storage_url.startsWith("/") ? (
            <video className="generated-video" controls src={toAssetUrl(assetsByType.lipSyncedVideo.storage_url)} />
          ) : assetsByType.video?.storage_url.startsWith("/") ? (
            <video className="generated-video" controls src={toAssetUrl(assetsByType.video.storage_url)} />
          ) : assetsByType.image?.storage_url.startsWith("/") ? (
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
        {assetsByType.audio?.storage_url.startsWith("/") ? (
          <audio className="generated-audio" controls src={toAssetUrl(assetsByType.audio.storage_url)} />
        ) : null}

        <ul className="status-list">
          <StatusItem job={findJob(project, "image_generation")} label="Image" provider="OpenAI Images" />
          <StatusItem job={findJob(project, "image_to_video")} label="Motion" provider="Runway" />
          <StatusItem job={findJob(project, "tts")} label="Voice" provider="Kokoro" />
          <StatusItem job={findJob(project, "lip_sync")} label="Lip sync" provider="MuseTalk" />
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
  return project?.jobs.filter((job) => job.job_type === jobType).at(-1);
}

function newestAsset(assets: MediaAsset[], type: MediaAsset["type"]) {
  return assets.filter((asset) => asset.type === type).at(-1);
}

function delay(durationMs: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, durationMs);
  });
}
