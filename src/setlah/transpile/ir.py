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


@dataclass(frozen=True)
class PrintedBlock:
    """A rewritten block as the rewriter hands it to the transpiler.

    One printed egglog expression per statement: ``rules`` are ``Rule(...)``
    terms, ``constraints`` are ``Constraint(...)`` or
    ``Constraint.integrity_constraints(...)`` terms, each possibly preceded
    by egglog's let-style bindings.  Printing and parsing statement by
    statement keeps every string as small as one statement, instead of one
    ``Block(...)`` whose right-nested ``cons_constraint`` chain grows a
    nesting level per statement and stops parsing near 200 of them
    (docs/known-issues.md, B5).
    """

    rules: list[str]
    constraints: list[str]
