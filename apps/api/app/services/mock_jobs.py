from datetime import datetime
from uuid import UUID

from app.models import GenerationJob, JobStatus, JobType, MediaAsset, MediaType, ProjectStatus
from app.services.openai_images import (
    OpenAIImageGenerationFailed,
    OpenAIImageGenerationUnavailable,
    generate_openai_image,
)
from app.services.runway import (
    RunwayGenerationFailed,
    RunwayGenerationUnavailable,
    generate_runway_video,
)
from app.store import store


def run_mock_job(job: GenerationJob) -> GenerationJob:
    job.status = JobStatus.running
    job.attempts += 1
    job.updated_at = datetime.utcnow()
    store.save()

    try:
        asset = _create_asset_for_job(job)
    except Exception as error:
        job.status = JobStatus.failed
        job.error_message = str(error)
        job.updated_at = datetime.utcnow()
        project = store.state.projects[job.project_id]
        project.status = ProjectStatus.failed
        project.updated_at = datetime.utcnow()
        store.save()
        return job

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


def _create_asset_for_job(job: GenerationJob) -> MediaAsset:
    match job.job_type:
        case JobType.image_generation:
            storage_url, provider, metadata = _generate_image_asset(job)
            return MediaAsset(
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
            storage_url, provider, metadata = _generate_video_asset(job)
            return MediaAsset(
                project_id=job.project_id,
                type=MediaType.generated_video,
                provider=provider,
                storage_url=storage_url,
                mime_type="video/mp4",
                duration_seconds=float(job.input.get("duration_seconds", 5)),
                width=1080,
                height=1920,
                metadata=metadata,
            )
        case JobType.tts:
            return MediaAsset(
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
            return MediaAsset(
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
    except OpenAIImageGenerationFailed:
        raise


def _generate_video_asset(job: GenerationJob) -> tuple[str, str, dict[str, object]]:
    motion_prompt = job.input.get("motion_prompt")
    source_image_asset_id = job.input.get("source_image_asset_id")
    duration_seconds = job.input.get("duration_seconds", 5)
    if not isinstance(motion_prompt, str) or not isinstance(source_image_asset_id, str):
        raise ValueError("Video generation requires motion prompt and source image asset")
    if not isinstance(duration_seconds, int):
        raise ValueError("Video generation duration must be an integer")

    source_image = store.state.media_assets.get(UUID(source_image_asset_id))
    if source_image is None:
        raise ValueError("Source image asset not found")

    metadata = {
        "motion_prompt": motion_prompt,
        "source_image_asset_id": source_image_asset_id,
        "duration_seconds": duration_seconds,
    }

    try:
        storage_url = generate_runway_video(
            project_id=job.project_id,
            source_image=source_image,
            motion_prompt=motion_prompt,
            duration_seconds=duration_seconds,
        )
        return storage_url, "runway", metadata | {"mode": "live"}
    except RunwayGenerationUnavailable as error:
        return (
            _mock_asset_url(job, "video.mp4"),
            "mock-runway",
            metadata | {"mode": "mock", "reason": str(error)},
        )
    except RunwayGenerationFailed:
        raise
