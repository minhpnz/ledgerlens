"""INVARIANT TEST: zero-downtime reindex — không cửa sổ rỗng, không trộn version."""
from app.embedding import HashEmbedder
from app.seed import build_seeded_service


def test_query_works_before_and_after_reindex():
    svc = build_seeded_service()
    ident = svc.identities.resolve("fin-admin")
    q = "expense travel reimbursement receipts thirty days"

    before = svc.query(ident, q)
    assert before.citations, "trước reindex phải trả kết quả"
    old_version = svc.active_version()

    # Đổi sang embedding model mới (seed khác → không gian vector khác).
    result = svc.reindex(HashEmbedder(dim=256, seed="v2"))
    assert result["built"] > 0
    assert svc.active_version() != old_version

    after = svc.query(ident, q)
    assert after.citations, "SAU reindex vẫn phải trả kết quả (không rỗng)"


def test_no_empty_window_active_spec_always_populated():
    """Ở mọi thời điểm quanh reindex, active spec luôn có vector (không rỗng)."""
    svc = build_seeded_service()
    old_version = svc.active_version()
    assert svc.stats()["vectors_active"] > 0  # trước

    svc.reindex(HashEmbedder(dim=256, seed="v2"))

    # sau khi switch: active spec mới đã đầy đủ; spec cũ bị retire.
    assert svc.stats()["vectors_active"] > 0  # sau
    assert svc.active_version() != old_version


def test_query_uses_only_active_version_no_mixing():
    """Search chỉ so cosine trong ĐÚNG một không gian embedding (active version)."""
    svc = build_seeded_service()
    ident = svc.identities.resolve("legal-admin")
    svc.reindex(HashEmbedder(dim=256, seed="v2"))
    # Nếu bị trộn version (cosine giữa v1 và v2), kết quả sẽ nhiễu/rỗng thất thường.
    # Câu hỏi khớp lit-1 (legal restricted) — legal-admin được phép.
    ans = svc.query(ident, "litigation defense strategy settlement ceiling")
    assert any("lit-1" in c for c in ans.citations)
