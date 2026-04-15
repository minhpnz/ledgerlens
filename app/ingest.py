#Developed by HenryPhan
"""Ingest pipeline RESUMABLE — parse -> chunk -> embed, có checkpoint theo stage.

Bài toán: ingest tài liệu lớn (parse/OCR/chunk/embed) tốn thời gian; nếu worker
crash giữa chừng, cách ngây thơ phải làm LẠI TỪ ĐẦU (lãng phí) hoặc mất progress.
Giải: mỗi doc là một STATE MACHINE có checkpoint stage; crash → resume() chạy tiếp
từ stage dở, KHÔNG làm lại phần đã xong. Mỗi stage IDEMPOTENT (chạy lại cho cùng
kết quả: chunk id tất định, embed upsert theo key) nên replay an toàn.

Đây là bản in-process (checkpoint in-memory); production đẩy stage vào DB + worker
queue (arq/Celery) và persist checkpoint để sống qua restart — interface giữ nguyên.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable, Dict, List, Optional

from .chunking import chunk_document
from .models import Chunk


class Stage(IntEnum):
    PARSE = 0
    CHUNK = 1
    EMBED = 2
    DONE = 3


@dataclass
class IngestJob:
    doc_id: str
    version: int
    raw_text: str
    stage: Stage = Stage.PARSE
    text: str = ""
    chunks: List[Chunk] = field(default_factory=list)
    error: str = ""


class IngestPipeline:
    def __init__(self,
                 on_chunks: Callable[[List[Chunk]], None],
                 on_embed: Callable[[List[Chunk]], None]) -> None:
        self._on_chunks = on_chunks   # đăng ký chunk vào retriever/bm25
        self._on_embed = on_embed     # embed chunk vào vector store (active spec)
        self._jobs: Dict[str, IngestJob] = {}
        # fault injection cho test: nếu set, ném lỗi khi tới stage này (giả lập crash).
        self._fail_at: Optional[Stage] = None

    def inject_fault(self, stage: Optional[Stage]) -> None:
        self._fail_at = stage

    def submit(self, doc_id: str, version: int, raw_text: str) -> IngestJob:
        job = IngestJob(doc_id=doc_id, version=version, raw_text=raw_text)
        self._jobs[doc_id] = job
        self._advance(job)
        return job

    def resume(self, doc_id: str) -> IngestJob:
        job = self._jobs[doc_id]
        job.error = ""
        self._advance(job)
        return job

    def job(self, doc_id: str) -> IngestJob:
        return self._jobs[doc_id]

    def _advance(self, job: IngestJob) -> None:
        try:
            while job.stage < Stage.DONE:
                if self._fail_at is not None and job.stage == self._fail_at:
                    raise RuntimeError(f"injected fault at stage {job.stage.name}")
                self._run_stage(job)
                job.stage = Stage(job.stage + 1)  # checkpoint SAU khi stage xong
        except Exception as exc:  # noqa: BLE001 — giữ nguyên stage để resume
            job.error = str(exc)

    def _run_stage(self, job: IngestJob) -> None:
        if job.stage == Stage.PARSE:
            job.text = job.raw_text.strip()  # prod: parse PDF/DOCX + OCR
        elif job.stage == Stage.CHUNK:
            job.chunks = chunk_document(job.doc_id, job.version, job.text)
            self._on_chunks(job.chunks)      # idempotent: chunk id tất định
        elif job.stage == Stage.EMBED:
            self._on_embed(job.chunks)       # idempotent: upsert theo key
