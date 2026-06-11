# vibepost - social media scheduling and posting tool
# Copyright (C) 2026  Travis West
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from .config import CORS_ORIGINS, FRONTEND_DIST, IS_PROD, UPLOADS_DIR
from .database import engine, Base, run_migrations
from .models import *  # noqa: register all models
from .scheduler import scheduler, restore_jobs
from .routers import profiles, channels, auth, posts, account

Base.metadata.create_all(bind=engine)
run_migrations()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    restore_jobs()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="vibepost",
    lifespan=lifespan,
    # No public API docs in production
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None,
    openapi_url=None if IS_PROD else "/openapi.json",
)

if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if IS_PROD:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
        )
    return response


@app.get("/api/health")
def health():
    return {"ok": True}


app.include_router(account.router, prefix="/api")
app.include_router(profiles.router, prefix="/api")
app.include_router(channels.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(posts.router, prefix="/api")

# Uploaded media is served publicly at /media/<uuid>.<ext>. This must stay
# publicly reachable: Instagram and Threads ingest media by fetching a URL.
# Filenames are unguessable UUIDs and files are deleted with their posts.
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(UPLOADS_DIR)), name="media")

# Single-container deployment: serve the built frontend if configured.
if FRONTEND_DIST and Path(FRONTEND_DIST).is_dir():
    _dist = Path(FRONTEND_DIST)
    app.mount("/assets", StaticFiles(directory=str(_dist / "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = (_dist / path).resolve()
        if path and candidate.is_relative_to(_dist.resolve()) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html")
