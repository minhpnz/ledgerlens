"""Zero-downtime reindex — đổi embedding model KHÔNG có cửa sổ search rỗng.

Bài toán (bài học từ arkon): đổi embedding model nghĩa là phải tính lại TOÀN BỘ
vector. Cách ngây thơ (xoá index cũ → build lại) tạo CỬA SỔ RỖNG: trong lúc build,
search trả 0 kết quả. Với hệ compliance, đó là downtime không chấp nhận được.

Giải pháp BLUE/GREEN theo spec:
  1. Build spec MỚI (model_version mới) SONG SONG, để nguyên spec cũ đang phục vụ.
     Trong lúc này query vẫn chạy trên spec cũ (active_version = cũ) → không rỗng.
  2. Khi spec mới build XONG hoàn toàn → ĐỔI ATOMIC active_version = mới (một phép
     gán). Từ giây đó query dùng spec mới, đã đầy đủ → vẫn không rỗng.
  3. Retire spec cũ (active_spec=False) để dọn dẹp.

Vì sao không trộn version: vector store.search lọc CHÍNH XÁC model_version ==
active_version → không bao giờ so cosine giữa hai không gian embedding khác nhau
(vốn vô nghĩa). embedding.py cố ý cho hash-v1/hash-v2 khác không gian để test điều này.
"""
from __future__ import annotations

from typing import Iterable

from .embedding import Embedder
from .models import Chunk, Embedding
from .vectorstore import VectorStore

# Bảng tra dept+sensitivity của chunk (retriever cần) — nạp từ doc metadata.
from typing import Callable, Tuple
from .models import Sensitivity


def embed_spec(chunks: Iterable[Chunk], embedder: Embedder, store: VectorStore,
               meta: Callable[[str], Tuple[str, Sensitivity]]) -> int:
    """Build (hoặc rebuild) toàn bộ vector cho spec của `embedder`.

    meta(doc_id) -> (dept, sensitivity) để gắn ACL metadata vào vector.
    Trả số vector đã ghi. active_spec=True nhưng chỉ 'hiển thị' khi active_version
    trỏ đúng version này (do vector store lọc theo version).
    """
    n = 0
    for c in chunks:
        dept, sens = meta(c.doc_id)
        store.upsert(Embedding(
            chunk_id=c.id, doc_id=c.doc_id, dept=dept, sensitivity=sens,
            vector=embedder.embed(c.text), model_version=embedder.version(),
            active_spec=True,
        ))
        n += 1
    return n
