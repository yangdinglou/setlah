"""
Order sorts: the core lowerings and the selection rule
======================================================

An ``OrdDOM`` sort is a bounded integer sort whose values occur only as the
last argument of ``Fun`` predicates and in comparisons (docs/order-sorts.md).
The core compiler lowers it in two ways, both plain ASP:

- ``enum`` (the basic lowering): the values as a finite sort, ``dom_S(lo..hi)``,
  each ``Fun`` as an exactly-one choice over them, comparisons grounded;
- ``rel``: no values; one total preorder ``__le_S`` per sort over the function
  terms, the range as a bound on the number of preorder classes, comparisons
  without offsets as ``__le_S`` literals (T2).

The ``dl`` lowering (values as theory variables under clingo-dl, T4) lives in
the extension ``setlah.ext.dl`` and is used only when that extension is
enabled. The selection rule (T6) is ``auto``: a sort is lowered relationally
when every comparison over it is between two values without offsets; a sort
that needs an offset, a constant or a distance goes to ``dl`` when the
extension is enabled and to ``enum`` otherwise; a sort whose values occur as
arguments of ordinary predicates or in aggregates goes to ``enum``.
"""

from __future__ import annotations

from typing import Any, Callable

from ..ast import nodes
from ..transpile.ir import TranspileError
from .formula import CompA, Lit, PredA, all_vars


class NeedsOther(TranspileError):
    """A sort cannot be lowered in the requested way; ``want`` names the lowering the
    selection rule should retry (``dl`` or ``enum``)."""

    def __init__(self, sort: str, want: str, msg: str):
        super().__init__(msg)
        self.sort, self.want = sort, want


class LinearTerm:
    """``sum coeff_i * V_i + const_expr`` over order-sort variables ``V_i``."""

    def __init__(self, coeffs: dict, const: str):
        self.coeffs, self.const = coeffs, const


class _Conj(list):
    """A conjunction of literals standing in for one cube item."""


class OrderLowering:
    def __init__(self, functions: dict[str, tuple[list[str], str]], order_sorts: dict[str, tuple[int, int]],
                 var_types_of: Callable[[str], str | None], modes: dict[str, str], extensions: tuple[str, ...] = ()):
        self.functions = functions           # f -> (argument sorts, order sort)
        self.order_sorts = order_sorts       # sort -> (lo, hi)
        self.var_types_of = var_types_of
        self.modes = modes                   # sort -> "enum" | "rel" | "dl"
        self.extensions = extensions
        self.dl = None
        if any(m == "dl" for m in modes.values()):
            if "dl" not in extensions:
                raise TranspileError("Order sorts: the dl lowering needs the dl extension (--ext dl)")
            from ..ext.dl import DifferenceLogic
            self.dl = DifferenceLogic(var_types_of)
            for f, (arg_sorts, sort) in functions.items():
                if modes[sort] == "dl":
                    lo, hi = order_sorts[sort]
                    self.dl.ranges(f, arg_sorts, lo, hi)

    def mode(self, sort: str) -> str:
        return self.modes[sort]

    # --- rules that depend on the whole program --------------------------------

    def finalize(self) -> list[str]:
        out: list[str] = []
        if self.dl is not None:
            out += self.dl.rules
        for sort, (lo, hi) in self.order_sorts.items():
            fs = [f for f, (_, s_) in self.functions.items() if s_ == sort]
            if not fs:
                continue
            m = self.mode(sort)
            if m == "enum":
                out.append(f"% order sort {sort}: enumeration (the basic lowering)")
                out.append(f"dom_{sort}({lo}..{hi}).")
                for f in fs:
                    arg_sorts = self.functions[f][0]
                    args = [f"A{i}" for i in range(len(arg_sorts))]
                    guards = ", ".join(f"dom_{s_}({a})" for s_, a in zip(arg_sorts, args))
                    out.append(f"1 {{ {f}({', '.join(args + ['V'])}) : dom_{sort}(V) }} 1{' :- ' + guards if guards else ''}.")
            elif m == "rel":
                el, le, head = f"__el_{sort}", f"__le_{sort}", f"__head_{sort}"
                out.append(f"% order sort {sort}: relational lowering (a total preorder over its function terms)")
                for f in fs:
                    arg_sorts = self.functions[f][0]
                    args = [f"A{i}" for i in range(len(arg_sorts))]
                    term = f"{f}({', '.join(args)})" if args else f
                    guards = ", ".join(f"dom_{s_}({a})" for s_, a in zip(arg_sorts, args))
                    out.append(f"{el}({term}){' :- ' + guards if guards else ''}.")
                out.append(f"{{ {le}(E1, E2) }} :- {el}(E1), {el}(E2), E1 != E2.")
                out.append(f"{le}(E, E) :- {el}(E).")
                out.append(f":- {el}(E1), {el}(E2), E1 < E2, not {le}(E1, E2), not {le}(E2, E1).")
                out.append(f":- {le}(E1, E2), {le}(E2, E3), not {le}(E1, E3).")
                out.append(f"{head}(E) :- {el}(E), #count{{ E2 : {le}(E, E2), {le}(E2, E), E2 < E }} = 0.")
                out.append(f":- #count{{ E : {head}(E) }} > {hi - lo + 1}.")
        return out

    # --- cubes ------------------------------------------------------------------

    def rewrite_cube(self, cube: list, var_types: dict[str, str]) -> list[list]:
        """Rewrite one conjunction of items; returns the cubes that replace it."""
        binding: dict[str, str] = {}      # value variable -> function term text (rel and dl sorts only)
        bound_args: dict[str, str] = {}   # argument variable -> its sort
        rest: list = []
        for it in cube:
            if isinstance(it, Lit) and isinstance(it.atom, PredA) and it.atom.name in self.functions:
                arg_sorts, sort = self.functions[it.atom.name]
                if self.mode(sort) == "enum":
                    rest.append(it)          # an ordinary predicate: the basic lowering handles it
                    continue
                if not it.positive:
                    raise TranspileError(f"Order sorts: a negated function atom ({it.atom.name}) is not supported")
                *args, val = it.atom.args
                if not isinstance(val, nodes.Variable):
                    raise TranspileError(f"Order sorts: the value argument of {it.atom.name} must be a variable")
                text = self._term_text(it.atom.name, args)
                if val.name in binding and binding[val.name] != text:
                    alias = val.name + "__eq"
                    rest.append(Lit(CompA("==", nodes.Variable(name=val.name), nodes.Variable(name=alias)), True))
                    binding[alias] = text
                else:
                    binding[val.name] = text
                for a, s_ in zip(args, arg_sorts):
                    if isinstance(a, nodes.Variable):
                        bound_args[a.name] = s_
            else:
                rest.append(it)
        if not binding:
            return [cube]
        cubes: list[list] = [[]]
        for it in rest:
            if isinstance(it, Lit) and isinstance(it.atom, CompA) and self._mentions(it.atom, binding):
                alternatives = self.compare(it.atom, it.positive, binding, bound_args, var_types)
                cubes = [c + [alt] for c in cubes for alt in alternatives]
            else:
                touched = [v for v in self._vars(it) if v in binding]
                if touched:
                    sort = self._sort_of(touched[0], binding)
                    raise NeedsOther(sort, "enum", f"Order sorts: a value of sort {sort} occurs outside comparisons; the sort is lowered by enumeration")
                cubes = [c + [it] for c in cubes]
        out: list[list] = []
        for c in cubes:
            positively: set = set()
            for it in c:
                if isinstance(it, Lit) and it.positive and isinstance(it.atom, PredA):
                    positively.update(t.name for t in it.atom.args if isinstance(t, nodes.Variable))
            guards = [Lit(PredA(f"dom_{s_}", (nodes.Variable(name=v),)), True) for v, s_ in bound_args.items() if v not in positively]
            out.append(guards + c)
        return out

    def rewrite_rule_body(self, body: list, var_types: dict[str, str]) -> list[list]:
        cube = []
        for lit in body:
            if isinstance(lit, nodes.PredAtom):
                cube.append(Lit(PredA(lit.predicate.name, tuple(lit.args)), True))
            elif isinstance(lit, nodes.Comparison):
                cube.append(Lit(CompA(lit.op, lit.left, lit.right), True))
            else:
                raise TranspileError(f"Unsupported rule body literal: {lit!r}")
        return self.rewrite_cube(cube, var_types)

    # --- comparisons --------------------------------------------------------------

    def compare(self, comp: CompA, positive: bool, binding: dict, bound_args: dict, var_types: dict) -> list:
        left, right = self._linear(comp.left, binding), self._linear(comp.right, binding)
        net: dict = dict(left.coeffs)
        for v, k in right.coeffs.items():
            net[v] = net.get(v, 0) - k
        net = {v: k for v, k in net.items() if k}
        pos = [v for v, k in net.items() if k == 1]
        neg = [v for v, k in net.items() if k == -1]
        anyvar = next(iter(left.coeffs or right.coeffs))
        sort = self._sort_of(anyvar, binding)
        if len(pos) + len(neg) != len(net) or len(pos) > 1 or len(neg) > 1:
            raise NeedsOther(sort, "enum", f"Order sorts: a comparison over sort {sort} is not a difference constraint; the sort is lowered by enumeration")
        x = pos[0] if pos else None
        y = neg[0] if neg else None
        const = _sub(right.const, left.const)
        op = comp.op if positive else {"==": "!=", "!=": "==", "<": ">=", ">=": "<", ">": "<=", "<=": ">"}[comp.op]
        if self.mode(sort) == "rel":
            if x is None or y is None or const != "0":
                raise NeedsOther(sort, "dl", f"Order sorts: sort {sort} is lowered relationally, which admits only comparisons between two values without offsets")
            if self._sort_of(y, binding) != sort:
                raise TranspileError("Order sorts: comparison between values of different sorts")
            return self._relational(binding[x], binding[y], op, sort)
        assert self.dl is not None
        if op == "<=": alts = [[(x, y, const)]]
        elif op == "<": alts = [[(x, y, _sub(const, "1"))]]
        elif op == ">=": alts = [[(y, x, _neg(const))]]
        elif op == ">": alts = [[(y, x, _sub(_neg(const), "1"))]]
        elif op == "==": alts = [[(x, y, const), (y, x, _neg(const))]]
        elif op == "!=": alts = [[(x, y, _sub(const, "1"))], [(y, x, _sub(_neg(const), "1"))]]
        else: raise TranspileError(f"Order sorts: unsupported comparison {op}")
        out = []
        for conj in alts:
            lits = [self.dl.reified(x_, y_, c_, True, binding, bound_args, var_types) for x_, y_, c_ in conj]
            out.append(_Conj(lits) if len(lits) > 1 else lits[0])
        return out

    def _relational(self, tx: str, ty: str, op: str, sort: str) -> list:
        le = f"__le_{sort}"
        def lit(a, b, sign): return Lit(PredA(le, (nodes.Identifier(name=a), nodes.Identifier(name=b))), sign)
        if op == "<=": return [lit(tx, ty, True)]
        if op == ">=": return [lit(ty, tx, True)]
        if op == "<": return [_Conj([lit(tx, ty, True), lit(ty, tx, False)])]
        if op == ">": return [_Conj([lit(ty, tx, True), lit(tx, ty, False)])]
        if op == "==": return [_Conj([lit(tx, ty, True), lit(ty, tx, True)])]
        if op == "!=": return [lit(tx, ty, False), lit(ty, tx, False)]
        raise TranspileError(f"Order sorts: unsupported comparison {op}")

    # --- helpers --------------------------------------------------------------------

    def _sort_of(self, var: str, binding: dict) -> str:
        return self.functions[binding[var].split("(")[0]][1]

    def _linear(self, t: Any, binding: dict) -> LinearTerm:
        if isinstance(t, nodes.Variable):
            return LinearTerm({t.name: 1}, "0") if t.name in binding else LinearTerm({}, t.name)
        if isinstance(t, nodes.Constant):
            return LinearTerm({}, str(t.value))
        if isinstance(t, nodes.Identifier):
            return LinearTerm({}, t.name)
        if isinstance(t, nodes.BinaryExpr) and t.op in ("+", "-"):
            a, b = self._linear(t.left, binding), self._linear(t.right, binding)
            coeffs = dict(a.coeffs)
            for v, k in b.coeffs.items():
                coeffs[v] = coeffs.get(v, 0) + (k if t.op == "+" else -k)
            return LinearTerm({v: k for v, k in coeffs.items() if k}, _add(a.const, b.const) if t.op == "+" else _sub(a.const, b.const))
        if isinstance(t, nodes.BinaryExpr):
            a, b = self._linear(t.left, binding), self._linear(t.right, binding)
            if a.coeffs or b.coeffs:
                raise NeedsOther(self._sort_of(next(iter(a.coeffs or b.coeffs)), binding), "enum", "Order sorts: a value is multiplied or divided; the sort is lowered by enumeration")
            return LinearTerm({}, f"({a.const} {t.op} {b.const})")
        raise TranspileError(f"Order sorts: unsupported term {t!r}")

    @staticmethod
    def _term_text(f: str, args: list) -> str:
        def t(a):
            if isinstance(a, nodes.Variable): return a.name
            if isinstance(a, nodes.Constant): return str(a.value)
            if isinstance(a, nodes.Identifier): return a.name
            raise TranspileError(f"Order sorts: unsupported function argument {a!r}")
        return f"{f}({', '.join(t(a) for a in args)})" if args else f

    @staticmethod
    def _mentions(comp: CompA, binding: dict) -> bool:
        def walk(t):
            if isinstance(t, nodes.Variable): return t.name in binding
            if isinstance(t, nodes.BinaryExpr): return walk(t.left) or walk(t.right)
            return False
        return walk(comp.left) or walk(comp.right)

    @staticmethod
    def _vars(it: Any) -> list[str]:
        try:
            return all_vars(it)
        except TranspileError:
            return []


def _add(a: str, b: str) -> str:
    if a == "0": return b
    if b == "0": return a
    return f"({a} + {b})"


def _sub(a: str, b: str) -> str:
    if b == "0": return a
    if a == "0": return str(-int(b)) if b.lstrip("-").isdigit() else f"(-{b})"
    if a.lstrip("-").isdigit() and b.lstrip("-").isdigit(): return str(int(a) - int(b))
    return f"({a} - {b})"


def _neg(a: str) -> str:
    return str(-int(a)) if a.lstrip("-").isdigit() else f"(-{a})"
