#Developed by HenryPhan
"""Resolve a token into an Identity (actor, dept, clearance).

The rule: the caller's department and clearance ALWAYS come from here, after
authentication, and never from the request body — otherwise any client could
escalate its own privileges. This is an in-memory demo; production would load
from IdP/OIDC claims and a directory, with a TTL cache.
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
