from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class JobType(StrEnum):
    image_generation = "image_generation"
    image_to_video = "image_to_video"
    tts = "tts"
    lip_sync = "lip_sync"
    final_export = "final_export"


class WorkerJob(BaseModel):
    id: UUID
    project_id: UUID
    job_type: JobType
    input: dict[str, object]
