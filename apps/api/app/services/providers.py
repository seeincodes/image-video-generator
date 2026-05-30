from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class ProviderReadiness:
    openai_images: bool
    runway: bool
    kokoro_tts: bool
    elevenlabs: bool
    storage: bool

    @property
    def live_generation_ready(self) -> bool:
        return self.openai_images and self.runway and self.kokoro_tts and self.storage


def get_provider_readiness() -> ProviderReadiness:
    return ProviderReadiness(
        openai_images=bool(settings.openai_api_key),
        runway=bool(settings.runwayml_api_secret),
        kokoro_tts=settings.kokoro_tts_enabled,
        elevenlabs=bool(settings.elevenlabs_api_key),
        storage=bool(settings.s3_bucket_name),
    )
