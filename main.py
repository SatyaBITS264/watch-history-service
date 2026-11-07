
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import os
import sqlite3

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DB_PATH = Path("/data/history.db")
CATALOG_URL = os.getenv("CATALOG_URL", "http://127.0.0.1:8001")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@asynccontextmanager
async def lifespan(app: FastAPI):
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watch_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                movie_id INTEGER NOT NULL,
                watched_at TEXT NOT NULL
            )
        """)
    yield


app = FastAPI(
    title="Watch History Service",
    version="1.0.0",
    lifespan=lifespan,
)


class WatchRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    movie_id: int = Field(gt=0)


@app.get("/health")
def health():
    return {"service": "watch-history", "status": "ok"}


@app.post("/history", status_code=201)
def record_watch(request: WatchRequest):
    try:
        response = requests.get(
            f"{CATALOG_URL}/movies/{request.movie_id}",
            timeout=3,
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail="Movie Catalog Service is unavailable",
        )

    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Movie does not exist in the catalog",
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail="Unexpected response from Movie Catalog Service",
        )

    watched_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO watch_history
               (user_id, movie_id, watched_at)
               VALUES (?, ?, ?)""",
            (request.user_id, request.movie_id, watched_at),
        )
        row = conn.execute(
            "SELECT * FROM watch_history WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()

    return dict(row)


@app.get("/history/{user_id}")
def get_history(user_id: str):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM watch_history
               WHERE user_id = ?
               ORDER BY id DESC""",
            (user_id,),
        ).fetchall()

    return [dict(row) for row in rows]
