# LedgerLens — Bài học (SRE/Platform-first, hiểu thấu đáo như thực chiến)

> Định vị cho phỏng vấn **SRE/Platform-AI**: LedgerLens **không có ML depth** — 100%
> là systems/retrieval/ops engineering. Nên file này **dẫn dắt bằng các trục SRE**
> (zero-downtime migration, resumable pipeline, security invariant, governance/SLO),
> rồi mới tới phần retrieval. Mỗi mục: mô hình tư duy → **vì sao chọn cách này thay vì
> cái phổ biến khác** → failure mode thật → phản biện 3 tầng.
>
> Đọc kèm: `../portfolio-projects.md` §Product 2 (thiết kế), `../core-ai-ml-interview.md`
> (CORE-H RAG, CORE-J security).

---

## 0. Pitch 30 giây (SRE-framed)

> "LedgerLens là RAG cấp compliance cho tài liệu tài chính/pháp lý. Nhìn từ góc
> platform: nó là một **search platform đa tenant** với ba bài toán SRE cứng —
> **đổi embedding model không downtime** (blue/green theo spec), **ingest resumable**
> (checkpoint state-machine + DLQ), và **cách ly truy cập ở cấp invariant test**
> (ACL pre-filter dept × clearance). Phần 'AI' chỉ là retrieval engineering: hybrid
> BM25+vector, RRF, rerank, citation bắt buộc. Security và tính đúng đắn là first-class,
> chứng minh bằng test chứ không bằng review."

---

# PHẦN A — Các trục SRE/Platform (đây là điểm mạnh để kể)

## A.1 Zero-downtime reindex — `app/reindex.py`, `app/service.py`, `app/vectorstore.py`

**Bài toán:** đổi embedding model = phải tính lại **toàn bộ** vector. Đây thực chất là
một **schema/data migration** trên hệ đang phục vụ.

**Mô hình blue/green theo spec:**
1. Build spec MỚI (`model_version` mới) **song song**, spec cũ vẫn phục vụ. Query lúc này
   dùng `active_version = cũ` → **không rỗng**.
2. Xong hết → **đổi atomic** `active_version = mới` (một phép gán). Từ đó dùng spec mới,
   đã đầy đủ → **vẫn không rỗng**.
3. Retire spec cũ.

**Vì sao cách này, KHÔNG chọn cái phổ biến hơn:**

| Cách | Vấn đề | Ghi chú |
|---|---|---|
| **Drop rồi rebuild** (ngây thơ) | **Cửa sổ rỗng**: trong lúc rebuild, search trả 0 kết quả → downtime; với compliance là không chấp nhận | Cái phần lớn người ta làm đầu tiên |
| **Rebuild in-place, ghi đè dần** | Trong lúc chạy, index **trộn** vector cũ + mới → cosine giữa hai không gian embedding **vô nghĩa** → kết quả rác | Sai âm thầm, khó phát hiện |
| **Blue/green theo spec (cái này)** | Tốn gấp đôi bộ nhớ tạm thời | Không downtime, không trộn version → đúng cho hệ luôn-bật |

**Vì sao không trộn version:** `vectorstore.search` lọc **chính xác** `model_version ==
active_version`. `embedding.py` cố ý cho `hash-v1`/`hash-v2` **khác không gian** để test
này có ý nghĩa (test `test_query_uses_only_active_version_no_mixing`).

**Failure mode thật:** "team đổi model embedding lúc 2h sáng bằng cách rebuild in-place;
trong 40 phút build, search trả kết quả trộn cũ-mới → analyst nhận tài liệu sai → sự cố
compliance." Fix chính là blue/green + atomic switch. **Đây là câu chuyện expand-contract
migration** — cùng pattern với đổi schema DB không downtime.

**Phản biện 3 tầng:**
- *Vì sao switch bằng một phép gán?* → để **atomic**; nếu switch nhiều bước, có cửa sổ
  trạng thái nửa vời (một phần query thấy spec mới, một phần cũ).
- *Tốn gấp đôi RAM có sao không?* → chấp nhận được vì tạm thời; đánh đổi RAM lấy uptime.
  Nếu RAM là ràng buộc, reindex theo shard/từng phần với cùng nguyên tắc.
- *Nếu build spec mới fail giữa chừng?* → active_version chưa đổi → vẫn phục vụ spec cũ
  bình thường; chỉ cần dọn spec mới dở. **Fail an toàn về trạng thái cũ.**

## A.2 Ingest resumable — `app/ingest.py`

**Mô hình:** mỗi doc là **state machine** (PARSE → CHUNK → EMBED → DONE) có **checkpoint
theo stage**. Crash giữa chừng → `resume()` chạy tiếp từ stage dở, **không làm lại phần
đã xong**. Mỗi stage **idempotent** (chunk id tất định, embed upsert theo key) → replay
an toàn.

**Vì sao cách này, không cái khác:**

| Cách | Vấn đề |
|---|---|
| Xử lý một phát, lỗi thì làm lại từ đầu | Lãng phí (re-parse/re-OCR tài liệu lớn); với batch lớn có thể không bao giờ xong |
| Ghi tiến độ nhưng stage **không idempotent** | Resume/replay tạo bản trùng, hỏng dữ liệu |
| **State machine + checkpoint + idempotent (cái này)** | Resume rẻ, replay an toàn; đổi được sang worker queue mà không đổi mô hình |

**Failure mode thật:** "worker OCR crash ở tài liệu thứ 8000/10000; không checkpoint →
job restart từ 0 → không bao giờ hoàn tất trong cửa sổ đêm." Fix = checkpoint per-doc +
resume. Đây là **resumable pipeline** giống embed worker của SentinelLog, chỉ khác đơn vị.

**Next step production:** đẩy stage vào DB + worker queue (arq/Celery) và persist checkpoint
để sống qua restart — interface giữ nguyên. **Vì sao arq/Celery chứ không thread:** cần
job **bền qua restart** + retry + visibility; thread trong process mất hết khi crash.

## A.3 ACL pre-filter như một INVARIANT có test — `app/acl.py`, `app/retriever.py`, `tests/test_acl_isolation.py`

**Mô hình:** lọc tài liệu được phép **TRƯỚC** ranking/rerank/generation. Biến "không thấy
ngoài quyền" thành **bất biến cấu trúc có CI test**, không dựa review.

**Vì sao PRE-filter, KHÔNG post-filter (câu hỏi bảo mật kinh điển):**

| Cách | Rò rỉ thế nào |
|---|---|
| **Post-filter** (search hết rồi bỏ tài liệu ngoài quyền ở cuối) | Rò qua **ranking** (thứ tự đổi vì có tài liệu ẩn), **timing** (query chậm hơn khi có nhiều tài liệu ẩn), **count** (số kết quả tiết lộ tồn tại); và một bug ở bước lọc cuối = leak toàn bộ |
| **Pre-filter (cái này)** | Tài liệu ngoài quyền **không bao giờ vào** pipeline scoring → không có bề mặt rò rỉ; có invariant test quét mọi identity × query |

**Điểm tinh tế — out-of-scope hint:** phân biệt "không có tài liệu" (refuse) vs "**có** tài
liệu nhưng ngoài quyền" (hint: báo có, **không lộ nội dung**). Vì sao đáng làm: UX tốt hơn
refuse trơ, mà vẫn không rò rỉ. Vì sao khó: phải báo tồn tại **mà không** để lộ chính sự
tồn tại đó thành kênh rò rỉ → chỉ hint chung chung, không kèm tiêu đề/nội dung.

**Failure mode thật:** "analyst phòng A gõ câu hỏi, hệ post-filter → thấy p95 latency câu
đó cao bất thường và trả 0 kết quả → suy ra 'có tài liệu mật liên quan tồn tại' → rò rỉ
metadata." Pre-filter triệt tiêu kênh này.

**Phản biện:** *Clearance cao có vượt được dept không?* → **Không**: `can_access` yêu cầu
**cả** đủ clearance **và** đúng dept (trừ public). Test `test_high_clearance_wrong_dept_still_blocked`
chứng minh: admin (clearance cao nhất) phòng legal **vẫn** không thấy tài liệu restricted
phòng finance. Clearance và dept là **hai chiều độc lập**, không bù trừ.

## A.4 Governance: audit hash-chain + warehouse/SLO — `app/audit.py`, `app/warehouse.py`

- **Audit hash-chain** (giống SentinelLog): tamper-evident cho kiểm toán. Giới hạn: không
  chống truncate đuôi → neo head ra WORM định kỳ.
- **Warehouse (sqlite → DuckDB ở prod)**: mỗi query ghi analytics (latency, cited, refused,
  injection, out_of_scope) → SLO dashboard + báo cáo compliance ("tuần này bao nhiêu query
  bị injection/refuse"). **Vì sao tách warehouse khỏi đường nóng:** analytics/aggregate là
  workload OLAP khác hẳn query nóng; đổ sang store riêng để không ảnh hưởng latency.

---

# PHẦN B — Retrieval engineering (biết đủ, không phải headline)

## B.1 Vì sao hybrid (BM25 + vector), không chỉ vector — `app/bm25.py`, `app/retriever.py`

| Chỉ dùng | Điểm mù |
|---|---|
| **Chỉ vector (embedding)** | Dở **khớp chính xác**: mã điều khoản "Article 17", số hiệu, tên riêng, thuật ngữ hiếm |
| **Chỉ BM25 (keyword)** | Không hiểu **đồng nghĩa/diễn giải** ("sa thải" vs "chấm dứt hợp đồng") |
| **Hybrid (cái này)** | Lấy điểm mạnh cả hai; đặc biệt quan trọng cho văn bản pháp lý (vừa cần khớp chính xác điều khoản vừa cần ngữ nghĩa) |

## B.2 Vì sao RRF fuse, không cộng score — `app/fusion.py`

Score BM25 và cosine ở **thang khác nhau**, không cộng trực tiếp được. **RRF** chỉ dùng
**thứ hạng** (`Σ 1/(k+rank)`) → không cần chuẩn hoá, ổn định, mạnh trong thực tế. Thay thế
phổ biến (weighted sum sau khi min-max normalize) mong manh: phụ thuộc phân phối score
từng truy vấn, dễ lệch. RRF "boring nhưng đúng".

## B.3 Vì sao retrieve-nhiều-rerank-ít — `app/rerank.py`

Kiến trúc **recall trước, precision sau**: retrieve rộng (BM25+vector+RRF, ~50 candidate)
→ rerank hẹp (cross-encoder, top ~8). Vì sao không rerank hết: **cross-encoder đắt** (đọc
cặp query-chunk cùng lúc) → chỉ chạy trên top-k. Vì sao không bỏ rerank: embedding (bi-
encoder) tính query và chunk **riêng** nên kém chính xác hơn cross-encoder đọc-cùng-lúc.

## B.4 Vì sao citation bắt buộc + refuse — `app/rag.py`

Trong compliance, **câu sai tệ hơn câu "không biết"**. Nên: không nguồn trên ngưỡng →
**refuse**, không bịa; mọi câu trả lời **trace về section_path**; nội dung retrieve là
**untrusted data** (injection bị gắn cờ, không thực thi). Đây là hợp đồng giữ nguyên khi
nối LLM thật.

---

## C. Bảng "why-this-not-that" tổng hợp (ôn nhanh)

| Quyết định | Chọn | Thay vì | Lý do |
|---|---|---|---|
| Đổi embedding model | blue/green theo spec + switch atomic | drop-rebuild / in-place | Không downtime, không trộn version |
| Ingest lỗi | resumable state-machine + idempotent | làm lại từ đầu | Rẻ + replay an toàn |
| Kiểm soát truy cập | pre-filter + invariant test | post-filter | Không bề mặt rò rỉ; chứng minh bằng CI |
| "Không kết quả" | phân biệt refuse vs out-of-scope hint | refuse trơ | UX tốt mà không lộ nội dung |
| Search | hybrid BM25+vector | chỉ vector | Cần cả khớp chính xác lẫn ngữ nghĩa |
| Hợp nhất kết quả | RRF (theo rank) | weighted sum score | Không cần chuẩn hoá, ổn định |
| Rerank | retrieve nhiều → rerank ít (cross-encoder) | rerank hết / bỏ rerank | Cân precision vs cost |
| Câu trả lời | citation bắt buộc + refuse-if-empty | trả lời mờ | Compliance: sai tệ hơn "không biết" |
| Warehouse | tách store OLAP (sqlite→DuckDB) | query analytics trên đường nóng | Không ảnh hưởng latency query |
| Worker | queue bền (arq/Celery) ở prod | thread trong process | Bền qua restart + retry + visibility |
| API framework | FastAPI | Flask/Django | Async-native + validation + OpenAPI sẵn |

---

## D. Câu hỏi phỏng vấn nhắm vào codebase này

1. Đổi embedding model mà không downtime — làm thế nào, chứng minh "không rỗng" ra sao? (A.1)
2. Vì sao không được trộn vector cũ và mới? (A.1)
3. Ingest crash ở tài liệu 8000/10000 — thiết kế để không làm lại từ đầu? (A.2)
4. Pre-filter vs post-filter ACL — rò rỉ khác nhau thế nào? (A.3)
5. Clearance cao có vượt được rào phòng ban không? Chứng minh? (A.3)
6. Out-of-scope hint là gì, làm sao báo "có tài liệu" mà không rò rỉ? (A.3)
7. Vì sao hybrid search, vì sao RRF chứ không cộng score? (B.1, B.2)
8. Vì sao không rerank toàn bộ candidate? (B.3)
9. RAG chống hallucination và prompt injection thế nào? (B.4)

## E. Còn để mở rộng

- Postgres + pgvector (HNSW) thay in-memory; BM25 → Postgres FTS/Elasticsearch.
- Cross-encoder rerank thật (bge-reranker); embedding thật (bge/e5); LLM thật (giữ hợp đồng citation).
- arq/Celery worker + persist checkpoint; DuckDB warehouse thật.
- MCP server SDK thật; Terraform/Helm; SLO dashboard + burn-rate alert; security test report (0 leak).
