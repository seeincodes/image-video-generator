from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str | None = None
    runwayml_api_secret: str | None = None
    elevenlabs_api_key: str | None = None
    s3_bucket_name: str = "image-video-voice-dev"
    aws_region: str = "us-east-1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
