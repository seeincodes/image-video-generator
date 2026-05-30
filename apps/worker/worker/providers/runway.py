from worker.models import WorkerJob


class RunwayProvider:
    def generate_video(self, job: WorkerJob) -> None:
        motion_prompt = job.input.get("motion_prompt")
        source_image_asset_id = job.input.get("source_image_asset_id")
        if not isinstance(motion_prompt, str) or not motion_prompt.strip():
            raise ValueError("Image-to-video generation requires a motion prompt")
        if not isinstance(source_image_asset_id, str):
            raise ValueError("Image-to-video generation requires a source image asset")

        print(f"Would call Runway image-to-video for job {job.id}: {motion_prompt[:80]}")


def generate_video(job: WorkerJob) -> None:
    RunwayProvider().generate_video(job)
