from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import jobs, projects, providers, research, uploads, voices

app = FastAPI(title="Image Video Voice API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/assets", StaticFiles(directory=".local/assets", check_dir=False), name="assets")

app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
app.include_router(voices.router, prefix="/voices", tags=["voices"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(providers.router, prefix="/providers", tags=["providers"])
app.include_router(research.router, prefix="/research", tags=["research"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
