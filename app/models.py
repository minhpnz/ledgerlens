"""Kiểu dữ liệu lõi của LedgerLens.

Mô hình bảo mật (đọc kỹ — đây là xương sống threat model):
- Sensitivity/clearance là thang 0..3: 0=public, 1=internal, 2=confidential, 3=restricted.
- Một user THẤY được một document khi: user.clearance >= doc.sensitivity  VÀ
  (doc.dept == user.dept  HOẶC  doc.sensitivity == PUBLIC).  → xem acl.can_access().
- TenantID/dept/clearance của người hỏi LUÔN đến từ Identity đã xác thực, KHÔNG từ
  input client (chống privilege escalation), giống hệt SentinelLog.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional


class Sensitivity(IntEnum):
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    RESTRICTED = 3


@dataclass(frozen=True)
class Identity:
    """Danh tính đã xác thực của người hỏi. dept + clearance KHÔNG từ client."""
    actor: str
    dept: str
    clearance: Sensitivity


@dataclass
class Document:
    id: str
    dept: str
    sensitivity: Sensitivity
    title: str
    # current_version trỏ tới version đang active (zero-downtime versioning).
    current_version: int = 1


@dataclass
class Chunk:
    """Một mẩu văn bản của document, đơn vị retrieval + citation.

    section_path (vd '2.1 > Retention') cho phép citation chính xác đến điều khoản.
    page_ref để trích dẫn số trang. version để gắn chunk với đúng phiên bản doc.
    """
    id: str
    doc_id: str
    version: int
    section_path: str
    text: str
    page_ref: str = ""

    def ref(self) -> str:
        """Con trỏ ổn định để cite: 'doc:<doc_id>#<section_path>'."""
        return f"doc:{self.doc_id}#{self.section_path}"


@dataclass
class Embedding:
    """Vector của một chunk, gắn với model_version + cờ active_spec.

    active_spec là chìa khoá ZERO-DOWNTIME REINDEX: khi đổi embedding model, ta
    build spec mới (active_spec=False) song song, rồi ĐỔI ATOMIC sang spec mới.
    Query luôn chỉ đọc active spec → không có cửa sổ rỗng, không trộn version.
    """
    chunk_id: str
    doc_id: str
    dept: str
    sensitivity: Sensitivity
    vector: List[float]
    model_version: str
    active_spec: bool = True


@dataclass
class RetrievedChunk:
    chunk: Chunk
    dept: str
    sensitivity: Sensitivity
    score: float
    source: str = ""  # "bm25" | "vector" | "fused" | "reranked" (để debug/observability)


@dataclass
class Answer:
    question: str
    text: str = ""
    citations: List[str] = field(default_factory=list)
    refused: bool = False
    reason: str = ""
    out_of_scope_hint: bool = False   # có tài liệu liên quan nhưng NGOÀI QUYỀN (không lộ nội dung)
    injection_flagged: bool = False
