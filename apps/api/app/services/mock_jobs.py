from datetime import datetime

from app.models import GenerationJob, JobStatus, JobType, MediaAsset, MediaType, ProjectStatus
from app.services.openai_images import OpenAIImageGenerationUnavailable, generate_openai_image
from app.store import store


def run_mock_job(job: GenerationJob) -> GenerationJob:
    job.status = JobStatus.running
    job.attempts += 1
    job.updated_at = datetime.utcnow()
    store.save()

    match job.job_type:
        case JobType.image_generation:
            storage_url, provider, metadata = _generate_image_asset(job)
            asset = MediaAsset(
                project_id=job.project_id,
                type=MediaType.generated_image,
                provider=provider,
                storage_url=storage_url,
                mime_type="image/png" if provider == "openai" else "image/svg+xml",
                width=1080,
                height=1920,
                metadata=metadata,
            )
        case JobType.image_to_video:
            asset = MediaAsset(
                project_id=job.project_id,
                type=MediaType.generated_video,
                provider=job.provider,
                storage_url=_mock_asset_url(job, "video.mp4"),
                mime_type="video/mp4",
                duration_seconds=float(job.input.get("duration_seconds", 5)),
                width=1080,
                height=1920,
                metadata={
                    "motion_prompt": job.input.get("motion_prompt"),
                    "source_image_asset_id": job.input.get("source_image_asset_id"),
                },
            )
        case JobType.tts:
            asset = MediaAsset(
                project_id=job.project_id,
                type=MediaType.generated_audio,
                provider=job.provider,
                storage_url=_mock_asset_url(job, "voice.mp3"),
                mime_type="audio/mpeg",
                duration_seconds=4.0,
                metadata={
                    "script": job.input.get("script"),
                    "voice_preset_id": job.input.get("voice_preset_id"),
                },
            )
        case JobType.final_export:
            asset = MediaAsset(
                project_id=job.project_id,
                type=MediaType.final_video,
                provider=job.provider,
                storage_url=_mock_asset_url(job, "final.mp4"),
                mime_type="video/mp4",
                duration_seconds=5.0,
                width=1080,
                height=1920,
                metadata={
                    "captions_enabled": job.input.get("captions_enabled"),
                    "generated_video_asset_id": job.input.get("generated_video_asset_id"),
                    "audio_asset_id": job.input.get("audio_asset_id"),
                },
            )

    store.state.media_assets[asset.id] = asset
    job.status = JobStatus.succeeded
    job.output_asset_id = asset.id
    job.updated_at = datetime.utcnow()

    project = store.state.projects[job.project_id]
    project.status = (
        ProjectStatus.ready if job.job_type == JobType.final_export else ProjectStatus.generating
    )
    project.updated_at = datetime.utcnow()

    store.save()
    return job


def _mock_asset_url(job: GenerationJob, filename: str) -> str:
    return f"mock://projects/{job.project_id}/jobs/{job.id}/{filename}"


def _generate_image_asset(job: GenerationJob) -> tuple[str, str, dict[str, object]]:
    prompt = job.input.get("prompt")
    if not isinstance(prompt, str):
        raise ValueError("Image generation requires a prompt")

    try:
        storage_url = generate_openai_image(job.project_id, prompt)
        return storage_url, "openai", {"prompt": prompt, "mode": "live"}
    except OpenAIImageGenerationUnavailable as error:
        return (
            _mock_asset_url(job, "image.svg"),
            "mock-openai",
            {"prompt": prompt, "mode": "mock", "reason": str(error)},
        )
