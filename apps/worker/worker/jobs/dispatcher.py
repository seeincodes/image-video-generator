from worker.jobs.export_video import export_video
from worker.models import JobType, WorkerJob
from worker.providers.elevenlabs import generate_speech
from worker.providers.musetalk import lip_sync
from worker.providers.openai_images import generate_image
from worker.providers.runway import generate_video


def dispatch_job(job: WorkerJob) -> None:
    match job.job_type:
        case JobType.image_generation:
            generate_image(job)
        case JobType.image_to_video:
            generate_video(job)
        case JobType.tts:
            generate_speech(job)
        case JobType.lip_sync:
            lip_sync(job)
        case JobType.final_export:
            export_video(job)
