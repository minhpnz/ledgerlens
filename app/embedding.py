"""Embedding local, DETERMINISTIC (feature hashing) — chạy/test offline, không API.

Giống HashEmbedder bên SentinelLog (Go): tách token → hash vào chiều cố định →
L2-normalize để cosine = dot product. Interface Embedder + version cho phép:
  1. thay bằng model thật (bge/e5/OpenAI) mà không đụng tầng trên, và
  2. ĐÁNH DẤU version để làm zero-downtime reindex (đổi model = đổi version).

Có Hai version cố ý KHÁC NHAU (hash-v1, hash-v2 dùng seed khác) để test reindex:
vector của v1 và v2 không tương thích → chứng minh việc chuyển spec phải atomic.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import List, Protocol

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


class Embedder(Protocol):
    def embed(self, text: str) -> List[float]: ...
    def dim(self) -> int: ...
    def version(self) -> str: ...


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


class HashEmbedder:
    def __init__(self, dim: int = 256, seed: str = "v1"):
        self._dim = dim
        self._seed = seed
        self._version = f"hash-{seed}"

    def dim(self) -> int:
        return self._dim

    def version(self) -> str:
        return self._version

    def embed(self, text: str) -> List[float]:
        v = [0.0] * self._dim
        for tok in _tokenize(text):
            idx, sign = self._bucket(tok)
            v[idx] += sign
        _l2normalize(v)
        return v

    def _bucket(self, tok: str) -> tuple[int, float]:
        # Seed đưa vào hash → hai version cho bucket khác nhau (vector không tương thích).
        h = hashlib.sha1((self._seed + ":" + tok).encode()).digest()
        n = int.from_bytes(h[:4], "big")
        idx = n % self._dim
        sign = 1.0 if (h[4] & 1) == 0 else -1.0
        return idx, sign


def _l2normalize(v: List[float]) -> None:
    s = math.sqrt(sum(x * x for x in v))
    if s == 0:
        return
    inv = 1.0 / s
    for i in range(len(v)):
        v[i] *= inv


def cosine(a: List[float], b: List[float]) -> float:
    if len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))
