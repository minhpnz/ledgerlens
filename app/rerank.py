#Developed by HenryPhan
"""Reranker — bước tinh (precision) sau retrieve (recall).

Kiến trúc chuẩn: retrieve NHIỀU (BM25+vector+RRF, recall cao) → rerank ÍT (top-k,
precision cao). Ở production dùng CROSS-ENCODER (bge-reranker / cohere rerank): đọc
CẶP (query, chunk) cùng lúc nên chính xác hơn bi-encoder (embedding tính riêng),
nhưng ĐẮT → chỉ chạy trên top-k candidate (vd 50 → 8).

Ở đây dùng reranker tất định dựa trên overlap từ vựng + ưu tiên khớp cụm — đủ để
minh hoạ và test kiến trúc. Interface Reranker cho phép thay bằng cross-encoder thật.
"""
from __future__ import annotations

import re
from typing import List, Protocol

from .models import RetrievedChunk

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


class Reranker(Protocol):
    def rerank(self, query: str, cands: List[RetrievedChunk], top_k: int) -> List[RetrievedChunk]: ...


class LexicalReranker:
    def rerank(self, query: str, cands: List[RetrievedChunk], top_k: int = 8) -> List[RetrievedChunk]:
        q_tokens = set(_TOKEN_RE.findall(query.lower()))
        rescored: List[RetrievedChunk] = []
        for rc in cands:
            text_low = rc.chunk.text.lower()
            d_tokens = set(_TOKEN_RE.findall(text_low))
            if not q_tokens:
                overlap = 0.0
            else:
                overlap = len(q_tokens & d_tokens) / len(q_tokens)
            # Thưởng nếu chứa nguyên cụm query (khớp mạnh hơn khớp token rời).
            phrase_bonus = 0.3 if query.lower().strip() in text_low else 0.0
            rc.score = overlap + phrase_bonus
            rc.source = "reranked"
            rescored.append(rc)
        rescored.sort(key=lambda r: r.score, reverse=True)
        return rescored[:top_k]
