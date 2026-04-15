#Developed by HenryPhan
"""LedgerLensService — orchestrator framework-agnostic (api.py chỉ là lớp mỏng).

Nối: ingest (resumable) -> retriever (hybrid + ACL pre-filter + rerank) -> rag
(grounded + citation) + audit (hash-chain) + warehouse (analytics) + reindex
(zero-downtime). Mọi truy vấn đi qua Identity đã xác thực và được audit + đo.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .audit import AuditLog
from .bm25 import BM25Index
from .embedding import Embedder, HashEmbedder
from .identity import IdentityResolver
from .ingest import IngestPipeline, IngestJob, Stage
from .models import Answer, Chunk, Document, Embedding, Identity, Sensitivity
from .rag import generate_answer
from .reindex import embed_spec
from .rerank import LexicalReranker
from .retriever import Retriever
from .vectorstore import VectorStore
from .warehouse import Warehouse


class LedgerLensService:
    def __init__(self, embedder: Optional[Embedder] = None,
                 min_score: float = 0.1, candidate_k: int = 50, top_k: int = 8) -> None:
        base = embedder or HashEmbedder(dim=256, seed="v1")
        self._embedders: Dict[str, Embedder] = {base.version(): base}
        self._active_version = base.version()

        self._vstore = VectorStore()
        self._bm25 = BM25Index()
        self._retriever = Retriever(self._bm25, self._vstore, LexicalReranker())
        self._docs: Dict[str, Document] = {}
        self._pipeline = IngestPipeline(on_chunks=self._on_chunks, on_embed=self._on_embed)

        self.audit = AuditLog()
        self.warehouse = Warehouse()
        self.identities = IdentityResolver()

        self._min_score = min_score
        self._candidate_k = candidate_k
        self._top_k = top_k

    # --- ingest ---
    def ingest_document(self, doc_id: str, dept: str, sensitivity: Sensitivity,
                        title: str, text: str) -> IngestJob:
        self._docs[doc_id] = Document(id=doc_id, dept=dept, sensitivity=sensitivity, title=title)
        self._retriever.register_doc(doc_id, dept, sensitivity)
        return self._pipeline.submit(doc_id, version=1, raw_text=text)

    def resume_ingest(self, doc_id: str) -> IngestJob:
        return self._pipeline.resume(doc_id)

    def _on_chunks(self, chunks: List[Chunk]) -> None:
        for c in chunks:
            self._retriever.register_chunk(c)

    def _on_embed(self, chunks: List[Chunk]) -> None:
        emb = self._active_embedder()
        for c in chunks:
            dept, sens = self._retriever.doc_meta(c.doc_id)
            self._vstore.upsert(Embedding(
                chunk_id=c.id, doc_id=c.doc_id, dept=dept, sensitivity=sens,
                vector=emb.embed(c.text), model_version=emb.version(), active_spec=True,
            ))

    # --- query ---
    def query(self, identity: Identity, question: str) -> Answer:
        start = time.perf_counter()
        reranked, blocked = self._retriever.search(
            identity, question, self._active_embedder(),
            candidate_k=self._candidate_k, top_k=self._top_k)
        ans = generate_answer(question, identity, reranked, blocked, min_score=self._min_score)
        latency_ms = (time.perf_counter() - start) * 1000

        doc_ids = sorted({rc.chunk.doc_id for rc in reranked if rc.score >= self._min_score})
        self.audit.append(identity.actor, identity.dept, "query", question,
                          doc_ids, ans.text, ans.refused)
        self.warehouse.record_query(
            ts=datetime.now(timezone.utc).isoformat(), dept=identity.dept, actor=identity.actor,
            latency_ms=latency_ms, retrieved_count=len(ans.citations),
            cited=bool(ans.citations), refused=ans.refused,
            injection=ans.injection_flagged, out_of_scope=ans.out_of_scope_hint)
        return ans

    # --- reindex (zero-downtime) ---
    def reindex(self, new_embedder: Embedder) -> Dict[str, int]:
        """Đổi embedding model KHÔNG downtime. Xem reindex.py để hiểu blue/green.

        Trong lúc chạy hàm này, active_version VẪN là spec cũ → query không rỗng.
        Chỉ khi spec mới build xong, ta ĐỔI ATOMIC active_version (một phép gán).
        """
        old_version = self._active_version
        self._embedders[new_embedder.version()] = new_embedder

        # 1) build spec mới song song (query vẫn dùng spec cũ).
        built = embed_spec(self._retriever.all_chunks(), new_embedder, self._vstore,
                           meta=self._retriever.doc_meta)
        # 2) ĐỔI ATOMIC: từ đây query dùng spec mới (đã đầy đủ).
        self._active_version = new_embedder.version()
        # 3) retire spec cũ (dọn dẹp; không ảnh hưởng query vì đã lọc theo version).
        retired = self._vstore.set_active_spec(old_version, active=False)

        self.audit.append("system", "platform", "reindex",
                          f"{old_version}->{new_embedder.version()}",
                          [], f"built={built}", refused=False)
        return {"built": built, "retired": retired,
                "active_version_switched": 1}

    # --- helpers / observability ---
    def _active_embedder(self) -> Embedder:
        return self._embedders[self._active_version]

    def active_version(self) -> str:
        return self._active_version

    def stats(self) -> Dict[str, int]:
        return {
            "documents": len(self._docs),
            "chunks": len(self._retriever.all_chunks()),
            "vectors_total": len(self._vstore),
            "vectors_active": self._vstore.active_count(self._active_version),
            "audit_records": len(self.audit),
        }
