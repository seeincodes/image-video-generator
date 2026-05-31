import subprocess
import tempfile
from datetime import datetime
from html import escape
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
    edit_openai_image,
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
                mime_type=_image_mime_type(provider, metadata),
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

    reference_image_asset_id = job.input.get("reference_image_asset_id")
    style = job.input.get("style")
    negative_prompt = job.input.get("negative_prompt")
    final_prompt = _build_image_prompt(
        prompt=prompt,
        style=style if isinstance(style, str) else None,
        negative_prompt=negative_prompt if isinstance(negative_prompt, str) else None,
    )
    metadata = {
        "prompt": prompt,
        "final_prompt": final_prompt,
        "style": style,
        "negative_prompt": negative_prompt,
    }
    if isinstance(reference_image_asset_id, str):
        reference_image = store.state.media_assets.get(UUID(reference_image_asset_id))
        if reference_image is None:
            raise ValueError("Reference image asset not found")

        try:
            storage_url = edit_openai_image(
                project_id=job.project_id,
                prompt=final_prompt,
                reference_storage_url=reference_image.storage_url,
            )
            return (
                storage_url,
                "openai",
                metadata
                | {
                    "mode": "live",
                    "generation_mode": "image_edit",
                    "reference_image_asset_id": reference_image_asset_id,
                },
            )
        except OpenAIImageGenerationUnavailable as error:
            storage_url, fallback_metadata = _generate_mock_image_file(
                job.project_id,
                final_prompt,
                reference_image,
            )
            return (
                storage_url,
                "mock-openai",
                metadata
                | fallback_metadata
                | {
                    "mode": "mock",
                    "generation_mode": "image_edit",
                    "reference_image_asset_id": reference_image_asset_id,
                    "reason": str(error),
                },
            )
        except OpenAIImageGenerationFailed:
            raise

    try:
        storage_url = generate_openai_image(job.project_id, final_prompt)
        return storage_url, "openai", metadata | {"mode": "live", "generation_mode": "text"}
    except OpenAIImageGenerationUnavailable as error:
        storage_url, fallback_metadata = _generate_mock_image_file(
            job.project_id,
            final_prompt,
            None,
        )
        return (
            storage_url,
            "mock-openai",
            metadata
            | fallback_metadata
            | {"mode": "mock", "generation_mode": "text", "reason": str(error)},
        )
    except OpenAIImageGenerationFailed:
        raise


def _build_image_prompt(
    *,
    prompt: str,
    style: str | None,
    negative_prompt: str | None,
) -> str:
    prompt_parts = [prompt]
    if style:
        prompt_parts.append(f"Style: {style}.")
    if negative_prompt:
        prompt_parts.append(f"Avoid: {negative_prompt}.")
    return "\n".join(prompt_parts)


def _image_mime_type(provider: str, metadata: dict[str, object]) -> str:
    mime_type = metadata.get("mime_type")
    if isinstance(mime_type, str):
        return mime_type
    return "image/png" if provider == "openai" else "image/svg+xml"


def _generate_mock_image_file(
    project_id: UUID,
    prompt: str,
    reference_image: MediaAsset | None,
) -> tuple[str, dict[str, object]]:
    if reference_image is not None:
        try:
            content, content_type = read_local_asset(reference_image.storage_url)
        except (OSError, ValueError):
            content = b""
            content_type = ""
        if content and content_type in {"image/jpeg", "image/png", "image/webp"}:
            extension = {
                "image/jpeg": "jpg",
                "image/png": "png",
                "image/webp": "webp",
            }[content_type]
            return (
                save_local_asset(
                    project_id=project_id,
                    filename=f"mock-reference-image.{extension}",
                    content=content,
                ),
                {"mime_type": content_type, "mock_source": "reference_image"},
            )

    safe_prompt = escape(prompt[:180])
    svg = "\n".join(
        [
            (
                '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" '
                'viewBox="0 0 1080 1920">'
            ),
            "  <defs>",
            '    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">',
            '      <stop offset="0%" stop-color="#1d1b4f"/>',
            '      <stop offset="100%" stop-color="#5546ff"/>',
            "    </linearGradient>",
            "  </defs>",
            '  <rect width="1080" height="1920" fill="url(#bg)"/>',
            '  <circle cx="540" cy="620" r="240" fill="#ffffff" opacity="0.16"/>',
            (
                '  <text x="540" y="900" text-anchor="middle" fill="#ffffff" '
                'font-family="Arial, sans-serif" font-size="64" font-weight="700">'
                "Mock generated image</text>"
            ),
            '  <foreignObject x="120" y="980" width="840" height="360">',
            (
                '    <div xmlns="http://www.w3.org/1999/xhtml" style="color: white; '
                "font: 42px Arial, sans-serif; text-align: center; line-height: 1.25;"
                f'">{safe_prompt}</div>'
            ),
            "  </foreignObject>",
            "</svg>",
        ]
    )
    return (
        save_local_asset(
            project_id=project_id,
            filename="mock-openai-image.svg",
            content=svg.encode("utf-8"),
        ),
        {"mime_type": "image/svg+xml", "mock_source": "placeholder"},
    )


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
        storage_url, mock_video_metadata = _generate_mock_video_file(
            job.project_id,
            duration_seconds,
            source_image,
        )
        return (
            storage_url,
            "mock-runway",
            metadata | mock_video_metadata | {"mode": "mock", "reason": str(error)},
        )
    except RunwayGenerationFailed:
        raise


def _generate_mock_video_file(
    project_id: UUID,
    duration_seconds: int,
    source_image: MediaAsset,
) -> tuple[str, dict[str, object]]:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        output_path = temp_path / "mock-video.mp4"
        command, mock_source = _mock_video_command(
            source_image=source_image,
            duration_seconds=duration_seconds,
            output_path=output_path,
            temp_path=temp_path,
        )
        result = _run_ffmpeg(command, timeout_seconds=30)
        if result is None or result.returncode != 0:
            command, mock_source = _mock_video_pattern_command(duration_seconds, output_path)
            result = _run_ffmpeg(command, timeout_seconds=30)
            if result is None:
                raise ValueError("FFmpeg mock video failed: timed out")
            if result.returncode != 0:
                raise ValueError(f"FFmpeg mock video failed: {result.stderr[-500:]}")

        return (
            save_local_asset(
                project_id=project_id,
                filename="mock-runway-video.mp4",
                content=output_path.read_bytes(),
            ),
            {"mock_video_source": mock_source},
        )


def _mock_video_command(
    *,
    source_image: MediaAsset,
    duration_seconds: int,
    output_path: Path,
    temp_path: Path,
) -> tuple[list[str], str]:
    try:
        image_content, image_type = read_local_asset(source_image.storage_url)
    except (OSError, ValueError):
        return _mock_video_pattern_command(duration_seconds, output_path)

    if image_type not in {"image/jpeg", "image/png", "image/webp", "image/svg+xml"}:
        return _mock_video_pattern_command(duration_seconds, output_path)

    extension = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/svg+xml": "svg",
    }[image_type]
    input_path = temp_path / f"source.{extension}"
    input_path.write_bytes(image_content)
    normalized_path = temp_path / "source-normalized.png"
    normalize_result = _run_ffmpeg(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-frames:v",
            "1",
            str(normalized_path),
        ],
        timeout_seconds=10,
    )
    if (
        normalize_result is None
        or normalize_result.returncode != 0
        or not normalized_path.exists()
        or normalized_path.stat().st_size == 0
    ):
        return _mock_video_pattern_command(duration_seconds, output_path)

    return (
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-loop",
            "1",
            "-framerate",
            "24",
            "-i",
            str(normalized_path),
            "-t",
            str(duration_seconds),
            "-vf",
            (
                "scale=720:1280:force_original_aspect_ratio=decrease,"
                "pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=0x24235f,format=yuv420p"
            ),
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        "source_image",
    )


def _run_ffmpeg(
    command: list[str],
    *,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return None


def _mock_video_pattern_command(
    duration_seconds: int,
    output_path: Path,
) -> tuple[list[str], str]:
    return (
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size=720x1280:rate=24:duration={duration_seconds}",
            "-vf",
            "format=yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        "test_pattern",
    )


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
