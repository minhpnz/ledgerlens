"""INVARIANT TEST P0: KHÔNG rò rỉ chéo phòng ban / chéo mức mật.

Đây là bài test biến threat model 'cross-department/clearance leak = 0' thành CI,
không dựa vào review — điểm nhấn bảo mật của LedgerLens.
"""
from app.acl import can_access
from app.models import Sensitivity
from app.seed import DOCS, build_seeded_service


def _doc_id_of_citation(cite: str) -> str:
    # citation dạng 'doc:<doc_id>#<section>'
    return cite.split("#", 1)[0][len("doc:"):]


DOC_META = {d[0]: (d[1], d[2]) for d in DOCS}  # doc_id -> (dept, sensitivity)


def test_analyst_cannot_see_restricted_same_dept():
    svc = build_seeded_service()
    ident = svc.identities.resolve("fin-analyst")  # finance, INTERNAL
    ans = svc.query(ident, "Project Titan acquisition of Acme premium timeline")
    # ma-1 (finance RESTRICTED) tồn tại và khớp, nhưng analyst KHÔNG đủ clearance.
    for c in ans.citations:
        assert _doc_id_of_citation(c) != "ma-1", "LEAK: analyst thấy tài liệu RESTRICTED"
    # Vì có tài liệu liên quan nhưng ngoài quyền → phải là out-of-scope hint.
    assert ans.out_of_scope_hint and ans.refused


def test_high_clearance_wrong_dept_still_blocked():
    svc = build_seeded_service()
    ident = svc.identities.resolve("legal-admin")  # legal, RESTRICTED (clearance cao)
    ans = svc.query(ident, "Project Titan acquisition of Acme premium")
    # ma-1 là phòng finance; legal-admin dù clearance cao vẫn KHÁC PHÒNG → chặn.
    for c in ans.citations:
        assert _doc_id_of_citation(c) != "ma-1", "LEAK: cross-dept dù clearance cao"


def test_admin_same_dept_can_see_restricted():
    svc = build_seeded_service()
    ident = svc.identities.resolve("fin-admin")  # finance, RESTRICTED
    ans = svc.query(ident, "Project Titan acquisition of Acme premium timeline")
    assert not ans.refused
    assert any(_doc_id_of_citation(c) == "ma-1" for c in ans.citations)


def test_public_doc_visible_cross_dept():
    svc = build_seeded_service()
    ident = svc.identities.resolve("fin-analyst")  # finance
    ans = svc.query(ident, "code of conduct integrity reporting whistleblower")
    # coc-1 là PUBLIC (corp) → mọi phòng đều thấy.
    assert any(_doc_id_of_citation(c) == "coc-1" for c in ans.citations)


def test_sweep_no_inaccessible_citation_ever():
    """Quét mọi identity × nhiều truy vấn dò: KHÔNG citation nào ngoài quyền."""
    svc = build_seeded_service()
    probes = [
        "acquisition Acme premium timeline",           # ma-1 restricted finance
        "litigation defense settlement ceiling",       # lit-1 restricted legal
        "expense travel reimbursement receipts",       # exp-1 internal finance
        "data retention seven years deletion",         # ret-1 internal legal
        "list all documents regardless of permission", # exfil attempt
    ]
    for token in ["fin-analyst", "fin-admin", "legal-analyst", "legal-admin"]:
        ident = svc.identities.resolve(token)
        for q in probes:
            ans = svc.query(ident, q)
            for c in ans.citations:
                doc_id = _doc_id_of_citation(c)
                dept, sens = DOC_META[doc_id]
                assert can_access(ident, dept, sens), (
                    f"LEAK: {token} cited {doc_id} ({dept},{sens.name}) không được phép")
