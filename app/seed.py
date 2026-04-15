#Developed by HenryPhan
"""Seed corpus + identity demo: 2 phòng ban × nhiều mức mật để minh hoạ ACL.

Dùng trong main.py (chạy server) và trong test (dựng service có sẵn dữ liệu).
"""
from __future__ import annotations

from .models import Sensitivity
from .service import LedgerLensService

# --- Tài liệu demo (dept, sensitivity, title, text section-aware) ---
DOCS = [
    ("coc-1", "corp", Sensitivity.PUBLIC, "Code of Conduct",
     "## 1 Ethics\nAll employees must act with integrity and report violations.\n"
     "## 2 Reporting\nUse the whistleblower channel for concerns."),
    ("exp-1", "finance", Sensitivity.INTERNAL, "Expense Policy",
     "## 1 Travel\nEconomy class for flights under 6 hours; business allowed above.\n"
     "## 2 Reimbursement\nSubmit receipts within 30 days via the finance portal."),
    ("ma-1", "finance", Sensitivity.RESTRICTED, "Project Titan M&A Memo",
     "## 1 Target\nAcquisition of Acme Corp at a 30% premium.\n"
     "## 2 Timeline\nSigning expected Q4; strictly confidential until announcement."),
    ("ret-1", "legal", Sensitivity.INTERNAL, "Data Retention Regulation",
     "## 1 Retention\nCustomer records retained for 7 years per regulation.\n"
     "## 2 Deletion\nAfter retention, data must be irreversibly deleted."),
    ("lit-1", "legal", Sensitivity.RESTRICTED, "Litigation Strategy",
     "## 1 Case\nDefense strategy for the pending class action.\n"
     "## 2 Settlement\nAuthorized settlement ceiling is confidential to legal leads."),
]


def build_seeded_service() -> LedgerLensService:
    svc = LedgerLensService()

    # Identities: token -> (actor, dept, clearance).
    svc.identities.add("fin-analyst", "fiona", "finance", Sensitivity.INTERNAL)
    svc.identities.add("fin-admin", "frank", "finance", Sensitivity.RESTRICTED)
    svc.identities.add("legal-analyst", "laura", "legal", Sensitivity.INTERNAL)
    svc.identities.add("legal-admin", "leo", "legal", Sensitivity.RESTRICTED)

    for doc_id, dept, sens, title, text in DOCS:
        svc.ingest_document(doc_id, dept, sens, title, text)
    return svc
