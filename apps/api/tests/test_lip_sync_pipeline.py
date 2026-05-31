import math
import struct
import subprocess
import wave
from pathlib import Path

from app.models import (
    GenerationJob,
    JobStatus,
    JobType,
    MediaAsset,
    MediaType,
    Project,
    ProjectStatus,
)
from app.services import mock_jobs
from app.services.mock_jobs import run_mock_job
from app.services.runway import RunwayGenerationUnavailable
from app.services.storage import save_local_asset
from app.store import StoreState, store


def test_lip_sync_falls_back_to_local_asset_and_final_export_uses_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        mock_jobs,
        "generate_runway_video",
        _raise_runway_unavailable,
    )
    store.path = tmp_path / "data.json"
    store.state = StoreState()

    project = Project(title="Lip-sync regression")
    store.state.projects[project.id] = project

    source_image_url = save_local_asset(
        project_id=project.id,
        filename="source.svg",
        content=_source_svg().encode("utf-8"),
    )
    source_image = MediaAsset(
        project_id=project.id,
        type=MediaType.generated_image,
        provider="mock-openai",
        storage_url=source_image_url,
        mime_type="image/svg+xml",
        width=720,
        height=1280,
        metadata={"mode": "mock"},
    )
    store.state.media_assets[source_image.id] = source_image

    video_job = GenerationJob(
        project_id=project.id,
        job_type=JobType.image_to_video,
        provider="runway",
        input={
            "source_image_asset_id": str(source_image.id),
            "motion_prompt": "subtle natural speaking movement",
            "duration_seconds": 1,
        },
    )
    store.state.generation_jobs[video_job.id] = video_job
    run_mock_job(video_job)

    video_asset = store.state.media_assets[video_job.output_asset_id]
    audio_url = save_local_asset(
        project_id=project.id,
        filename="voice.wav",
        content=_sine_wave_bytes(),
    )
    audio_asset = MediaAsset(
        project_id=project.id,
        type=MediaType.generated_audio,
        provider="kokoro",
        storage_url=audio_url,
        mime_type="audio/wav",
        duration_seconds=1.0,
        metadata={"mode": "live"},
    )
    store.state.media_assets[audio_asset.id] = audio_asset

    lip_sync_job = GenerationJob(
        project_id=project.id,
        job_type=JobType.lip_sync,
        provider="musetalk",
        input={
            "generated_video_asset_id": str(video_asset.id),
            "audio_asset_id": str(audio_asset.id),
        },
    )
    store.state.generation_jobs[lip_sync_job.id] = lip_sync_job
    run_mock_job(lip_sync_job)

    lip_sync_asset = store.state.media_assets[lip_sync_job.output_asset_id]

    final_export_job = GenerationJob(
        project_id=project.id,
        job_type=JobType.final_export,
        provider="ffmpeg",
        input={
            "generated_video_asset_id": str(lip_sync_asset.id),
            "audio_asset_id": str(audio_asset.id),
            "captions_enabled": True,
        },
    )
    store.state.generation_jobs[final_export_job.id] = final_export_job
    run_mock_job(final_export_job)

    final_asset = store.state.media_assets[final_export_job.output_asset_id]

    assert lip_sync_job.status == JobStatus.succeeded
    assert lip_sync_job.attempts == 1
    assert lip_sync_asset.type == MediaType.lip_synced_video
    assert lip_sync_asset.provider == "mock-musetalk"
    assert lip_sync_asset.storage_url.startswith("/assets/")
    assert lip_sync_asset.mime_type == "video/mp4"
    assert lip_sync_asset.metadata["mode"] == "mock"
    assert lip_sync_asset.metadata["source_video_asset_id"] == str(video_asset.id)
    assert lip_sync_asset.metadata["audio_asset_id"] == str(audio_asset.id)

    assert final_export_job.status == JobStatus.succeeded
    assert final_export_job.input["generated_video_asset_id"] == str(lip_sync_asset.id)
    assert final_asset.type == MediaType.final_video
    assert final_asset.storage_url.startswith("/assets/")
    assert final_asset.provider == "ffmpeg"
    assert final_asset.metadata["mode"] == "live"
    assert store.state.projects[project.id].status == ProjectStatus.ready

    final_path = _asset_path(tmp_path, final_asset.storage_url)
    assert final_path.stat().st_size > 0
    assert _ffprobe_streams(final_path) == ["h264,video", "aac,audio"]


def _source_svg() -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="720" height="1280">'
        '<rect width="720" height="1280" fill="#ff3366"/>'
        '<circle cx="360" cy="480" r="180" fill="#ffe7c2"/>'
        '<rect x="260" y="560" width="200" height="40" rx="20" fill="#7c1d2f"/>'
        "</svg>"
    )


def _raise_runway_unavailable(*args, **kwargs) -> str:
    raise RunwayGenerationUnavailable("Runway disabled for regression test")


def _sine_wave_bytes() -> bytes:
    path = Path("voice.wav")
    sample_rate = 16_000
    duration_seconds = 1
    frequency = 440
    frame_count = sample_rate * duration_seconds

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for index in range(frame_count):
            value = int(32767 * 0.2 * math.sin(2 * math.pi * frequency * index / sample_rate))
            wav_file.writeframes(struct.pack("<h", value))

    return path.read_bytes()


def _asset_path(root: Path, storage_url: str) -> Path:
    return root / ".local" / "assets" / storage_url.removeprefix("/assets/")


def _ffprobe_streams(path: Path) -> list[str]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,codec_type",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip().splitlines()
