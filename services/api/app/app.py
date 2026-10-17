from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="NetGuard API", version="0.1.0")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )
