from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str | None = None
    runwayml_api_secret: str | None = None
    runway_api_base_url: str = "https://api.dev.runwayml.com"
    runway_api_version: str = "2024-11-06"
    runway_video_model: str = "gen4.5"
    runway_video_ratio: str = "1280:720"
    elevenlabs_api_key: str | None = None
    s3_bucket_name: str = "image-video-voice-dev"
    aws_region: str = "us-east-1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
