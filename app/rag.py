#Developed by HenryPhan
"""Sinh câu trả lời RAG cấp compliance — grounded, có citation, an toàn.

Bốn ràng buộc cứng (khác 'RAG demo'):
  1. CITATION BẮT BUỘC: mọi câu trả lời trace về section_path gốc; không nguồn → refuse.
  2. GROUNDING THRESHOLD: chunk dưới min_score bị loại; hết chunk → refuse (không bịa).
  3. OUT-OF-SCOPE HINT: nếu có tài liệu liên quan nhưng NGOÀI QUYỀN (ACL chặn),
     báo 'có tài liệu ngoài phạm vi quyền' mà KHÔNG lộ nội dung — thay vì refuse trơ.
  4. UNTRUSTED SEPARATION: nội dung chunk là DỮ LIỆU; injection bị gắn cờ, không thực thi.

Đây là 'grounded generator' tất định (thay LLM thật để chạy offline). Khi nối LLM
thật, GIỮ NGUYÊN hợp đồng: context = nguồn đã cite, system prompt tách khỏi data
untrusted, bắt buộc citation, refuse-if-empty.
"""
from __future__ import annotations

from typing import List

from .guardrail import sanitize_snippet
from .models import Answer, Identity, RetrievedChunk


def generate_answer(query: str, identity: Identity, reranked: List[RetrievedChunk],
                    blocked_count: int, min_score: float = 0.1) -> Answer:
    grounded = [rc for rc in reranked if rc.score >= min_score]

    if not grounded:
        if blocked_count > 0:
            # Có tài liệu liên quan nhưng ngoài quyền — hint, KHÔNG lộ nội dung.
            return Answer(
                question=query,
                text=("Có tài liệu liên quan nhưng NẰM NGOÀI phạm vi quyền của bạn "
                      f"(phòng ban '{identity.dept}', mức '{identity.clearance.name}'). "
                      "Liên hệ chủ sở hữu tài liệu nếu cần truy cập."),
                refused=True, reason="out_of_scope", out_of_scope_hint=True,
            )
        return Answer(
            question=query, refused=True, reason="insufficient_grounded_evidence",
            text="Không đủ căn cứ trong tài liệu bạn được phép truy cập để trả lời chắc chắn.",
        )

    ans = Answer(question=query)
    lines: List[str] = ["Tổng hợp có trích dẫn từ các tài liệu bạn được phép truy cập:\n"]
    for i, rc in enumerate(grounded, 1):
        snippet, injected = sanitize_snippet(rc.chunk.text)
        if injected:
            ans.injection_flagged = True
        ref = rc.chunk.ref()
        lines.append(f"{i}. [{ref}] ({rc.chunk.page_ref}) {_truncate(snippet, 220)}")
        ans.citations.append(ref)
    lines.append("\nMọi kết luận truy vết được về [ref] điều khoản ở trên.")
    ans.text = "\n".join(lines)
    return ans


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n] + "…"
