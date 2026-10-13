"""REST API - SKELETON (owner: Member 3). Health + read-only detections, enough for the thin pipeline.

TODO week 6: auth (JWT), admin role, filters (time/type/severity/source), stats, rate limiting (NFR06).
"""

from __future__ import annotations

import os

import psycopg
from fastapi import FastAPI, Query
from psycopg.rows import dict_row

from netguard_common import setup_logging

setup_logging("api")
app = FastAPI(title="NetGuard API", version="0.1.0")


def _conn():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)


@app.get("/health")
def health() -> dict:
    try:
        with _conn() as c:
            c.execute("SELECT 1")
        return {"status": "ok", "db": "ok"}
    except Exception as e:  # report, don't crash: compose healthcheck reads this
        return {"status": "degraded", "db": str(e)[:200]}


@app.get("/api/v1/detections")
def detections(limit: int = Query(50, ge=1, le=500)) -> list[dict]:
    with _conn() as c:
        return c.execute(
            "SELECT detection_id, created_at, type, method, severity, confidence, host(src_ip) AS src_ip, "
            "host(dst_ip) AS dst_ip, window_size_s, features, explanation FROM detections "
            "ORDER BY created_at DESC LIMIT %s",
            (limit,),
        ).fetchall()
