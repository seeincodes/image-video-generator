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
    elevenlabs_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
