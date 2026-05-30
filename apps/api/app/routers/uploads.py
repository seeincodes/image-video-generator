from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()


class PresignUploadRequest(BaseModel):
    filename: str
    content_type: str
    project_id: str


class PresignUploadResponse(BaseModel):
    storage_key: str
    presigned_put_url: str
    read_url: str


@router.post("/presign")
def presign_upload(request: PresignUploadRequest) -> PresignUploadResponse:
    storage_key = f"uploads/{request.project_id}/{uuid4()}-{request.filename}"
    placeholder_url = f"https://{settings.s3_bucket_name}.s3.amazonaws.com/{storage_key}"
    return PresignUploadResponse(
        storage_key=storage_key,
        presigned_put_url=placeholder_url,
        read_url=placeholder_url,
    )
