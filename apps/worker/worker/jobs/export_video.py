from worker.models import WorkerJob


def export_video(job: WorkerJob) -> None:
    video_asset_id = job.input.get("generated_video_asset_id")
    audio_asset_id = job.input.get("audio_asset_id")
    if not isinstance(video_asset_id, str):
        raise ValueError("Final export requires a generated video asset")
    if not isinstance(audio_asset_id, str):
        raise ValueError("Final export requires an audio asset")

    print(f"Would run FFmpeg final export for job {job.id}")
