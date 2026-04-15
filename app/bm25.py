#Developed by HenryPhan
"""BM25 — lexical/keyword search, hiện thực from scratch (không thư viện).

Vì sao cần BM25 bên cạnh vector (câu hỏi phỏng vấn kinh điển):
- Vector (embedding) giỏi NGỮ NGHĨA nhưng dở KHỚP CHÍNH XÁC: mã điều khoản
  ('Article 17'), thuật ngữ pháp lý hiếm, số hiệu, tên riêng.
- BM25 ngược lại: khớp token chính xác + có TF-IDF weighting.
→ Hybrid (BM25 + vector) lấy điểm mạnh cả hai (fusion ở fusion.py).

Công thức BM25 cho term t trong doc d:
    score += IDF(t) * ( f(t,d) * (k1+1) ) / ( f(t,d) + k1*(1 - b + b*|d|/avgdl) )
  IDF(t) = ln( 1 + (N - n_t + 0.5) / (n_t + 0.5) )   (dạng có smoothing, luôn > 0)
  k1 điều chỉnh bão hoà tần suất; b điều chỉnh phạt độ dài doc.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Dict, List, Tuple

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._docs: Dict[str, List[str]] = {}          # doc_key -> tokens
        self._df: Dict[str, int] = defaultdict(int)     # term -> số doc chứa
        self._tf: Dict[str, Dict[str, int]] = {}        # doc_key -> {term: freq}
        self._len: Dict[str, int] = {}
        self._avgdl = 0.0

    def add(self, key: str, text: str) -> None:
        if key in self._docs:
            # idempotent: bỏ df cũ trước khi thêm lại (hỗ trợ reindex/update).
            self._remove_stats(key)
        toks = _tokenize(text)
        self._docs[key] = toks
        tf: Dict[str, int] = defaultdict(int)
        for t in toks:
            tf[t] += 1
        self._tf[key] = tf
        self._len[key] = len(toks)
        for term in tf:
            self._df[term] += 1
        self._recompute_avgdl()

    def remove(self, key: str) -> None:
        if key in self._docs:
            self._remove_stats(key)
            del self._docs[key]
            del self._tf[key]
            del self._len[key]
            self._recompute_avgdl()

    def _remove_stats(self, key: str) -> None:
        for term in self._tf.get(key, {}):
            self._df[term] -= 1
            if self._df[term] <= 0:
                del self._df[term]

    def _recompute_avgdl(self) -> None:
        self._avgdl = (sum(self._len.values()) / len(self._len)) if self._len else 0.0

    def _idf(self, term: str) -> float:
        n = len(self._docs)
        n_t = self._df.get(term, 0)
        return math.log(1 + (n - n_t + 0.5) / (n_t + 0.5))

    def search(self, query: str, limit: int = 50) -> List[Tuple[str, float]]:
        """Trả [(doc_key, score)] giảm dần. Chỉ doc có ít nhất 1 term khớp."""
        q_terms = _tokenize(query)
        scores: Dict[str, float] = defaultdict(float)
        for term in q_terms:
            if term not in self._df:
                continue
            idf = self._idf(term)
            for key, tf in self._tf.items():
                f = tf.get(term, 0)
                if f == 0:
                    continue
                dl = self._len[key]
                denom = f + self.k1 * (1 - self.b + self.b * dl / (self._avgdl or 1))
                scores[key] += idf * (f * (self.k1 + 1)) / denom
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:limit]

    def __len__(self) -> int:
        return len(self._docs)
