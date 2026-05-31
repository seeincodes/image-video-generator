from pathlib import PurePath
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.models import (
    GenerationJob,
    JobType,
    MediaAsset,
    MediaType,
    Project,
    ProjectDetail,
    ProjectStatus,
)
from app.services.mock_jobs import run_mock_job
from app.services.storage import save_local_asset
from app.store import store

router = APIRouter()
REFERENCE_IMAGE_FILE = File(...)


class CreateProjectRequest(BaseModel):
    title: str
    aspect_ratio: str = "9:16"


class GenerateImageRequest(BaseModel):
    prompt: str
    style: str | None = None
    negative_prompt: str | None = None
    reference_image_asset_id: UUID | None = None


class UploadReferenceImageResponse(BaseModel):
    asset: MediaAsset


class GenerateVideoRequest(BaseModel):
    source_image_asset_id: UUID
    motion_prompt: str
    duration_seconds: int = 5


class GenerateVoiceRequest(BaseModel):
    script: str
    voice_preset_id: str


class ExportRequest(BaseModel):
    generated_video_asset_id: UUID
    audio_asset_id: UUID
    captions_enabled: bool = True


@router.post("")
def create_project(request: CreateProjectRequest) -> Project:
    project = Project(title=request.title, aspect_ratio=request.aspect_ratio)
    store.state.projects[project.id] = project
    store.save()
    return project


@router.get("")
def list_projects() -> list[Project]:
    return list(store.state.projects.values())


@router.get("/{project_id}")
def get_project(project_id: UUID) -> ProjectDetail:
    project = store.state.projects.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectDetail(
        **project.model_dump(),
        media_assets=[
            asset for asset in store.state.media_assets.values() if asset.project_id == project_id
        ],
        jobs=[job for job in store.state.generation_jobs.values() if job.project_id == project_id],
    )


@router.post("/{project_id}/generate-image")
def generate_image(
    project_id: UUID,
    request: GenerateImageRequest,
    background_tasks: BackgroundTasks,
) -> GenerationJob:
    ensure_project(project_id)
    job = GenerationJob(
        project_id=project_id,
        job_type=JobType.image_generation,
        provider="openai",
        input=request.model_dump(mode="json"),
    )
    queue_mock_job(job, background_tasks)
    return job


@router.post("/{project_id}/reference-image")
async def upload_reference_image(
    project_id: UUID,
    file: UploadFile = REFERENCE_IMAGE_FILE,
) -> UploadReferenceImageResponse:
    ensure_project(project_id)
    content_type = file.content_type or "application/octet-stream"
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=400, detail="Reference image must be JPG, PNG, or WebP")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Reference image is empty")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Reference image must be 10MB or smaller")

    filename = PurePath(file.filename or "reference-image").name
    storage_url = save_local_asset(project_id=project_id, filename=filename, content=content)
    asset = MediaAsset(
        project_id=project_id,
        type=MediaType.uploaded_image,
        provider="local-upload",
        storage_url=storage_url,
        mime_type=content_type,
        metadata={"filename": filename, "mode": "reference"},
    )
    store.state.media_assets[asset.id] = asset
    store.save()
    return UploadReferenceImageResponse(asset=asset)


@router.post("/{project_id}/generate-video")
def generate_video(
    project_id: UUID,
    request: GenerateVideoRequest,
    background_tasks: BackgroundTasks,
) -> GenerationJob:
    ensure_project(project_id)
    job = GenerationJob(
        project_id=project_id,
        job_type=JobType.image_to_video,
        provider="runway",
        input=request.model_dump(mode="json"),
    )
    queue_mock_job(job, background_tasks)
    return job


@router.post("/{project_id}/generate-voice")
def generate_voice(
    project_id: UUID,
    request: GenerateVoiceRequest,
    background_tasks: BackgroundTasks,
) -> GenerationJob:
    ensure_project(project_id)
    job = GenerationJob(
        project_id=project_id,
        job_type=JobType.tts,
        provider="kokoro",
        input=request.model_dump(),
    )
    queue_mock_job(job, background_tasks)
    return job


@router.post("/{project_id}/export")
def export_project(
    project_id: UUID,
    request: ExportRequest,
    background_tasks: BackgroundTasks,
) -> GenerationJob:
    ensure_project(project_id)
    job = GenerationJob(
        project_id=project_id,
        job_type=JobType.final_export,
        provider="ffmpeg",
        input=request.model_dump(mode="json"),
    )
    queue_mock_job(job, background_tasks)
    return job


def ensure_project(project_id: UUID) -> None:
    if project_id not in store.state.projects:
        raise HTTPException(status_code=404, detail="Project not found")


def queue_mock_job(job: GenerationJob, background_tasks: BackgroundTasks) -> None:
    project = store.state.projects[job.project_id]
    project.status = ProjectStatus.generating
    store.state.generation_jobs[job.id] = job
    store.save()
    background_tasks.add_task(run_mock_job, job)
