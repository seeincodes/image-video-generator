import json
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from app.core.config import settings
from app.models import GenerationJob, MediaAsset, Project


class StoreState(BaseModel):
    projects: dict[UUID, Project] = {}
    media_assets: dict[UUID, MediaAsset] = {}
    generation_jobs: dict[UUID, GenerationJob] = {}


class JsonStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.state = self._load()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self.state.model_dump_json(indent=2), encoding="utf-8")

    def _load(self) -> StoreState:
        if not self.path.exists():
            return StoreState()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return StoreState.model_validate(data)


store = JsonStore(settings.local_data_path)
