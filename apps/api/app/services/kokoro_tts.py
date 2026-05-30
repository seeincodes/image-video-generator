import io
from functools import lru_cache
from uuid import UUID

from app.core.config import settings
from app.services.storage import save_local_asset

KOKORO_SAMPLE_RATE = 24000

KOKORO_VOICES = {
    "kokoro-af-heart": ("af_heart", "a"),
    "kokoro-af-sky": ("af_sky", "a"),
    "kokoro-am-adam": ("am_adam", "a"),
    "kokoro-am-onyx": ("am_onyx", "a"),
    "kokoro-bf-emma": ("bf_emma", "b"),
    "kokoro-bm-george": ("bm_george", "b"),
}


class KokoroTTSUnavailable(RuntimeError):
    pass


class KokoroTTSFailed(RuntimeError):
    pass


def generate_kokoro_speech(
    *,
    project_id: UUID,
    script: str,
    voice_preset_id: str,
) -> tuple[str, float, dict[str, object]]:
    if not settings.kokoro_tts_enabled:
        raise KokoroTTSUnavailable("KOKORO_TTS_ENABLED is false")

    voice_id, lang_code = _resolve_voice(voice_preset_id)

    try:
        import numpy as np
        import soundfile as sf

        pipeline = _get_pipeline(lang_code)
        audio_chunks = []
        for _graphemes, _phonemes, audio in pipeline(script, voice=voice_id):
            audio_chunks.append(np.asarray(audio, dtype=np.float32))
    except KokoroTTSUnavailable:
        raise
    except ImportError as error:
        raise KokoroTTSUnavailable("kokoro audio dependencies are not installed") from error
    except Exception as error:
        raise KokoroTTSFailed(str(error)) from error

    if not audio_chunks:
        raise KokoroTTSFailed("Kokoro did not return audio")

    audio_array = np.concatenate(audio_chunks)
    audio_buffer = io.BytesIO()
    sf.write(audio_buffer, audio_array, KOKORO_SAMPLE_RATE, format="WAV")
    audio_bytes = audio_buffer.getvalue()
    duration_seconds = len(audio_array) / KOKORO_SAMPLE_RATE

    storage_url = save_local_asset(
        project_id=project_id,
        filename="kokoro-voice.wav",
        content=audio_bytes,
    )
    metadata = {
        "script": script,
        "voice_preset_id": voice_preset_id,
        "kokoro_voice": voice_id,
        "kokoro_lang_code": lang_code,
        "mode": "live",
    }
    return storage_url, duration_seconds, metadata


def _resolve_voice(voice_preset_id: str) -> tuple[str, str]:
    if voice_preset_id in KOKORO_VOICES:
        return KOKORO_VOICES[voice_preset_id]
    return settings.kokoro_voice, settings.kokoro_lang_code


@lru_cache(maxsize=8)
def _get_pipeline(lang_code: str):
    try:
        from kokoro import KPipeline
    except ImportError as error:
        raise KokoroTTSUnavailable("kokoro is not installed") from error

    return KPipeline(lang_code=lang_code, repo_id=settings.kokoro_repo_id)
