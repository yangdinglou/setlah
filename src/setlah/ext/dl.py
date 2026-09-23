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
        self.shared: dict[tuple, int] = {}      # canonical (x, y, c) -> Boolean id
        self.emitted: set[tuple] = set()        # (id, canonical guard body) already written

    def ranges(self, f: str, arg_sorts: list[str], lo: int, hi: int) -> None:
        args = [f"A{i}" for i in range(len(arg_sorts))]
        guards = ", ".join(f"dom_{s}({a})" for s, a in zip(arg_sorts, args))
        term = f"{f}({', '.join(args)})" if args else f
        body = f" :- {guards}" if guards else ""
        self.rules.append(f"&diff{{ {term} }} <= {hi}{body}.")
        self.rules.append(f"&diff{{ {term} }} >= {lo}{body}.")

    def reified(self, x: str | None, y: str | None, c: str, sign: bool, binding: dict, bound_args: dict, var_types: dict, context: list = ()) -> Lit:
        """Boolean ``__dl_k(vars)`` with  ``__dl_k <-> (x - y <= c)``; ``x``/``y`` are value
        variables bound to theory terms (None stands for 0), ``c`` a constant expression.
        The Boolean's choice and its converse theory rule are guarded by the cube's own
        positive deterministic literals that bind its variables (``context``, greedily,
        each literal taken only if it binds a variable still unbound), so it is grounded
        only where the comparison occurs; a variable none of them binds gets a domain
        guard. Chosen literals are never guards (see ``OrderLowering.rewrite_cube``).

        One Boolean per comparison, not per site: two sites whose comparison is the
        same up to the names of its variables share the Boolean (the hand-written
        DPQA program's ``xlt(Q0, Q1, S)`` used by every constraint), each site adding
        its own guard rules once; the negation of a shared comparison with a numeric
        bound (``y - x <= -c - 1``) is the shared Boolean's complement."""
        tx = binding[x] if x else "0"
        ty = binding[y] if y else "0"
        vars_: list[str] = []
        for name in _vars_of(tx) + _vars_of(ty) + _vars_of(c):
            if name not in vars_:
                vars_.append(name)
        canon = {v: f"V{i}" for i, v in enumerate(vars_)}
        key = (_rename(tx, canon), _rename(ty, canon), _rename(c, canon))
        negate = False
        if key in self.shared:
            k = self.shared[key]
        else:
            k = None
            if c.lstrip("-").isdigit():
                # the complement, y - x <= -c - 1, canonicalised in its own variable order
                c_neg = str(-int(c) - 1)
                vars_neg: list[str] = []
                for name in _vars_of(ty) + _vars_of(tx) + _vars_of(c_neg):
                    if name not in vars_neg:
                        vars_neg.append(name)
                canon_neg = {v: f"V{i}" for i, v in enumerate(vars_neg)}
                key_neg = (_rename(ty, canon_neg), _rename(tx, canon_neg), c_neg)
                if key_neg in self.shared:
                    k = self.shared[key_neg]; negate = True
                    tx, ty, c, vars_, canon = ty, tx, c_neg, vars_neg, canon_neg
            if k is None:
                k = self.next_id
                self.next_id += 1
                self.shared[key] = k
        head = f"__dl_{k}({', '.join(vars_)})" if vars_ else f"__dl_{k}"
        guards = []
        bound: set = set()
        need = set(vars_)
        for lit in context:
            lv = set(_vars_of(lit))
            if lv & (need - bound):
                guards.append(lit); bound |= lv
        for v in vars_:
            if v in bound:
                continue
            s = bound_args.get(v) or var_types.get(v) or self.var_types_of(v)
            if s is None:
                raise TranspileError(f"Order sorts (dl): cannot determine the sort of variable {v} in a comparison")
            guards.append(f"dom_{s}({v})")
        extra = {}
        for g in guards:
            for v in _vars_of(g):
                if v not in canon and v not in extra:
                    extra[v] = f"W{len(extra)}"
        gkey = (k, tuple(sorted(_rename(g, {**canon, **extra}) for g in guards)))
        if gkey not in self.emitted:
            self.emitted.add(gkey)
            body = f" :- {', '.join(guards)}" if guards else ""
            self.rules.append(f"{{ {head} }}{body}.")
            if len([g for g in self.emitted if g[0] == k]) == 1:
                self.rules.append(f"&diff{{ {tx} - {ty} }} <= {c} :- {head}.")
            self.rules.append(f"&diff{{ {ty} - {tx} }} <= {_sub(_neg(c), '1')} :- not {head}{', ' + ', '.join(guards) if guards else ''}.")
        return Lit(PredA(f"__dl_{k}", tuple(nodes.Variable(name=v) for v in vars_)), sign if not negate else not sign)


    def lemmas(self) -> list[str]:
        """Propositional consequences between shared Booleans over the same pair of
        terms that the theory would only discover at conflict time: ``x - y <= c1``
        and ``y - x <= c2`` exclude each other when ``c1 + c2 < 0`` (the hand-written
        DPQA program's exactly-one over less, greater and equal). Only exclusions of
        two positive atoms are emitted, which are sound wherever the atoms exist."""
        out: list[str] = []
        keys = list(self.shared.items())
        for a, ((tx1, ty1, c1), i) in enumerate(keys):
            if not c1.lstrip("-").isdigit():
                continue
            for (tx2, ty2, c2), j in keys[a:]:
                if not c2.lstrip("-").isdigit() or int(c1) + int(c2) >= 0:
                    continue
                # renumber the second key's swapped orientation (ty2, tx2) in first-occurrence order
                names2 = [v for v in _vars_of(ty2) + _vars_of(tx2) + _vars_of(c2)]
                order2: list[str] = []
                for v in names2:
                    if v not in order2:
                        order2.append(v)
                mapping = {v: f"V{n}" for n, v in enumerate(order2)}
                if (_rename(ty2, mapping), _rename(tx2, mapping)) != (tx1, ty1):
                    continue
                vars1 = []
                for v in _vars_of(tx1) + _vars_of(ty1) + _vars_of(c1):
                    if v not in vars1:
                        vars1.append(v)
                vars2 = []
                for v in _vars_of(tx2) + _vars_of(ty2) + _vars_of(c2):
                    if v not in vars2:
                        vars2.append(v)
                args2 = [mapping[v] for v in vars2]
                if i == j and args2 == vars1:
                    continue
                out.append(f":- __dl_{i}({', '.join(vars1)}), __dl_{j}({', '.join(args2)}).")
        return out


def _vars_of(text: str) -> list[str]:
    return re.findall(r"\b[A-Z][A-Za-z0-9_']*", text)


def _rename(text: str, mapping: dict) -> str:
    return re.sub(r"\b[A-Z][A-Za-z0-9_']*", lambda m: mapping.get(m.group(0), m.group(0)), text)


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
