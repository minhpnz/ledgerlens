"""Vector store in-memory, cosine brute-force, có nhận thức ACL metadata + spec.

Khác SentinelLog (phân vùng theo tenant): ở đây ACL phức tạp hơn (dept × clearance)
nên vector store LƯU KÈM dept + sensitivity của mỗi chunk, và search chỉ nhận
candidate; ACL PRE-FILTER do retriever áp TRƯỚC rerank (xem acl.py + retriever.py).
Đồng thời mỗi vector gắn model_version + active_spec để phục vụ zero-downtime reindex:
search chỉ xét vector có active_spec=True.

Production: thay bằng pgvector/Qdrant với HNSW; ACL pre-filter thành WHERE dept=..
AND sensitivity<=.. chạy TRƯỚC toán tử vector; active_spec thành cột lọc.
"""
from __future__ import annotations

from typing import Dict, List

from .embedding import cosine
from .models import Embedding, Sensitivity


class VectorStore:
    def __init__(self) -> None:
        self._items: Dict[str, Embedding] = {}  # key = f"{chunk_id}|{model_version}"

    def upsert(self, emb: Embedding) -> None:
        self._items[f"{emb.chunk_id}|{emb.model_version}"] = emb

    def set_active_spec(self, model_version: str, active: bool) -> int:
        """Bật/tắt active cho toàn bộ vector của một spec. Trả số vector đổi trạng thái.

        Đây là 'công tắc' zero-downtime reindex: gọi để ATOMIC chuyển active giữa
        hai spec (xem reindex.py).
        """
        n = 0
        for e in self._items.values():
            if e.model_version == model_version and e.active_spec != active:
                e.active_spec = active
                n += 1
        return n

    def search(self, query_vec: List[float], model_version: str, limit: int = 50) -> List[Embedding]:
        """Chỉ xét vector active của ĐÚNG spec truy vấn → không trộn version."""
        scored = []
        for e in self._items.values():
            if not e.active_spec or e.model_version != model_version:
                continue
            scored.append((cosine(query_vec, e.vector), e))
        scored.sort(key=lambda se: se[0], reverse=True)
        return [e for _, e in scored[:limit]]

    def active_count(self, model_version: str) -> int:
        return sum(1 for e in self._items.values()
                   if e.active_spec and e.model_version == model_version)

    def __len__(self) -> int:
        return len(self._items)
