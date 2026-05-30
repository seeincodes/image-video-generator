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
            id="kokoro-af-heart",
            provider="kokoro",
            display_name="Kokoro Heart",
            language="en-US",
            style="warm narrator",
        ),
        VoicePreset(
            id="kokoro-bf-emma",
            provider="kokoro",
            display_name="Kokoro Emma",
            language="en-GB",
            style="clear narrator",
        ),
        VoicePreset(
            id="kokoro-am-onyx",
            provider="kokoro",
            display_name="Kokoro Onyx",
            language="en-US",
            style="deep narrator",
        ),
        VoicePreset(
            id="elevenlabs-default-narrator",
            provider="elevenlabs",
            display_name="Default Narrator",
            language="en",
            style="warm",
        )
    ]
