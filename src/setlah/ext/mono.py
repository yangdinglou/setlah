"""
MonoSAT backend: SAT with a graph theory
========================================

The completed ground program (``ext.ground``) with its ``#edge`` directives as
edges of a MonoSAT graph under the ``acyclic`` predicate: the solver Cobra and
PolySI use, reached from the same model text as the clingo propagator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .ground import Completion, NotSupported, card_clauses, complete, ground, model_symbols

NAME = "monosat"


@dataclass
class MonoResult:
    satisfiable: bool
    atoms: list
    stats: dict


def run_source(source: str, *, extra_files: list[str] | None = None, on_model: Callable[[list], None] | None = None) -> MonoResult:
    try:
        import monosat
    except ImportError as e:  # pragma: no cover
        raise NotSupported("The monosat backend needs the monosat Python module") from e
    gp = ground(source, extra_files)
    comp = complete(gp)
    extra, top = card_clauses(comp)
    clauses = comp.clauses + extra
    monosat.Monosat().newSolver()
    vars_: dict = {}
    def var(i):
        v = vars_.get(i)
        if v is None:
            v = vars_[i] = monosat.Var()
        return v
    def lit(l):
        return var(l) if l > 0 else monosat.Not(var(-l))
    for c in clauses:
        monosat.AssertClause([lit(l) for l in c])
    if comp.edges:
        g = monosat.Graph(); nodes: dict = {}
        def node(n):
            if n not in nodes:
                nodes[n] = g.addNode()
            return nodes[n]
        for u, v, cond in comp.edges:
            e = g.addEdge(node(u), node(v))
            if not cond:
                monosat.AssertTrue(e)
            elif len(cond) == 1:
                monosat.AssertIff(e, lit(cond[0]))
            else:
                monosat.AssertIff(e, monosat.And(*[lit(l) for l in cond]))
        monosat.Assert(g.acyclic())
    sat = monosat.Solve()
    atoms: list = []
    if sat:
        atoms = model_symbols(comp, lambda a: a in vars_ and vars_[a].value())
        if on_model is not None:
            on_model(atoms)
    return MonoResult(sat, atoms, {"vars": top, "clauses": len(clauses), "cards": len(comp.cards), "edges": len(comp.edges)})
