"""Entrypoint: chạy LedgerLens API với dữ liệu seed.

    ./.venv/bin/python -m uvicorn main:app --port 8090
hoặc:
    ./.venv/bin/python main.py
"""
from __future__ import annotations

from app.api import create_app
from app.seed import build_seeded_service

app = create_app(build_seeded_service())

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8090)
