# MVP Technical Spec

## Architecture

- Frontend: Next.js.
- Backend: FastAPI.
- Worker: Python process connected to SQS, Redis, Celery, or another queue.
- Storage: S3.
- Database: Postgres.
- Image generation: OpenAI Images API.
- Image-to-video: Runway first, Luma later.
- TTS: Kokoro first, with commercial APIs as optional later providers.
- Export: FFmpeg.

## Data model

### projects

- `id`
- `user_id`
- `title`
- `status`
- `aspect_ratio`
- `created_at`
- `updated_at`

### media_assets

- `id`
- `project_id`
- `type`
- `provider`
- `storage_url`
- `mime_type`
- `duration_seconds`
- `width`
- `height`
- `metadata_json`
- `created_at`

### generation_jobs

- `id`
- `project_id`
- `job_type`
- `status`
- `provider`
- `provider_job_id`
- `input_json`
- `output_asset_id`
- `error_message`
- `attempts`
- `created_at`
- `updated_at`

## API

- `POST /projects`
- `GET /projects`
- `GET /projects/{project_id}`
- `POST /uploads/presign`
- `GET /voices`
- `GET /providers/readiness`
- `POST /projects/{project_id}/generate-image`
- `POST /projects/{project_id}/generate-video`
- `POST /projects/{project_id}/generate-voice`
- `POST /projects/{project_id}/export`
- `GET /jobs/{job_id}`

## Job flow

1. API creates a `generation_jobs` record.
2. API enqueues job.
3. Worker picks up job and calls provider.
4. Worker stores provider output in S3.
5. Worker creates a `media_assets` record.
6. Worker marks job `succeeded` or `failed`.
7. Web polls job status and updates preview.

## Current skeleton behavior

The current skeleton includes a local mock mode:

- `apps/api` persists projects, jobs, and media assets to `.local/data.json`.
- Generation routes enqueue FastAPI background tasks.
- OpenAI image generation uses the real Images API when `OPENAI_API_KEY` is present.
- Runway image-to-video uses the real API when `RUNWAYML_API_SECRET` is present.
- Voice and export jobs currently create `mock://...` media assets.
- `apps/web` runs the guided flow from a single button.

This proves the orchestration shape before paid provider keys are connected.

## MVP constraints

- Single-scene video only.
- 5-10 second generated clips.
- App-owned provider keys.
- Preset voices only.
- No voice cloning.
- No full timeline editor.

## Future upgrades

- Multi-scene timeline.
- Caption styles.
- Background music.
- Voice library.
- Luma fallback.
- User quotas and billing.
- Provider cost dashboard.
