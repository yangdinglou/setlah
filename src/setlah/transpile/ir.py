"""
Intermediate Representation (Mini-IR)
======================================

IRRule and IRConstraint dataclasses used during transpilation.
Also contains TranspileError so other modules can import it without circularity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class TranspileError(Exception):
    pass


# =============================================================================
# 5. INTERMEDIATE REPRESENTATION (Mini-IR)
# =============================================================================


@dataclass(frozen=True)
class IRRule:
    head: Any
    body: list[Any]
    is_choice: bool


@dataclass(frozen=True)
class IRConstraint:
    kind: str
    vars: list[Any] | None
    lits: list[Any] | None
    body: Any | None
    let_rules: list[str] | None = None  # ASP rules generated from Let expressions
