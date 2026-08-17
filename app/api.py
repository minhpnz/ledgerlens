"""Lớp FastAPI MỎNG bọc LedgerLensService (mọi logic ở app/service.py).

Vì sao FastAPI (không Flask/Django): async-native (hợp việc gọi LLM/embedding I/O-
bound), type-safe qua pydantic (validate request tự động), OpenAPI docs miễn phí —
đúng nhu cầu một API service AI. Django nặng (ORM/admin) không cần; Flask thiếu
async + validation sẵn.

Auth: Bearer token -> Identity (dept/clearance) do service.identities phân giải.
Không endpoint nào lấy dept/clearance từ body (chống privilege escalation).
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from .models import Identity, Sensitivity
from .service import LedgerLensService
from . import mcp


class QueryReq(BaseModel):
    question: str


class IngestReq(BaseModel):
    doc_id: str
    dept: str
    sensitivity: int  # 0..3
    title: str
    text: str


def create_app(service: LedgerLensService) -> FastAPI:
    app = FastAPI(title="LedgerLens", version="0.1.0")

    def identity_of(authorization: Optional[str] = Header(default=None)) -> Identity:
        token = ""
        if authorization and authorization.startswith("Bearer "):
            token = authorization[len("Bearer "):].strip()
        ident = service.identities.resolve(token)
        if ident is None:
            raise HTTPException(status_code=401, detail="unauthorized")
        return ident

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/stats")
    def stats():
        return service.stats()

    @app.post("/v1/query")
    def query(req: QueryReq, ident: Identity = Depends(identity_of)):
        ans = service.query(ident, req.question)
        return ans.__dict__

    @app.post("/v1/ingest")
    def ingest(req: IngestReq, ident: Identity = Depends(identity_of)):
        if ident.clearance < Sensitivity.RESTRICTED:  # chỉ admin (clearance cao nhất) được ingest
            raise HTTPException(status_code=403, detail="forbidden: ingest requires admin clearance")
        job = service.ingest_document(req.doc_id, req.dept, Sensitivity(req.sensitivity),
                                      req.title, req.text)
        return {"doc_id": job.doc_id, "stage": job.stage.name, "error": job.error,
                "chunks": len(job.chunks)}

    @app.get("/v1/analytics")
    def analytics(ident: Identity = Depends(identity_of)):
        if ident.clearance < Sensitivity.RESTRICTED:
            raise HTTPException(status_code=403, detail="forbidden")
        return service.warehouse.report()

    @app.get("/v1/audit/verify")
    def audit_verify(ident: Identity = Depends(identity_of)):
        if ident.clearance < Sensitivity.RESTRICTED:
            raise HTTPException(status_code=403, detail="forbidden")
        ok, seq = service.audit.verify()
        return {"intact": ok, "broken_at_seq": seq, "head": service.audit.head(),
                "records": len(service.audit)}

    # MCP-style tool endpoints (Claude/agent connect).
    app.include_router(mcp.build_router(service, identity_of))
    return app
