from worker.jobs.dispatcher import dispatch_job
from worker.models import WorkerJob


def process_job(job: WorkerJob) -> None:
    dispatch_job(job)


if __name__ == "__main__":
    print("Worker skeleton ready. Connect this process to SQS, Redis, or Celery.")
