"""Audit trail append-only, HASH-CHAINED (tamper-evident) — cho kiểm toán.

Giống SentinelLog: mỗi bản ghi chứa hash bản ghi trước → sửa/xoá giữa chuỗi làm
Verify() gãy. Với LedgerLens, mỗi truy vấn ghi: ai hỏi, thấy tài liệu nào (doc ids),
answer_hash, có bị từ chối/injection không → bằng chứng compliance.

Giới hạn (nói được khi phỏng vấn): hash-chain KHÔNG tự chống truncate đuôi → cần
neo (anchor) head định kỳ ra WORM (S3 Object Lock) — chừa hook head().
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


def _genesis() -> str:
    return hashlib.sha256(b"ledgerlens-audit-genesis").hexdigest()


@dataclass
class AuditRecord:
    seq: int
    actor: str
    dept: str
    action: str          # "query" | "reindex" | ...
    query_text: str
    retrieved_doc_ids: List[str]
    answer_hash: str
    refused: bool
    at: str
    prev_hash: str
    hash: str = ""


class AuditLog:
    def __init__(self) -> None:
        self._records: List[AuditRecord] = []
        self._last = _genesis()
        self._seq = 0

    def append(self, actor: str, dept: str, action: str, query_text: str,
               retrieved_doc_ids: List[str], answer_text: str, refused: bool) -> AuditRecord:
        self._seq += 1
        r = AuditRecord(
            seq=self._seq, actor=actor, dept=dept, action=action,
            query_text=query_text, retrieved_doc_ids=list(retrieved_doc_ids),
            answer_hash=hashlib.sha256(answer_text.encode()).hexdigest()[:16],
            refused=refused, at=datetime.now(timezone.utc).isoformat(),
            prev_hash=self._last,
        )
        r.hash = self._hash_record(r)
        self._last = r.hash
        self._records.append(r)
        return r

    def verify(self) -> tuple[bool, int]:
        prev = _genesis()
        for r in self._records:
            if r.prev_hash != prev or r.hash != self._hash_record(r):
                return False, r.seq
            prev = r.hash
        return True, 0

    def head(self) -> str:
        return self._last

    def __len__(self) -> int:
        return len(self._records)

    @staticmethod
    def _hash_record(r: AuditRecord) -> str:
        data = "|".join([
            str(r.seq), r.actor, r.dept, r.action, r.query_text,
            ",".join(r.retrieved_doc_ids), r.answer_hash, str(r.refused),
            r.at, r.prev_hash,
        ])
        return hashlib.sha256(data.encode()).hexdigest()
