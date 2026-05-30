from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.models import GenerationJob
from app.store import store

router = APIRouter()


@router.get("/{job_id}")
def get_job(job_id: UUID) -> GenerationJob:
    job = store.state.generation_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
