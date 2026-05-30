from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/image_video_voice"
    local_data_path: str = ".local/data.json"
    s3_bucket_name: str = "image-video-voice-dev"
    aws_region: str = "us-east-1"
    openai_api_key: str | None = None
    openai_image_model: str = "gpt-image-1"
    runwayml_api_secret: str | None = None
    runway_api_base_url: str = "https://api.dev.runwayml.com"
    runway_api_version: str = "2024-11-06"
    runway_video_model: str = "gen4.5"
    runway_video_ratio: str = "1280:720"
    runway_poll_interval_seconds: float = 5.0
    runway_poll_attempts: int = 60
    elevenlabs_api_key: str | None = None
    kokoro_tts_enabled: bool = True
    kokoro_repo_id: str = "hexgrad/Kokoro-82M"
    kokoro_voice: str = "af_heart"
    kokoro_lang_code: str = "a"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
