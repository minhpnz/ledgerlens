#Developed by HenryPhan
# LedgerLens — Compliance-grade RAG over regulatory documents (Python/FastAPI)

A compliance-grade retrieval system: hybrid search (BM25 + vector) with
reranking and **mandatory citations**, an **ACL pre-filter** (department ×
clearance), **zero-downtime reindexing**, **resumable ingest**, a hash-chained
audit log, warehouse analytics, and an **MCP-style tool interface** for agents to
connect through.

The engineering focus is systems, retrieval and operations rather than ML depth.
Design notes and the "why this, not that" reasoning behind each decision are in
`LESSONS.md`.

The core (`app/`) is **framework-agnostic and tested with pytest**; `app/api.py`
is a thin FastAPI layer on top.

## Running

```bash
cd ledgerlens
python3 -m venv .venv && ./.venv/bin/pip install "fastapi" "uvicorn" "pytest" "httpx"
./.venv/bin/python -m pytest -q          # 25 tests: ACL isolation, reindex, RAG, ingest resume, ...
./.venv/bin/python main.py               # API at http://127.0.0.1:8090
```

Demo tokens (token → department, clearance): `fin-analyst` (finance, INTERNAL),
`fin-admin` (finance, RESTRICTED), `legal-analyst`, `legal-admin`.

```bash
# Query with citations, honouring the caller's ACL
curl -s localhost:8090/v1/query -H 'Authorization: Bearer fin-admin' \
  -d '{"question":"Project Titan acquisition premium timeline"}'

# The analyst asks the same question → out-of-scope hint: documents exist but are
# outside their clearance, and NO content is revealed
curl -s localhost:8090/v1/query -H 'Authorization: Bearer fin-analyst' \
  -d '{"question":"Project Titan acquisition premium timeline"}'

# MCP tool (agent connection) — still passes through ACL and audit
curl -s localhost:8090/mcp/call -H 'Authorization: Bearer fin-admin' \
  -d '{"name":"search_policies","arguments":{"question":"data retention seven years"}}'

# Governance (admin only)
curl -s localhost:8090/v1/analytics    -H 'Authorization: Bearer fin-admin'
curl -s localhost:8090/v1/audit/verify -H 'Authorization: Bearer fin-admin'
```

## Module map (details and alternatives in `LESSONS.md`)

| File | Role | Pattern |
|---|---|---|
| `app/ingest.py` | Resumable pipeline (PARSE → CHUNK → EMBED) | Checkpointed state machine, idempotent, with fault-injection tests |
| `app/reindex.py` + `service.py` | Zero-downtime reindex | **Blue/green by spec with an atomic switch** |
| `app/acl.py` + `retriever.py` | Access control | **ACL PRE-filter (department × clearance)** applied before reranking |
| `app/bm25.py` | Lexical search | BM25 from scratch (exact clause matching) |
| `app/vectorstore.py` | Semantic search | Cosine similarity, filtered by `active_spec`/version so generations never mix |
| `app/fusion.py` | Result merging | **Reciprocal rank fusion** (by rank, not by summing scores) |
| `app/rerank.py` | Refinement | Retrieve wide, rerank narrow (cross-encoder in production) |
| `app/rag.py` | Answer generation | **Mandatory citations + refusal + out-of-scope hints + untrusted-data separation** |
| `app/guardrail.py` | LLM defence | Injection/exfiltration detection, sanitise-as-data |
| `app/audit.py` | Auditing | Append-only hash chain (tamper-evident) |
| `app/warehouse.py` | Analytics | SQLite (→ DuckDB) query analytics for SLO and compliance reporting |
| `app/api.py` + `mcp.py` | Interfaces | FastAPI REST + MCP-style tool |

## P0 security tests

`tests/test_acl_isolation.py` sweeps every identity against probing queries and
asserts that **no citation ever falls outside the caller's permissions**, guarding
against cross-department and cross-clearance leaks. `tests/test_reindex.py`
verifies zero-downtime behaviour: no empty-result window, and no mixing of index
versions.
