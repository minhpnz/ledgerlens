#Developed by HenryPhan
"""Entrypoint: run the LedgerLens API with seeded data.

    ./.venv/bin/python -m uvicorn main:app --port 8090
or:
    ./.venv/bin/python main.py
"""
from __future__ import annotations

from app.api import create_app
from app.seed import build_seeded_service

app = create_app(build_seeded_service())

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8090)
