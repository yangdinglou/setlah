"""
Difference-logic extension for order sorts
==========================================

Lowers a ``Fun`` into an ``OrdDOM`` sort to a clingo-dl theory variable and every
comparison over its values to a reified Boolean tied to a ``&diff`` atom in both
directions (docs/order-sorts.md, T4). This is an extension in the design's
sense: a different solver (clingo-dl), its own admissibility check (the
comparison must be a difference constraint, ``x - y <= c`` after normalisation),
and its own runner. The core lowering asks for it through ``OrderLowering``
when a sort is selected ``dl``; it is never imported otherwise.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from ..ast import nodes
from ..transpile.ir import TranspileError
from ..lowering.formula import Lit, PredA

NAME = "dl"


class DifferenceLogic:
    def __init__(self, var_types_of: Callable[[str], str | None]):
        self.var_types_of = var_types_of
        self.rules: list[str] = []
        self.next_id = 0

    def ranges(self, f: str, arg_sorts: list[str], lo: int, hi: int) -> None:
        args = [f"A{i}" for i in range(len(arg_sorts))]
        guards = ", ".join(f"dom_{s}({a})" for s, a in zip(arg_sorts, args))
        term = f"{f}({', '.join(args)})" if args else f
        body = f" :- {guards}" if guards else ""
        self.rules.append(f"&diff{{ {term} }} <= {hi}{body}.")
        self.rules.append(f"&diff{{ {term} }} >= {lo}{body}.")

    def reified(self, x: str | None, y: str | None, c: str, sign: bool, binding: dict, bound_args: dict, var_types: dict) -> Lit:
        """Boolean ``__dl_k(vars)`` with  ``__dl_k <-> (x - y <= c)``; ``x``/``y`` are value
        variables bound to theory terms (None stands for 0), ``c`` a constant expression."""
        tx = binding[x] if x else "0"
        ty = binding[y] if y else "0"
        vars_: list[str] = []
        for name in _vars_of(tx) + _vars_of(ty) + _vars_of(c):
            if name not in vars_:
                vars_.append(name)
        k = self.next_id
        self.next_id += 1
        head = f"__dl_{k}({', '.join(vars_)})" if vars_ else f"__dl_{k}"
        guards = []
        for v in vars_:
            s = bound_args.get(v) or var_types.get(v) or self.var_types_of(v)
            if s is None:
                raise TranspileError(f"Order sorts (dl): cannot determine the sort of variable {v} in a comparison")
            guards.append(f"dom_{s}({v})")
        body = f" :- {', '.join(guards)}" if guards else ""
        self.rules.append(f"{{ {head} }}{body}.")
        self.rules.append(f"&diff{{ {tx} - {ty} }} <= {c} :- {head}.")
        self.rules.append(f"&diff{{ {ty} - {tx} }} <= {_sub(_neg(c), '1')} :- not {head}{', ' + ', '.join(guards) if guards else ''}.")
        return Lit(PredA(f"__dl_{k}", tuple(nodes.Variable(name=v) for v in vars_)), sign)


def _vars_of(text: str) -> list[str]:
    return re.findall(r"\b[A-Z][A-Za-z0-9_']*", text)


def _sub(a: str, b: str) -> str:
    if b == "0":
        return a
    if a == "0":
        return str(-int(b)) if b.lstrip("-").isdigit() else f"(-{b})"
    if a.lstrip("-").isdigit() and b.lstrip("-").isdigit():
        return str(int(a) - int(b))
    return f"({a} - {b})"


def _neg(a: str) -> str:
    return str(-int(a)) if a.lstrip("-").isdigit() else f"(-{a})"


def run_source(source: str, *, extra_files: list[str] | None = None, arguments: list[str] | None = None, on_model: Callable[[Any], None] | None = None) -> Any:
    """Execute a program with ``&diff`` atoms under clingo-dl."""
    import clingo
    import clingo.ast
    try:
        from clingodl import ClingoDLTheory
    except ImportError as e:  # pragma: no cover
        raise TranspileError("The dl extension needs clingo-dl (pip install clingo-dl)") from e
    thy = ClingoDLTheory()
    ctl = clingo.Control(arguments or [])
    thy.register(ctl)
    with clingo.ast.ProgramBuilder(ctl) as builder:
        clingo.ast.parse_string(source, lambda stm: thy.rewrite_ast(stm, builder.add))
    for path in (extra_files or []):
        ctl.load(path)
    ctl.ground([("base", [])])
    thy.prepare(ctl)

    def _on_model(m):
        thy.on_model(m)
        if on_model is not None:
            on_model((m, [(str(k), v) for k, v in thy.assignment(m.thread_id)]))

    return ctl.solve(on_model=_on_model)
