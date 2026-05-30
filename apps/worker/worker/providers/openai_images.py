from worker.models import WorkerJob


class OpenAIImagesProvider:
    def generate_image(self, job: WorkerJob) -> None:
        prompt = job.input.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Image generation requires a non-empty prompt")

        print(f"Would call OpenAI Images for job {job.id}: {prompt[:80]}")


def generate_image(job: WorkerJob) -> None:
    OpenAIImagesProvider().generate_image(job)
