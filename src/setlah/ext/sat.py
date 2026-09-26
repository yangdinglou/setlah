"""
SAT backend: a solver-level lowering
====================================

The compiled ASP program, grounded by clingo and completed (``ext.ground``), is
decided by a SAT solver through pysat. Correct for tight programs without
objectives, theory atoms or ``#edge`` directives (the last need the graph theory
of ``ext.mono``). Extension in the design's sense: a different system, its own
admissibility check, its own runner.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .ground import Completion, NotSupported, card_clauses, complete, ground, model_symbols

NAME = "sat"


@dataclass
class SatResult:
    satisfiable: bool
    atoms: list
    stats: dict


def run_source(source: str, *, extra_files: list[str] | None = None, solver: str = "cadical153",
               on_model: Callable[[list], None] | None = None) -> SatResult:
    try:
        from pysat.solvers import Solver
    except ImportError as e:  # pragma: no cover
        raise NotSupported("The sat backend needs pysat (pip install python-sat)") from e
    gp = ground(source, extra_files)
    if gp.edges:
        raise NotSupported("#edge directives in the program: use the monosat backend, or --acyclic-lowering positions/closure")
    comp = complete(gp)
    extra, top = card_clauses(comp)
    clauses = comp.clauses + extra
    with Solver(name=solver, bootstrap_with=clauses) as s:
        sat = s.solve()
        atoms: list = []
        if sat:
            model = set(l for l in s.get_model() if l > 0)
            atoms = model_symbols(comp, lambda a: a in model)
            if on_model is not None:
                on_model(atoms)
    return SatResult(sat, atoms, {"vars": top, "clauses": len(clauses), "cards": len(comp.cards)})
