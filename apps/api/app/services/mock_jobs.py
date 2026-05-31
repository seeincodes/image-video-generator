import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import UUID

from app.models import GenerationJob, JobStatus, JobType, MediaAsset, MediaType, ProjectStatus
from app.services.kokoro_tts import (
    KokoroTTSFailed,
    KokoroTTSUnavailable,
    generate_kokoro_speech,
)
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
from app.services.storage import read_local_asset, save_local_asset
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
            (
                storage_url,
                provider,
                mime_type,
                duration_seconds,
                metadata,
            ) = _generate_audio_asset(job)
            return MediaAsset(
                project_id=job.project_id,
                type=MediaType.generated_audio,
                provider=provider,
                storage_url=storage_url,
                mime_type=mime_type,
                duration_seconds=duration_seconds,
                metadata=metadata,
            )
        case JobType.final_export:
            storage_url, provider, metadata = _generate_final_export(job)
            return MediaAsset(
                project_id=job.project_id,
                type=MediaType.final_video,
                provider=provider,
                storage_url=storage_url,
                mime_type="video/mp4",
                duration_seconds=5.0,
                width=1080,
                height=1920,
                metadata=metadata,
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


def _generate_audio_asset(
    job: GenerationJob,
) -> tuple[str, str, str, float, dict[str, object]]:
    script = job.input.get("script")
    voice_preset_id = job.input.get("voice_preset_id")
    if not isinstance(script, str) or not isinstance(voice_preset_id, str):
        raise ValueError("TTS generation requires script and voice preset")

    try:
        storage_url, duration_seconds, metadata = generate_kokoro_speech(
            project_id=job.project_id,
            script=script,
            voice_preset_id=voice_preset_id,
        )
        return storage_url, "kokoro", "audio/wav", duration_seconds, metadata
    except KokoroTTSUnavailable as error:
        return (
            _mock_asset_url(job, "voice.mp3"),
            "mock-kokoro",
            "audio/mpeg",
            4.0,
            {
                "script": script,
                "voice_preset_id": voice_preset_id,
                "mode": "mock",
                "reason": str(error),
            },
        )
    except KokoroTTSFailed:
        raise


def _generate_final_export(job: GenerationJob) -> tuple[str, str, dict[str, object]]:
    generated_video_asset_id = job.input.get("generated_video_asset_id")
    audio_asset_id = job.input.get("audio_asset_id")
    if not isinstance(generated_video_asset_id, str) or not isinstance(audio_asset_id, str):
        raise ValueError("Final export requires generated video and audio assets")

    metadata = {
        "captions_enabled": job.input.get("captions_enabled"),
        "generated_video_asset_id": generated_video_asset_id,
        "audio_asset_id": audio_asset_id,
    }

    generated_video = store.state.media_assets.get(UUID(generated_video_asset_id))
    audio = store.state.media_assets.get(UUID(audio_asset_id))
    if generated_video is None or audio is None:
        raise ValueError("Final export source assets not found")

    if generated_video.storage_url.startswith("mock://") or audio.storage_url.startswith("mock://"):
        return _mock_asset_url(job, "final.mp4"), job.provider, metadata | {"mode": "mock"}

    try:
        video_content, _video_type = read_local_asset(generated_video.storage_url)
        audio_content, _audio_type = read_local_asset(audio.storage_url)
    except OSError as error:
        raise ValueError("Final export source assets could not be read") from error

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_video_path = temp_path / "input.mp4"
        input_audio_path = temp_path / "input.wav"
        output_path = temp_path / "final.mp4"
        input_video_path.write_bytes(video_content)
        input_audio_path.write_bytes(audio_content)

        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_video_path),
            "-i",
            str(input_audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ]
        result = subprocess.run(command, capture_output=True, check=False, text=True)
        if result.returncode != 0:
            raise ValueError(f"FFmpeg final export failed: {result.stderr[-500:]}")

        storage_url = save_local_asset(
            project_id=job.project_id,
            filename="final.mp4",
            content=output_path.read_bytes(),
        )

    return storage_url, job.provider, metadata | {"mode": "live"}
