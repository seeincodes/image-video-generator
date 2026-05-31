from worker.models import WorkerJob


class MuseTalkProvider:
    def lip_sync(self, job: WorkerJob) -> None:
        generated_video_asset_id = job.input.get("generated_video_asset_id")
        audio_asset_id = job.input.get("audio_asset_id")
        if not isinstance(generated_video_asset_id, str):
            raise ValueError("Lip-sync requires a generated video asset")
        if not isinstance(audio_asset_id, str):
            raise ValueError("Lip-sync requires an audio asset")

        print(f"Would run MuseTalk lip-sync for job {job.id}")


def lip_sync(job: WorkerJob) -> None:
    MuseTalkProvider().lip_sync(job)
