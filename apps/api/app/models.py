from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ProjectStatus(StrEnum):
    draft = "draft"
    generating = "generating"
    ready = "ready"
    failed = "failed"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    canceled = "canceled"


class JobType(StrEnum):
    image_generation = "image_generation"
    image_to_video = "image_to_video"
    tts = "tts"
    final_export = "final_export"


class MediaType(StrEnum):
    uploaded_image = "uploaded_image"
    generated_image = "generated_image"
    generated_video = "generated_video"
    generated_audio = "generated_audio"
    final_video = "final_video"


class Project(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    status: ProjectStatus = ProjectStatus.draft
    aspect_ratio: str = "9:16"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MediaAsset(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    type: MediaType
    provider: str
    storage_url: str
    mime_type: str
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GenerationJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    job_type: JobType
    status: JobStatus = JobStatus.queued
    provider: str
    provider_job_id: str | None = None
    input: dict[str, object] = Field(default_factory=dict)
    output_asset_id: UUID | None = None
    error_message: str | None = None
    attempts: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProjectDetail(Project):
    media_assets: list[MediaAsset] = Field(default_factory=list)
    jobs: list[GenerationJob] = Field(default_factory=list)
