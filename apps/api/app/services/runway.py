import time
from typing import Any
from uuid import UUID

import httpx

from app.core.config import settings
from app.models import MediaAsset
from app.services.storage import read_local_asset, save_local_asset, to_data_uri


class RunwayGenerationUnavailable(RuntimeError):
    pass


class RunwayGenerationFailed(RuntimeError):
    pass


def generate_runway_video(
    *,
    project_id: UUID,
    source_image: MediaAsset,
    motion_prompt: str,
    duration_seconds: int,
) -> str:
    if not settings.runwayml_api_secret:
        raise RunwayGenerationUnavailable("RUNWAYML_API_SECRET is not configured")

    prompt_image = _prompt_image_from_asset(source_image)
    headers = {
        "Authorization": f"Bearer {settings.runwayml_api_secret}",
        "Content-Type": "application/json",
        "X-Runway-Version": settings.runway_api_version,
    }
    payload = {
        "model": settings.runway_video_model,
        "promptImage": prompt_image,
        "promptText": motion_prompt,
        "ratio": settings.runway_video_ratio,
        "duration": duration_seconds,
    }

    with httpx.Client(timeout=120) as client:
        try:
            create_response = client.post(
                f"{settings.runway_api_base_url}/v1/image_to_video",
                headers=headers,
                json=payload,
            )
            create_response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise RunwayGenerationFailed(_format_runway_http_error(error)) from error
        task_id = _extract_task_id(create_response.json())
        task = _wait_for_task(client, headers, task_id)
        output_url = _extract_output_url(task)
        try:
            video_response = client.get(output_url)
            video_response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise RunwayGenerationFailed(_format_runway_http_error(error)) from error

    return save_local_asset(
        project_id=project_id,
        filename="runway-video.mp4",
        content=video_response.content,
    )


def _prompt_image_from_asset(source_image: MediaAsset) -> str:
    if source_image.storage_url.startswith("http://") or source_image.storage_url.startswith("https://"):
        return source_image.storage_url
    if source_image.storage_url.startswith("/assets/"):
        content, content_type = read_local_asset(source_image.storage_url)
        return to_data_uri(content, content_type)
    raise RunwayGenerationUnavailable("Runway requires a live URL or local generated image asset")


def _extract_task_id(response_json: dict[str, Any]) -> str:
    task_id = response_json.get("id")
    if not isinstance(task_id, str):
        raise RunwayGenerationFailed("Runway response did not include task id")
    return task_id


def _wait_for_task(
    client: httpx.Client,
    headers: dict[str, str],
    task_id: str,
) -> dict[str, Any]:
    for _ in range(settings.runway_poll_attempts):
        response = client.get(
            f"{settings.runway_api_base_url}/v1/tasks/{task_id}",
            headers=headers,
        )
        response.raise_for_status()
        task = response.json()
        status = task.get("status")
        if status == "SUCCEEDED":
            return task
        if status in {"FAILED", "CANCELLED"}:
            raise RunwayGenerationFailed(f"Runway task {task_id} ended with status {status}")
        time.sleep(settings.runway_poll_interval_seconds)

    raise RunwayGenerationFailed(f"Runway task {task_id} did not finish before timeout")


def _extract_output_url(task: dict[str, Any]) -> str:
    output = task.get("output")
    if not isinstance(output, list) or not output or not isinstance(output[0], str):
        raise RunwayGenerationFailed("Runway task did not include an output URL")
    return output[0]


def _format_runway_http_error(error: httpx.HTTPStatusError) -> str:
    return f"Runway API returned {error.response.status_code}: {error.response.text}"
