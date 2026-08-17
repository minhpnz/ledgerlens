# LedgerLens — Compliance-grade RAG over regulatory documents (Python/FastAPI)

Product 2 của portfolio (xem `../portfolio-projects.md` §Product 2). RAG cấp compliance:
hybrid search (BM25+vector) + rerank + **citation bắt buộc**, **ACL pre-filter** (dept ×
clearance), **zero-downtime reindex**, **resumable ingest**, audit hash-chain, warehouse
analytics, và **MCP-style tool** để agent kết nối.

**Định vị SRE/Platform:** không có ML depth — toàn bộ là systems/retrieval/ops engineering.
Bài học & "why-this-not-that" ở `LESSONS.md` (đọc phần A: các trục SRE).

Lõi (`app/`) **framework-agnostic + test bằng pytest**; `app/api.py` là lớp FastAPI mỏng.

## Chạy

```bash
cd ledgerlens
python3 -m venv .venv && ./.venv/bin/pip install "fastapi" "uvicorn" "pytest" "httpx"
./.venv/bin/python -m pytest -q          # 25 test: ACL isolation, reindex, RAG, ingest resume...
./.venv/bin/python main.py               # API tại http://127.0.0.1:8090
```

Token demo (token → dept, clearance): `fin-analyst` (finance, INTERNAL), `fin-admin`
(finance, RESTRICTED), `legal-analyst`, `legal-admin`.

```bash
# Query có citation, tôn trọng ACL của người gọi
curl -s localhost:8090/v1/query -H 'Authorization: Bearer fin-admin' \
  -d '{"question":"Project Titan acquisition premium timeline"}'

# analyst hỏi cùng câu → out-of-scope hint (có tài liệu nhưng ngoài quyền, KHÔNG lộ nội dung)
curl -s localhost:8090/v1/query -H 'Authorization: Bearer fin-analyst' \
  -d '{"question":"Project Titan acquisition premium timeline"}'

# MCP tool (agent connect) — vẫn qua ACL + audit
curl -s localhost:8090/mcp/call -H 'Authorization: Bearer fin-admin' \
  -d '{"name":"search_policies","arguments":{"question":"data retention seven years"}}'

# Governance (admin only)
curl -s localhost:8090/v1/analytics    -H 'Authorization: Bearer fin-admin'
curl -s localhost:8090/v1/audit/verify -H 'Authorization: Bearer fin-admin'
```

## Bản đồ module (chi tiết + alternatives ở `LESSONS.md`)

| File | Vai trò | Pattern |
|---|---|---|
| `app/ingest.py` | Resumable pipeline (PARSE→CHUNK→EMBED) | checkpoint state-machine + idempotent + fault-inject test |
| `app/reindex.py` + `service.py` | Zero-downtime reindex | **blue/green theo spec + switch atomic** |
| `app/acl.py` + `retriever.py` | Kiểm soát truy cập | **ACL PRE-filter (dept × clearance)** trước rerank |
| `app/bm25.py` | Lexical search | BM25 from scratch (khớp chính xác điều khoản) |
| `app/vectorstore.py` | Semantic search | cosine + lọc `active_spec`/version (không trộn) |
| `app/fusion.py` | Hợp nhất | **RRF** (theo rank, không cộng score) |
| `app/rerank.py` | Tinh chỉnh | retrieve-nhiều → rerank-ít (cross-encoder ở prod) |
| `app/rag.py` | Sinh câu trả lời | **citation bắt buộc + refuse + out-of-scope hint + untrusted separation** |
| `app/guardrail.py` | Phòng thủ LLM | injection/exfil detect, sanitize-as-data |
| `app/audit.py` | Kiểm toán | append-only hash-chain (tamper-evident) |
| `app/warehouse.py` | Analytics | sqlite (→DuckDB) query analytics cho SLO/compliance |
| `app/api.py` + `mcp.py` | Giao diện | FastAPI REST + MCP-style tool |

## Test bảo mật P0

`tests/test_acl_isolation.py` — quét mọi identity × truy vấn dò, khẳng định **không
citation nào ngoài quyền** (chống cross-department/clearance leak). `tests/test_reindex.py`
— zero-downtime (không cửa sổ rỗng, không trộn version).
