"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createProject,
  exportProject,
  generateImage,
  generateVideo,
  generateVoice,
  getProject,
  lipSync,
  listProjects,
  toAssetUrl,
  uploadReferenceImage,
} from "@/app/api";
import type { GenerationJob, MediaAsset, MediaType, Project, ProjectDetail } from "@/app/types";

const pollIntervalMs = 2000;

type GenerationStage = "images" | "video" | "voice" | "lipSync" | "export" | null;

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
  const [recentProjects, setRecentProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [selectedImageId, setSelectedImageId] = useState<string | null>(null);
  const [activeStage, setActiveStage] = useState<GenerationStage>(null);
  const [error, setError] = useState<string | null>(null);

  const isGenerating = activeStage !== null;

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

  const refreshProjectHistory = useCallback(async () => {
    const projects = await listProjects();
    const sortedProjects = sortProjects(projects);
    setRecentProjects(sortedProjects.slice(0, 8));
    return sortedProjects;
  }, []);

  useEffect(() => {
    let shouldUpdate = true;
    listProjects()
      .then((projects) => {
        if (shouldUpdate) {
          setRecentProjects(sortProjects(projects).slice(0, 8));
        }
      })
      .catch(() => {
        if (shouldUpdate) {
          setRecentProjects([]);
        }
      });

    return () => {
      shouldUpdate = false;
    };
  }, []);

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
    setActiveStage("images");

    try {
      const createdProject = await createProject({
        title: imagePrompt.slice(0, 48) || "Untitled video",
        aspect_ratio: aspectRatio,
      });

      setProject({ ...createdProject, media_assets: [], jobs: [] });
      setSelectedProjectId(createdProject.id);

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
      await refreshProjectHistory();
    } catch (generationError) {
      setError(
        generationError instanceof Error ? generationError.message : "Image generation failed",
      );
    } finally {
      setActiveStage(null);
    }
  }

  async function handleGenerateVideo() {
    if (!project || !selectedImage) {
      setError("Select an image option before generating video.");
      return;
    }

    setError(null);

    try {
      const activeProject = project;
      const video = await generateVideoFromSelectedImage(activeProject, selectedImage);
      const audio = await generateVoiceover(activeProject);
      const lipSyncedVideo = await generateLipSync(activeProject, video, audio);
      await generateFinalExport(activeProject, lipSyncedVideo, audio);
      await refreshProjectHistory();
    } catch (generationError) {
      setError(generationError instanceof Error ? generationError.message : "Generation failed");
    } finally {
      setActiveStage(null);
    }
  }

  async function handleRegenerateVideo() {
    if (!project || !selectedImage) {
      setError("Select an image option before regenerating motion.");
      return;
    }

    setError(null);

    try {
      await generateVideoFromSelectedImage(project, selectedImage);
    } catch (generationError) {
      setError(
        generationError instanceof Error ? generationError.message : "Motion generation failed",
      );
    } finally {
      setActiveStage(null);
    }
  }

  async function handleRegenerateVoice() {
    if (!project) {
      setError("Generate image options before regenerating voice.");
      return;
    }

    setError(null);

    try {
      await generateVoiceover(project);
    } catch (generationError) {
      setError(generationError instanceof Error ? generationError.message : "Voice generation failed");
    } finally {
      setActiveStage(null);
    }
  }

  async function handleRegenerateLipSync() {
    if (!project || !assetsByType.video || !assetsByType.audio) {
      setError("Generate motion and voice before regenerating lip sync.");
      return;
    }

    setError(null);

    try {
      await generateLipSync(project, assetsByType.video, assetsByType.audio);
    } catch (generationError) {
      setError(generationError instanceof Error ? generationError.message : "Lip sync failed");
    } finally {
      setActiveStage(null);
    }
  }

  async function handleRegenerateExport() {
    if (!project || !assetsByType.lipSyncedVideo || !assetsByType.audio) {
      setError("Generate lip sync and voice before regenerating export.");
      return;
    }

    setError(null);

    try {
      await generateFinalExport(project, assetsByType.lipSyncedVideo, assetsByType.audio);
      await refreshProjectHistory();
    } catch (generationError) {
      setError(generationError instanceof Error ? generationError.message : "Export failed");
    } finally {
      setActiveStage(null);
    }
  }

  async function generateVideoFromSelectedImage(activeProject: ProjectDetail, image: MediaAsset) {
    setActiveStage("video");
    const videoJob = await generateVideo(activeProject.id, {
      source_image_asset_id: image.id,
      motion_prompt: motionPrompt,
      duration_seconds: 5,
    });
    return waitForJobAsset(activeProject.id, videoJob.id, "generated_video", 180);
  }

  async function generateVoiceover(activeProject: ProjectDetail) {
    setActiveStage("voice");
    const voiceJob = await generateVoice(activeProject.id, {
      script: narration,
      voice_preset_id: "kokoro-af-heart",
    });
    return waitForJobAsset(activeProject.id, voiceJob.id, "generated_audio");
  }

  async function generateLipSync(
    activeProject: ProjectDetail,
    video: MediaAsset,
    audio: MediaAsset,
  ) {
    setActiveStage("lipSync");
    const lipSyncJob = await lipSync(activeProject.id, {
      generated_video_asset_id: video.id,
      audio_asset_id: audio.id,
    });
    return waitForJobAsset(activeProject.id, lipSyncJob.id, "lip_synced_video");
  }

  async function generateFinalExport(
    activeProject: ProjectDetail,
    lipSyncedVideo: MediaAsset,
    audio: MediaAsset,
  ) {
    setActiveStage("export");
    const exportJob = await exportProject(activeProject.id, {
      generated_video_asset_id: lipSyncedVideo.id,
      audio_asset_id: audio.id,
      captions_enabled: true,
    });
    return waitForJobAsset(activeProject.id, exportJob.id, "final_video");
  }

  async function refreshProject(projectId: string) {
    const detail = await getProject(projectId);
    setProject(detail);
    setSelectedProjectId(detail.id);
    return detail;
  }

  async function handleLoadProject(projectId: string) {
    setError(null);
    setSelectedProjectId(projectId);
    try {
      const detail = await refreshProject(projectId);
      const newestImage = newestAsset(detail.media_assets, "generated_image");
      setSelectedImageId(newestImage?.id ?? null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Project load failed");
    }
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
              {activeStage === "images" ? "Generating images..." : "Generate/regenerate image options"}
            </button>

            <button
              className="button secondary"
              disabled={isGenerating || !selectedImage}
              onClick={handleGenerateVideo}
              type="button"
            >
              {isGenerating && activeStage !== "images"
                ? "Generating pipeline..."
                : "Generate video from selected image"}
            </button>
          </div>

          <div className="regen-panel">
            <div>
              <strong>Regenerate one step</strong>
              <p>Keep earlier assets and rerun only the stage you want to improve.</p>
            </div>
            <div className="regen-actions">
              <button
                className="button secondary"
                disabled={isGenerating || !selectedImage}
                onClick={handleRegenerateVideo}
                type="button"
              >
                {activeStage === "video" ? "Regenerating motion..." : "Regenerate motion only"}
              </button>
              <button
                className="button secondary"
                disabled={isGenerating || !project}
                onClick={handleRegenerateVoice}
                type="button"
              >
                {activeStage === "voice" ? "Regenerating voice..." : "Regenerate voice only"}
              </button>
              <button
                className="button secondary"
                disabled={isGenerating || !assetsByType.video || !assetsByType.audio}
                onClick={handleRegenerateLipSync}
                type="button"
              >
                {activeStage === "lipSync" ? "Regenerating lip sync..." : "Regenerate lip sync only"}
              </button>
              <button
                className="button secondary"
                disabled={isGenerating || !assetsByType.lipSyncedVideo || !assetsByType.audio}
                onClick={handleRegenerateExport}
                type="button"
              >
                {activeStage === "export" ? "Regenerating export..." : "Regenerate export only"}
              </button>
            </div>
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

      <ProjectHistory
        currentProjectId={project?.id ?? selectedProjectId}
        onLoadProject={handleLoadProject}
        projects={recentProjects}
      />

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
        {assetsByType.final?.storage_url.startsWith("/") ? (
          <a className="download-link" download href={toAssetUrl(assetsByType.final.storage_url)}>
            Download final MP4
          </a>
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

function ProjectHistory({
  currentProjectId,
  onLoadProject,
  projects,
}: {
  currentProjectId: string;
  onLoadProject: (projectId: string) => void;
  projects: Project[];
}) {
  return (
    <div className="card history-card">
      <div>
        <h2>Recent projects</h2>
        <p>Reopen previous outputs and compare generated videos.</p>
      </div>
      {projects.length > 0 ? (
        <ul className="history-list">
          {projects.map((project) => (
            <li key={project.id}>
              <button
                className={project.id === currentProjectId ? "history-item selected" : "history-item"}
                onClick={() => onLoadProject(project.id)}
                type="button"
              >
                <span>{project.title}</span>
                <small>
                  {project.status} · {formatDate(project.updated_at)}
                </small>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="history-empty">Generated projects will appear here.</p>
      )}
    </div>
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

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function sortProjects(projects: Project[]) {
  return [...projects].sort(
    (left, right) => new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime(),
  );
}

function delay(durationMs: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, durationMs);
  });
}
