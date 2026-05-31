# Image Video Voice App

MVP skeleton for a creator app that turns prompts or uploaded images into short videos with AI voice narration.

## What this includes

- `apps/web`: Next.js editor that creates a project and runs the full mock generation flow.
- `apps/api`: FastAPI API with persistent local JSON storage, project/media/job routes, and mock background job completion.
- `apps/worker`: Python worker skeleton with provider boundaries for OpenAI Images, Runway, Kokoro, ElevenLabs, and FFmpeg export.
- `docs/mvp-spec.md`: product/technical plan.
- `.env.example`: required environment variables.

## Recommended MVP workflow

1. Create project.
2. Generate or upload image.
3. Generate image-to-video clip with Runway.
4. Generate narration with Kokoro.
5. Lip-sync the video to the narration with MuseTalk.
6. Merge video + voice with FFmpeg.
7. Download final MP4.

## Local setup

### Web

```bash
npm install
npm run dev:web
```

### API

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

The API stores local mock data at `.local/data.json` by default. Delete that file to reset local state.

### Worker

```bash
cd apps/worker
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m worker.main
```

## Required provider secrets

- `OPENAI_API_KEY`
- `RUNWAYML_API_SECRET`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`
- `DATABASE_URL`

The app runs in mock mode when provider dependencies or keys are missing. OpenAI image generation, Runway image-to-video generation, Kokoro text-to-speech, MuseTalk lip-sync, and FFmpeg export are connected first:

- Set `OPENAI_API_KEY` and optionally `OPENAI_IMAGE_MODEL` to generate a real image.
- Set `RUNWAYML_API_SECRET` to turn that image into a real video.
- Install Kokoro dependencies to generate real narration locally.
- Configure MuseTalk to lip-sync the generated video to the narration. If MuseTalk is not configured, the app preserves the source video and records a mock lip-sync asset so local development still completes.

Generated files are stored under `.local/assets`. Final export muxes the latest lip-synced video asset with narration when both are local files.

## Local mock MVP demo

1. Start the API:

   ```bash
   cd apps/api
   source .venv/bin/activate
   uvicorn app.main:app --reload
   ```

2. Start the web app:

   ```bash
   npm run dev:web
   ```

3. Open the web app and click `Generate MVP video`.

The button creates a project, runs image/video/voice/lip-sync/export jobs, persists them in `.local/data.json`, and shows the final MP4 when local assets are available.

## OpenAI image generation

1. Copy `.env.example` to `apps/api/.env`.
2. Set:

   ```bash
   OPENAI_API_KEY=...
   OPENAI_IMAGE_MODEL=gpt-image-1
   ```

3. Start the API from `apps/api` so `pydantic-settings` loads the `.env` file.
4. Click `Generate MVP video` in the web app.

When `OPENAI_API_KEY` is configured, the image step calls OpenAI Images and saves a local PNG under `.local/assets/{project_id}`. If the key is missing, the app falls back to a mock `mock://.../image.svg` asset.

## Runway image-to-video

Set this in `apps/api/.env`:

```bash
RUNWAYML_API_SECRET=...
RUNWAY_API_BASE_URL=https://api.dev.runwayml.com
RUNWAY_API_VERSION=2024-11-06
RUNWAY_VIDEO_MODEL=gen4.5
RUNWAY_VIDEO_RATIO=1280:720
RUNWAY_POLL_INTERVAL_SECONDS=5
RUNWAY_POLL_ATTEMPTS=60
```

When `RUNWAYML_API_SECRET` is configured, the video step sends the generated image as a data URI to Runway, polls `/v1/tasks/{task_id}`, downloads the ephemeral output URL, and saves the MP4 under `.local/assets/{project_id}`. If the key is missing, the app falls back to a local mock MP4 rendered from the source image when possible.

## Kokoro text-to-speech

Kokoro is the default open-source TTS provider for narration. It uses Apache-2.0 licensed weights and runs locally without a vendor API key.

```bash
cd apps/api
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional settings in `apps/api/.env`:

```bash
KOKORO_TTS_ENABLED=true
KOKORO_REPO_ID=hexgrad/Kokoro-82M
KOKORO_VOICE=af_heart
KOKORO_LANG_CODE=a
```

The default web flow sends `voice_preset_id=kokoro-af-heart`. When Kokoro is available, the TTS job saves a WAV under `.local/assets/{project_id}` with `provider=kokoro` and `metadata.mode=live`. If Kokoro is disabled or missing, the app falls back to a mock `mock://.../voice.mp3` asset with `provider=mock-kokoro`.

## MuseTalk lip-sync

MuseTalk is the first self-hosted lip-sync backend. It takes the generated video and Kokoro audio, runs MuseTalk inference, and saves a lip-synced MP4 under `.local/assets/{project_id}` with `provider=musetalk`.

MuseTalk is disabled by default because it needs a separate Python 3.10/CUDA environment and downloaded model weights. Local development still completes through `provider=mock-musetalk`, which copies the generated video forward as a `lip_synced_video` asset before final FFmpeg export.

Example API environment settings:

```bash
MUSETALK_ENABLED=true
MUSETALK_REPO_PATH=/opt/MuseTalk
MUSETALK_MODEL_DIR=/opt/MuseTalk/models
MUSETALK_RESULT_DIR=.local/musetalk-results
MUSETALK_PYTHON=/opt/musetalk-venv/bin/python
MUSETALK_USE_FLOAT16=true
MUSETALK_GPU_ID=0
MUSETALK_BATCH_SIZE=8
MUSETALK_TIMEOUT_SECONDS=900
```

Expected MuseTalk setup:

1. Use Python 3.10 and CUDA-compatible PyTorch in the MuseTalk environment.
2. Clone `https://github.com/TMElyralab/MuseTalk`.
3. Run MuseTalk's dependency installation and `download_weights.sh`.
4. Point `MUSETALK_REPO_PATH`, `MUSETALK_MODEL_DIR`, and `MUSETALK_PYTHON` at that environment.

Model weights are intentionally downloaded during setup and are not committed to this repo.

## First implementation tickets

1. Replace local JSON store with Postgres models/migrations.
2. Implement S3 presigned upload/download URLs.
3. Add queue backend: SQS, Redis/BullMQ, or Celery/RQ.
4. Move OpenAI image generation from FastAPI background tasks into the durable worker queue.
5. Move Runway video generation from FastAPI background tasks into the durable worker queue.
6. Move Kokoro and MuseTalk generation into the durable worker queue.
7. Implement FFmpeg export worker.
8. Add auth, quotas, and cost tracking.
