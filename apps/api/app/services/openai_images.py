from openai import OpenAI, OpenAIError

from app.core.config import settings
from app.services.storage import decode_base64_image, save_local_asset


class OpenAIImageGenerationUnavailable(RuntimeError):
    pass


class OpenAIImageGenerationFailed(RuntimeError):
    pass


def generate_openai_image(project_id, prompt: str) -> str:
    if not settings.openai_api_key:
        raise OpenAIImageGenerationUnavailable("OPENAI_API_KEY is not configured")

    client = OpenAI(api_key=settings.openai_api_key)
    try:
        result = client.images.generate(
            model=settings.openai_image_model,
            prompt=prompt,
            size="1024x1536",
            n=1,
        )
    except OpenAIError as error:
        raise OpenAIImageGenerationFailed(str(error)) from error

    first_image = result.data[0]
    if not first_image.b64_json:
        raise OpenAIImageGenerationUnavailable("OpenAI image response did not include b64_json")

    image_bytes = decode_base64_image(first_image.b64_json)
    return save_local_asset(project_id=project_id, filename="openai-image.png", content=image_bytes)
