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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

_APP_DIR = Path(__file__).resolve().parent
load_dotenv(_APP_DIR.parent / ".env")

from .database import engine, Base
from .models import *  # noqa: register all models
from .scheduler import scheduler
from .routers import profiles, channels, auth, posts

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="vibepost", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profiles.router, prefix="/api")
app.include_router(channels.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(posts.router, prefix="/api")

# Serve uploaded media at /media/filename (no /api prefix, so meta callbacks can reach it)
uploads_dir = _APP_DIR.parent / "uploads"
uploads_dir.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory=str(uploads_dir)), name="media")
