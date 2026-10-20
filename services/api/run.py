"""Local development entry point; Docker continues to supply its own environment."""

import argparse
from pathlib import Path

import uvicorn

API_DIR = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local API with reload and an explicit environment file.")
    parser.add_argument("--env-file", type=Path, default=(API_DIR / "../../.env").resolve())
    parser.add_argument("--port", type=int, default=8000)
    arguments = parser.parse_args()
    if not arguments.env_file.is_file():
        parser.error("Environment file not found. Copy .env.example to .env in the repository root or pass --env-file.")
    uvicorn.run(
        "app.app:app",
        app_dir=str(API_DIR),
        host="127.0.0.1",
        port=arguments.port,
        reload=True,
        reload_dirs=[str(API_DIR / "app")],
        env_file=str(arguments.env_file),
    )


if __name__ == "__main__":
    main()
