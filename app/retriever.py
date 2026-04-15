#Developed by HenryPhan
"""Hybrid retriever: BM25 + vector -> RRF -> ACL PRE-FILTER -> rerank.

Thứ tự CỐ Ý (mỗi bước một quyết định senior):
  1. BM25 (khớp chính xác thuật ngữ) + vector (ngữ nghĩa) chạy song song → recall cao.
  2. RRF hợp nhất hai bảng xếp hạng (khác thang score → dùng thứ hạng).
  3. ACL PRE-FILTER: loại tài liệu NGOÀI QUYỀN **TRƯỚC** rerank/generation — không
     post-filter (chống rò rỉ qua ranking/timing/count). Đếm số bị chặn để làm
     'out-of-scope hint' (báo có tài liệu nhưng không lộ nội dung).
  4. Rerank (cross-encoder ở prod) chỉ trên tập ĐÃ được phép → precision cao.

Trả (danh sách RetrievedChunk đã rerank, số candidate bị ACL chặn).
"""
from __future__ import annotations

from typing import Callable, Dict, List, Tuple

from .acl import can_access
from .bm25 import BM25Index
from .embedding import Embedder
from .fusion import rrf_fuse
from .models import Chunk, Identity, RetrievedChunk, Sensitivity
from .rerank import Reranker
from .vectorstore import VectorStore


class Retriever:
    def __init__(self, bm25: BM25Index, vstore: VectorStore, reranker: Reranker) -> None:
        self._bm25 = bm25
        self._vstore = vstore
        self._reranker = reranker
        self._chunks: Dict[str, Chunk] = {}
        self._doc_meta: Dict[str, Tuple[str, Sensitivity]] = {}  # doc_id -> (dept, sensitivity)

    # --- registry (service gọi khi ingest) ---
    def register_doc(self, doc_id: str, dept: str, sensitivity: Sensitivity) -> None:
        self._doc_meta[doc_id] = (dept, sensitivity)

    def register_chunk(self, chunk: Chunk) -> None:
        self._chunks[chunk.id] = chunk
        self._bm25.add(chunk.id, chunk.text)

    def doc_meta(self, doc_id: str) -> Tuple[str, Sensitivity]:
        return self._doc_meta[doc_id]

    def all_chunks(self) -> List[Chunk]:
        return list(self._chunks.values())

    def search(self, identity: Identity, query: str, active_embedder: Embedder,
               candidate_k: int = 50, top_k: int = 8) -> Tuple[List[RetrievedChunk], int]:
        # 1) hai retriever song song.
        lex = [key for key, _ in self._bm25.search(query, limit=candidate_k)]
        qv = active_embedder.embed(query)
        vec_hits = self._vstore.search(qv, active_embedder.version(), limit=candidate_k)
        vec = [e.chunk_id for e in vec_hits]

        # 2) RRF fuse.
        fused = rrf_fuse([lex, vec], k=60, limit=candidate_k)

        # 3) ACL PRE-FILTER (trước rerank).
        allowed: List[RetrievedChunk] = []
        blocked = 0
        for chunk_id, score in fused:
            chunk = self._chunks.get(chunk_id)
            if chunk is None:
                continue
            dept, sens = self._doc_meta[chunk.doc_id]
            if not can_access(identity, dept, sens):
                blocked += 1
                continue
            allowed.append(RetrievedChunk(chunk=chunk, dept=dept, sensitivity=sens,
                                          score=score, source="fused"))

        # 4) rerank chỉ trên tập được phép.
        reranked = self._reranker.rerank(query, allowed, top_k=top_k)
        return reranked, blocked
