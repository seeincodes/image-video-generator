# Image Video Voice App

MVP skeleton for a creator app that turns prompts or uploaded images into short videos with AI voice narration.

## What this includes

- `apps/web`: Next.js editor that creates a project and runs the full mock generation flow.
- `apps/api`: FastAPI API with persistent local JSON storage, project/media/job routes, and mock background job completion.
- `apps/worker`: Python worker skeleton with provider boundaries for OpenAI Images, Runway, ElevenLabs, and FFmpeg export.
- `docs/mvp-spec.md`: product/technical plan.
- `.env.example`: required environment variables.

## Recommended MVP workflow

1. Create project.
2. Generate or upload image.
3. Generate image-to-video clip with Runway.
4. Generate narration with ElevenLabs.
5. Merge video + voice with FFmpeg.
6. Download final MP4.

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
- `ELEVENLABS_API_KEY`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`
- `DATABASE_URL`

The app runs in mock mode without provider keys. OpenAI image generation is connected first: set `OPENAI_API_KEY` and optionally `OPENAI_IMAGE_MODEL` to generate a real image, store it under `.local/assets`, and display it in the web preview. Video, voice, and final export still use mock assets until Runway, ElevenLabs, and FFmpeg are connected.

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

The button creates a project, runs mock image/video/voice/export jobs, persists them in `.local/data.json`, and shows the final `mock://.../final.mp4` asset URL.

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

## First implementation tickets

1. Replace local JSON store with Postgres models/migrations.
2. Implement S3 presigned upload/download URLs.
3. Add queue backend: SQS, Redis/BullMQ, or Celery/RQ.
4. Move OpenAI image generation from FastAPI background tasks into the durable worker queue.
5. Implement Runway image-to-video generation and polling.
6. Implement ElevenLabs text-to-speech.
7. Implement FFmpeg export worker.
8. Add upload-image path in the web editor.
9. Add auth, quotas, and cost tracking.
