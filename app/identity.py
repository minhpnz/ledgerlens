"""Phân giải token -> Identity (actor, dept, clearance).

Nguyên tắc như SentinelLog: dept/clearance của người hỏi LUÔN đến từ đây (sau xác
thực), KHÔNG từ body request → chống privilege escalation. Bản demo in-memory;
production nạp từ IdP/OIDC claims + directory, cache TTL.
"""
from __future__ import annotations

from typing import Dict, Optional

from .models import Identity, Sensitivity


class IdentityResolver:
    def __init__(self) -> None:
        self._by_token: Dict[str, Identity] = {}

    def add(self, token: str, actor: str, dept: str, clearance: Sensitivity) -> None:
        self._by_token[token] = Identity(actor=actor, dept=dept, clearance=clearance)

    def resolve(self, token: str) -> Optional[Identity]:
        return self._by_token.get(token)
