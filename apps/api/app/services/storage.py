import base64
import mimetypes
import shutil
from pathlib import Path
from uuid import UUID, uuid4

LOCAL_ASSET_ROOT = ".local/assets"

def save_local_asset(
    *,
    project_id: UUID,
    filename: str,
    content: bytes,
    local_root: str = LOCAL_ASSET_ROOT,
) -> str:
    asset_dir = Path(local_root) / str(project_id)
    asset_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name
    path = asset_dir / f"{uuid4()}-{safe_name}"
    path.write_bytes(content)
    return f"/assets/{project_id}/{path.name}"


def decode_base64_image(image_base64: str) -> bytes:
    return base64.b64decode(image_base64)


def read_local_asset(storage_url: str, local_root: str = LOCAL_ASSET_ROOT) -> tuple[bytes, str]:
    if not storage_url.startswith("/assets/"):
        raise ValueError("Only local /assets URLs can be read from disk")

    relative_path = storage_url.removeprefix("/assets/")
    path = Path(local_root) / relative_path
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return path.read_bytes(), content_type


def delete_local_project_assets(project_id: UUID, local_root: str = LOCAL_ASSET_ROOT) -> None:
    asset_dir = Path(local_root) / str(project_id)
    if asset_dir.exists():
        shutil.rmtree(asset_dir)


def to_data_uri(content: bytes, content_type: str) -> str:
    encoded = base64.b64encode(content).decode("utf-8")
    return f"data:{content_type};base64,{encoded}"
