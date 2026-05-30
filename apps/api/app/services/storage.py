import base64
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
    path = asset_dir / f"{uuid4()}-{filename}"
    path.write_bytes(content)
    return f"/assets/{project_id}/{path.name}"


def decode_base64_image(image_base64: str) -> bytes:
    return base64.b64decode(image_base64)
