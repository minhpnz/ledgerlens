#Developed by HenryPhan
"""Section-aware chunking cho tài liệu policy/pháp lý.

Vì sao section-aware (không fixed-size cắt mù): tài liệu compliance có cấu trúc
điều/khoản; cắt theo heading giữ ngữ nghĩa nguyên vẹn và cho CITATION chính xác
đến điều khoản (section_path) — thứ mà bản demo RAG cắt fixed-size không làm được.

Định dạng đầu vào (đơn giản hoá cho demo): plain text với heading dạng
'## <số> <tiêu đề>' ví dụ:
    ## 1 Data Retention
    Policy text ...
    ## 2.1 Access Control
    More text ...
Mỗi section thành 1..n chunk; section dài bị chia nhỏ theo max_chars + overlap để
không vượt ngân sách token, vẫn giữ section_path để cite.
"""
from __future__ import annotations

import re
from typing import List

from .models import Chunk

_HEADING_RE = re.compile(r"^\s*#{1,6}\s*([\d.]+\s+.*)$")


def chunk_document(doc_id: str, version: int, text: str,
                   max_chars: int = 500, overlap: int = 60) -> List[Chunk]:
    sections = _split_sections(text)
    chunks: List[Chunk] = []
    seq = 0
    for section_path, body in sections:
        for piece in _window(body, max_chars, overlap):
            seq += 1
            chunks.append(Chunk(
                id=f"{doc_id}:v{version}:c{seq}",
                doc_id=doc_id,
                version=version,
                section_path=section_path,
                text=piece.strip(),
                page_ref=f"p{1 + seq // 3}",
            ))
    return chunks


def _split_sections(text: str) -> List[tuple[str, str]]:
    """Trả list (section_path, body). Text trước heading đầu = 'preamble'."""
    lines = text.splitlines()
    sections: List[tuple[str, str]] = []
    cur_path = "preamble"
    cur_body: List[str] = []

    def flush():
        body = "\n".join(cur_body).strip()
        if body:
            sections.append((cur_path, body))

    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            flush()
            cur_path = m.group(1).strip()
            cur_body = []
        else:
            cur_body.append(line)
    flush()
    return sections


def _window(body: str, max_chars: int, overlap: int) -> List[str]:
    if len(body) <= max_chars:
        return [body]
    out: List[str] = []
    start = 0
    n = len(body)
    while start < n:
        end = min(start + max_chars, n)
        out.append(body[start:end])
        if end == n:
            break
        start = end - overlap  # overlap để không cắt mất ngữ cảnh ở ranh giới
    return out
