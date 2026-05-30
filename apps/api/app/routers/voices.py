from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class VoicePreset(BaseModel):
    id: str
    provider: str
    display_name: str
    language: str
    style: str


@router.get("")
def list_voices() -> list[VoicePreset]:
    return [
        VoicePreset(
            id="elevenlabs-default-narrator",
            provider="elevenlabs",
            display_name="Default Narrator",
            language="en",
            style="warm",
        )
    ]
