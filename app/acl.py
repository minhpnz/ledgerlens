#Developed by HenryPhan
"""ACL — access control by (department × clearance).

THE PRE-FILTER RULE, which is LedgerLens's primary security property:
restrict documents to the ones the caller MAY see **BEFORE** ranking, reranking
or generation — never post-filter. Why:
  - Post-filtering (search everything, then drop unauthorised documents at the
    end) leaks through ranking, timing and the RESULT COUNT; a single bug in that
    final filter is a breach.
  - Pre-filtering makes "nothing outside your permissions is ever seen" a
    STRUCTURAL INVARIANT that can be tested.

We also distinguish two different kinds of empty result:
  - No relevant document exists → an ordinary refusal.
  - A relevant document exists but is OUT OF SCOPE for this caller → an
    "out-of-scope hint": we acknowledge something exists without revealing any
    content. Better UX, still no leak.
"""
from __future__ import annotations

from .models import Identity, Sensitivity


def can_access(identity: Identity, dept: str, sensitivity: Sensitivity) -> bool:
    """True if the identity may see a document with this (dept, sensitivity).

    Requires sufficient clearance AND (same department OR a public document).
    """
    if identity.clearance < sensitivity:
        return False
    if sensitivity == Sensitivity.PUBLIC:
        return True
    return identity.dept == dept
