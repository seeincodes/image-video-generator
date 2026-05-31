import shutil
import subprocess
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

from app.core.config import settings
from app.models import MediaAsset
from app.services.storage import read_local_asset, save_local_asset


class MuseTalkLipSyncUnavailable(RuntimeError):
    pass


class MuseTalkLipSyncFailed(RuntimeError):
    pass


def generate_musetalk_lip_sync(
    *,
    project_id: UUID,
    video_asset: MediaAsset,
    audio_asset: MediaAsset,
    bbox_shift: int = 0,
) -> tuple[str, float | None, dict[str, object]]:
    if not settings.musetalk_enabled:
        raise MuseTalkLipSyncUnavailable("MUSETALK_ENABLED is false")
    if settings.musetalk_repo_path is None:
        raise MuseTalkLipSyncUnavailable("MUSETALK_REPO_PATH is not configured")
    if settings.musetalk_model_dir is None:
        raise MuseTalkLipSyncUnavailable("MUSETALK_MODEL_DIR is not configured")

    repo_path = Path(settings.musetalk_repo_path)
    model_dir = Path(settings.musetalk_model_dir)
    if not repo_path.exists():
        raise MuseTalkLipSyncUnavailable("MuseTalk repo path does not exist")
    if not model_dir.exists():
        raise MuseTalkLipSyncUnavailable("MuseTalk model directory does not exist")

    try:
        video_content, _video_type = read_local_asset(video_asset.storage_url)
        audio_content, _audio_type = read_local_asset(audio_asset.storage_url)
    except (OSError, ValueError) as error:
        message = "MuseTalk requires local video and audio assets"
        raise MuseTalkLipSyncUnavailable(message) from error

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_video_path = temp_path / "source.mp4"
        input_audio_path = temp_path / "voice.wav"
        config_path = temp_path / "inference.yaml"
        output_name = f"{uuid4()}-musetalk-lipsync.mp4"
        result_dir = Path(settings.musetalk_result_dir)
        result_path = result_dir / "v15" / output_name

        input_video_path.write_bytes(video_content)
        input_audio_path.write_bytes(audio_content)
        config_path.write_text(
            "\n".join(
                [
                    "task_0:",
                    f' video_path: "{input_video_path}"',
                    f' audio_path: "{input_audio_path}"',
                    f" bbox_shift: {bbox_shift}",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        command = _musetalk_command(
            repo_path=repo_path,
            model_dir=model_dir,
            inference_config=config_path,
            result_dir=result_dir,
            output_name=output_name,
        )
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            cwd=repo_path,
            text=True,
            timeout=settings.musetalk_timeout_seconds,
        )
        if result.returncode != 0:
            raise MuseTalkLipSyncFailed(result.stderr[-1000:] or result.stdout[-1000:])
        if not result_path.exists() or result_path.stat().st_size == 0:
            raise MuseTalkLipSyncFailed("MuseTalk did not write an output MP4")

        storage_url = save_local_asset(
            project_id=project_id,
            filename="musetalk-lipsync.mp4",
            content=result_path.read_bytes(),
        )

    duration_seconds = _probe_duration(video_asset)
    metadata = {
        "mode": "live",
        "backend": "musetalk",
        "source_video_asset_id": str(video_asset.id),
        "audio_asset_id": str(audio_asset.id),
        "bbox_shift": bbox_shift,
        "musetalk_version": "v15",
        "use_float16": settings.musetalk_use_float16,
    }
    return storage_url, duration_seconds, metadata


def _musetalk_command(
    *,
    repo_path: Path,
    model_dir: Path,
    inference_config: Path,
    result_dir: Path,
    output_name: str,
) -> list[str]:
    command = [
        settings.musetalk_python,
        "scripts/inference.py",
        "--inference_config",
        str(inference_config),
        "--result_dir",
        str(result_dir),
        "--output_vid_name",
        output_name,
        "--unet_config",
        str(model_dir / "musetalk" / "musetalk.json"),
        "--unet_model_path",
        str(model_dir / "musetalkV15" / "unet.pth"),
        "--whisper_dir",
        str(model_dir / "whisper"),
        "--gpu_id",
        str(settings.musetalk_gpu_id),
        "--batch_size",
        str(settings.musetalk_batch_size),
        "--version",
        "v15",
    ]
    if settings.musetalk_use_float16:
        command.append("--use_float16")
    ffmpeg_static_path = repo_path / "ffmpeg-4.4-amd64-static"
    if ffmpeg_static_path.exists():
        command.extend(["--ffmpeg_path", str(ffmpeg_static_path)])
    return command


def copy_video_as_mock_lip_sync(
    *,
    project_id: UUID,
    video_asset: MediaAsset,
    audio_asset: MediaAsset,
    reason: str,
) -> tuple[str, float | None, dict[str, object]]:
    try:
        video_content, _video_type = read_local_asset(video_asset.storage_url)
    except (OSError, ValueError) as error:
        raise ValueError("Lip-sync fallback requires a local video asset") from error

    storage_url = save_local_asset(
        project_id=project_id,
        filename="mock-lipsync-video.mp4",
        content=video_content,
    )
    metadata = {
        "mode": "mock",
        "backend": "mock-copy",
        "source_video_asset_id": str(video_asset.id),
        "audio_asset_id": str(audio_asset.id),
        "reason": reason,
    }
    return storage_url, video_asset.duration_seconds, metadata


def _probe_duration(video_asset: MediaAsset) -> float | None:
    if video_asset.duration_seconds is not None:
        return video_asset.duration_seconds
    if shutil.which("ffprobe") is None:
        return None
    try:
        video_content, _video_type = read_local_asset(video_asset.storage_url)
    except (OSError, ValueError):
        return None
    with tempfile.TemporaryDirectory() as temp_dir:
        video_path = Path(temp_dir) / "video.mp4"
        video_path.write_bytes(video_content)
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            check=False,
            text=True,
        )
    if result.returncode != 0:
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None
