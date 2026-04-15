#Developed by HenryPhan
from app.bm25 import BM25Index
from app.fusion import rrf_fuse


def test_bm25_exact_term_ranks_top():
    idx = BM25Index()
    idx.add("d1", "the annual data retention period is seven years")
    idx.add("d2", "travel expense reimbursement within thirty days")
    idx.add("d3", "data deletion after retention is irreversible")
    ranked = idx.search("data retention", limit=3)
    keys = [k for k, _ in ranked]
    # d1 và d3 (chứa 'data'/'retention') phải xếp trên d2 (không chứa).
    assert "d2" not in keys[:2]
    assert set(keys[:2]) == {"d1", "d3"}


def test_bm25_idf_downweights_common_terms():
    idx = BM25Index()
    for i in range(10):
        idx.add(f"common{i}", "the policy applies to all staff")
    idx.add("rare", "the policy mentions cryptography keys")
    ranked = idx.search("cryptography policy", limit=3)
    # 'cryptography' hiếm (IDF cao) → doc chứa nó phải đứng đầu.
    assert ranked[0][0] == "rare"


def test_bm25_remove_is_idempotent_for_reindex():
    idx = BM25Index()
    idx.add("d1", "alpha beta")
    idx.add("d1", "alpha beta")  # add lại cùng key không được nhân đôi df
    assert len(idx) == 1
    idx.remove("d1")
    assert len(idx) == 0


def test_rrf_merges_rankings():
    lex = ["a", "b", "c"]
    vec = ["c", "b", "d"]
    fused = rrf_fuse([lex, vec], k=60, limit=10)
    keys = [k for k, _ in fused]
    # b và c xuất hiện ở CẢ hai list → phải xếp trên a, d (chỉ ở một list).
    assert keys.index("b") < keys.index("a")
    assert keys.index("c") < keys.index("d")
