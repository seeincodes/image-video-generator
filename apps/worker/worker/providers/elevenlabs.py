from worker.models import WorkerJob


class ElevenLabsProvider:
    def generate_speech(self, job: WorkerJob) -> None:
        script = job.input.get("script")
        voice_preset_id = job.input.get("voice_preset_id")
        if not isinstance(script, str) or not script.strip():
            raise ValueError("TTS generation requires a script")
        if not isinstance(voice_preset_id, str):
            raise ValueError("TTS generation requires a voice preset")

        print(f"Would call ElevenLabs TTS for job {job.id}: {script[:80]}")


def generate_speech(job: WorkerJob) -> None:
    ElevenLabsProvider().generate_speech(job)
