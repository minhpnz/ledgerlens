"""Reciprocal Rank Fusion (RRF) — hợp nhất kết quả BM25 + vector.

Vì sao RRF (không cộng score trực tiếp): score của BM25 và cosine ở THANG KHÁC
NHAU, không so sánh trực tiếp được. RRF chỉ dùng THỨ HẠNG:
    rrf(d) = Σ_lists 1 / (k + rank_list(d))        (k thường = 60)
→ đơn giản, ổn định, không cần chuẩn hoá score, rất mạnh trong thực tế.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Sequence, Tuple


def rrf_fuse(ranked_lists: Sequence[Sequence[str]], k: int = 60,
             limit: int = 50) -> List[Tuple[str, float]]:
    """ranked_lists: mỗi phần tử là list key ĐÃ SẮP theo hạng (tốt→xấu).

    Trả [(key, rrf_score)] giảm dần.
    """
    scores: Dict[str, float] = defaultdict(float)
    for lst in ranked_lists:
        for rank, key in enumerate(lst):
            scores[key] += 1.0 / (k + rank + 1)  # rank 0-based → +1
    fused = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return fused[:limit]
