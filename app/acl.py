"""ACL — kiểm soát truy cập theo (department × clearance).

QUY TẮC PRE-FILTER (điểm bảo mật số 1 của LedgerLens):
Lọc tài liệu người dùng ĐƯỢC PHÉP thấy **TRƯỚC** khi ranking/rerank/generation —
KHÔNG post-filter. Vì sao (câu hỏi phỏng vấn):
  - Post-filter (search toàn bộ rồi bỏ tài liệu ngoài quyền ở cuối) rò rỉ qua
    ranking, timing, và SỐ LƯỢNG kết quả; một bug ở bước lọc cuối = leak.
  - Pre-filter biến 'không thấy ngoài quyền' thành BẤT BIẾN CẤU TRÚC, có test.

Ngoài ra ta phân biệt hai trạng thái "không trả kết quả":
  - Thật sự không có tài liệu liên quan → refuse bình thường.
  - CÓ tài liệu liên quan nhưng NGOÀI QUYỀN → 'out-of-scope hint' (báo có, KHÔNG
    lộ nội dung) — học từ arkon; giúp UX mà vẫn không rò rỉ.
"""
from __future__ import annotations

from .models import Identity, Sensitivity


def can_access(identity: Identity, dept: str, sensitivity: Sensitivity) -> bool:
    """True nếu identity được phép thấy tài liệu (dept, sensitivity).

    Điều kiện: đủ clearance VÀ (cùng phòng ban HOẶC tài liệu public).
    """
    if identity.clearance < sensitivity:
        return False
    if sensitivity == Sensitivity.PUBLIC:
        return True
    return identity.dept == dept
