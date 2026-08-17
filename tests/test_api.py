from fastapi.testclient import TestClient

from app.api import create_app
from app.seed import build_seeded_service


def client() -> TestClient:
    return TestClient(create_app(build_seeded_service()))


def test_unauthorized_without_token():
    r = client().post("/v1/query", json={"question": "expense policy"})
    assert r.status_code == 401


def test_query_returns_citations():
    c = client()
    r = c.post("/v1/query", headers={"Authorization": "Bearer fin-admin"},
               json={"question": "travel expense reimbursement receipts"})
    assert r.status_code == 200
    body = r.json()
    assert body["citations"]
    assert body["refused"] is False


def test_ingest_requires_admin_clearance():
    c = client()
    # analyst (INTERNAL) không được ingest.
    r = c.post("/v1/ingest", headers={"Authorization": "Bearer fin-analyst"},
               json={"doc_id": "x-1", "dept": "finance", "sensitivity": 1,
                     "title": "X", "text": "## 1 A\nbody"})
    assert r.status_code == 403


def test_mcp_tool_respects_acl():
    c = client()
    # analyst hỏi tài liệu restricted qua MCP → không lộ nội dung.
    r = c.post("/mcp/call", headers={"Authorization": "Bearer fin-analyst"},
               json={"name": "search_policies",
                     "arguments": {"question": "Titan acquisition Acme premium"}})
    assert r.status_code == 200
    body = r.json()
    for ccite in body["citations"]:
        assert "ma-1" not in ccite  # không cite tài liệu restricted


def test_analytics_and_audit_admin_only():
    c = client()
    # gọi vài query để có dữ liệu analytics.
    c.post("/v1/query", headers={"Authorization": "Bearer fin-admin"},
           json={"question": "expense policy"})
    r = c.get("/v1/analytics", headers={"Authorization": "Bearer fin-admin"})
    assert r.status_code == 200
    assert r.json()["total_queries"] >= 1

    r2 = c.get("/v1/audit/verify", headers={"Authorization": "Bearer fin-admin"})
    assert r2.json()["intact"] is True

    # analyst không được xem analytics.
    r3 = c.get("/v1/analytics", headers={"Authorization": "Bearer fin-analyst"})
    assert r3.status_code == 403
