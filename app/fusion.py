#Developed by HenryPhan
"""Reciprocal Rank Fusion (RRF) — merging BM25 and vector results.

Why RRF rather than summing scores directly: BM25 scores and cosine similarities
live on DIFFERENT SCALES and cannot be compared head to head. RRF uses only the
RANKS:
    rrf(d) = Σ_lists 1 / (k + rank_list(d))        (k is typically 60)
This is simple, stable, needs no score normalisation, and performs remarkably
well in practice.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Sequence, Tuple


def rrf_fuse(ranked_lists: Sequence[Sequence[str]], k: int = 60,
             limit: int = 50) -> List[Tuple[str, float]]:
    """ranked_lists: each element is a list of keys ALREADY SORTED best to worst.

    Returns [(key, rrf_score)] in descending order.
    """
    scores: Dict[str, float] = defaultdict(float)
    for lst in ranked_lists:
        for rank, key in enumerate(lst):
            scores[key] += 1.0 / (k + rank + 1)  # rank is 0-based, hence +1
    fused = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return fused[:limit]
