from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class ProviderReadiness:
    openai_images: bool
    runway: bool
    kokoro_tts: bool
    musetalk_lipsync: bool
    elevenlabs: bool
    storage: bool

    @property
    def live_generation_ready(self) -> bool:
        return (
            self.openai_images
            and self.runway
            and self.kokoro_tts
            and self.musetalk_lipsync
            and self.storage
        )


def get_provider_readiness() -> ProviderReadiness:
    return ProviderReadiness(
        openai_images=bool(settings.openai_api_key),
        runway=bool(settings.runwayml_api_secret),
        kokoro_tts=settings.kokoro_tts_enabled,
        musetalk_lipsync=bool(settings.musetalk_enabled)
        and bool(settings.musetalk_repo_path)
        and bool(settings.musetalk_model_dir),
        elevenlabs=bool(settings.elevenlabs_api_key),
        storage=bool(settings.s3_bucket_name),
    )
