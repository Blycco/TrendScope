"""Plan gate middleware — re-exports require_plan from auth.dependencies.

RULE 17: no duplication.
"""

from __future__ import annotations

from backend.auth.dependencies import require_plan as require_plan

__all__ = ["require_plan"]
