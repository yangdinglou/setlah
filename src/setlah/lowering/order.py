"""
Order sorts: the difference-logic lowering
==========================================

An ``OrdDOM`` sort is a bounded integer sort whose values occur only as the
last argument of ``Fun`` predicates and in comparisons with constant offsets
(docs/order-sorts.md). This pass rewrites the cubes the direct lowering
produces so that

- a functional atom ``f(a, V)`` binds the value variable ``V`` to the theory
  term ``f(a)`` and disappears from the cube (its argument variables stay
  bound by the other literals or by domain guards);
- a comparison over such values becomes one reified Boolean atom
  ``__dl_k(vars)`` whose truth is tied to the theory atom in both directions
  (``&diff{ t1 - t2 } <= c :- __dl_k(vars)`` and the strict converse under
  ``not __dl_k(vars)``), so the constraint or rule that contained the
  comparison mentions only Booleans (T4 in the design note);
- every ground function value is bounded by the sort's range.

The reification is exact for any valuation: for each ground instance exactly
one of ``__dl_k`` true / false is consistent with the theory. Comparisons
``!=`` split a cube into two (``<`` and ``>``). A value variable used
anywhere else (as an argument of an ordinary predicate, in an aggregate, or
in a sum of two values) is reported as unsupported: such a sort must be
declared ``DefDOM`` and lowered by enumeration instead.
"""

from __future__ import annotations

from typing import Any

from ..ast import nodes
from ..transpile.ir import TranspileError
from .formula import CompA, Lit, PredA


class NeedsTheory(TranspileError):
    """A sort lowered relationally met a comparison only difference logic can carry
    (an offset, a constant, or a distance); the automatic selection retries it as dl."""

    def __init__(self, sort: str, msg: str):
        super().__init__(msg)
        self.sort = sort


class LinearTerm:
    """``sum coeff_i * V_i + const_expr`` over order-sort variables ``V_i``; the
    difference of two sides is admitted when its net coefficients are one ``+1``
    and one ``-1`` at most (a difference constraint)."""

    def __init__(self, coeffs: dict, const: str):
        self.coeffs, self.const = coeffs, const


class OrderLowering:
    def __init__(self, functions: dict[str, tuple[list[str], str]], order_sorts: dict[str, tuple[int, int]], var_types_of, modes: dict[str, str] | None = None):
        self.functions = functions           # f -> (argument sorts, order sort)
        self.order_sorts = order_sorts       # sort -> (lo, hi)
        self.var_types_of = var_types_of     # callable: variable name -> sort name or None (for constant-side variables)
        self.modes = modes or {}             # sort -> "dl" | "rel"; default "dl"
        self.theory_rules: list[str] = []
        self.next_id = 0
        self._emit_ranges()

    def mode(self, sort: str) -> str:
        return self.modes.get(sort, self.modes.get("*", "dl"))

    def finalize(self) -> list[str]:
        """Rules that depend on the whole program: the preorder axioms of the
        relational lowering, one preorder per order sort (T2 in the design note)."""
        out: list[str] = []
        for sort, (lo, hi) in self.order_sorts.items():
            if self.mode(sort) != "rel":
                continue
            fs = [f for f, (_, s_) in self.functions.items() if s_ == sort]
            if not fs:
                continue
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

    # --- ranges ---------------------------------------------------------------

    def _emit_ranges(self) -> None:
        for f, (arg_sorts, sort) in self.functions.items():
            if self.mode(sort) != "dl":
                continue
            lo, hi = self.order_sorts[sort]
            args = [f"A{i}" for i in range(len(arg_sorts))]
            guards = ", ".join(f"dom_{s}({a})" for s, a in zip(arg_sorts, args))
            term = f"{f}({', '.join(args)})" if args else f
            body = f" :- {guards}" if guards else ""
            self.theory_rules.append(f"&diff{{ {term} }} <= {hi}{body}.")
            self.theory_rules.append(f"&diff{{ {term} }} >= {lo}{body}.")

    # --- cubes ------------------------------------------------------------------

    def rewrite_cube(self, cube: list, var_types: dict[str, str]) -> list[list]:
        """Rewrite one conjunction of items; returns the list of cubes that replace it
        (more than one when a ``!=`` over values is split)."""
        binding: dict[str, str] = {}      # value variable -> theory term text
        bound_args: dict[str, str] = {}   # argument variable -> its sort (from the Fun declaration)
        rest: list = []
        for it in cube:
            if isinstance(it, Lit) and isinstance(it.atom, PredA) and it.atom.name in self.functions:
                if not it.positive:
                    raise TranspileError(f"Order sorts: a negated function atom ({it.atom.name}) is not supported")
                arg_sorts, _ = self.functions[it.atom.name]
                *args, val = it.atom.args
                if not isinstance(val, nodes.Variable):
                    raise TranspileError(f"Order sorts: the value argument of {it.atom.name} must be a variable")
                text = self._term_text(it.atom.name, args)
                if val.name in binding and binding[val.name] != text:
                    # two functions equal to the same variable: keep the equality as a comparison
                    rest.append(Lit(CompA("==", nodes.Variable(name=val.name), nodes.Variable(name=val.name + "__eq")), True))
                    binding[val.name + "__eq"] = text
                else:
                    binding[val.name] = text
                for a, s in zip(args, arg_sorts):
                    if isinstance(a, nodes.Variable):
                        bound_args[a.name] = s
            else:
                rest.append(it)
        if not binding:
            return [cube]
        cubes: list[list] = [[]]
        for it in rest:
            if isinstance(it, Lit) and isinstance(it.atom, CompA) and self._mentions(it.atom, binding):
                alternatives = self.reify(it.atom, it.positive, binding, bound_args, var_types)
                cubes = [c + [alt] for c in cubes for alt in alternatives]
            else:
                if self._touches(it, binding):
                    raise TranspileError("Order sorts: a value variable may occur only in comparisons and function atoms")
                cubes = [c + [it] for c in cubes]
        # argument variables the remaining literals leave unbound get their sort's guard
        out: list[list] = []
        for c in cubes:
            positively = set()
            for it in c:
                if isinstance(it, Lit) and it.positive and isinstance(it.atom, PredA):
                    positively.update(t.name for t in it.atom.args if isinstance(t, nodes.Variable))
            guards = [Lit(PredA(f"dom_{s}", (nodes.Variable(name=v),)), True) for v, s in bound_args.items() if v not in positively]
            out.append(guards + c)
        return out

    def rewrite_rule_body(self, body: list, var_types: dict[str, str]) -> list[list]:
        """Same for a rule body (positive literals); returns alternative bodies."""
        cube = []
        for lit in body:
            if isinstance(lit, nodes.PredAtom):
                cube.append(Lit(PredA(lit.predicate.name, tuple(lit.args)), True))
            elif isinstance(lit, nodes.Comparison):
                cube.append(Lit(CompA(lit.op, lit.left, lit.right), True))
            else:
                raise TranspileError(f"Unsupported rule body literal: {lit!r}")
        return self.rewrite_cube(cube, var_types)

    # --- comparisons ------------------------------------------------------------

    def reify(self, comp: CompA, positive: bool, binding: dict, bound_args: dict, var_types: dict) -> list[Lit]:
        """Reified literal(s) for ``comp`` (a list of alternatives, one per cube)."""
        left, right = self._linear(comp.left, binding), self._linear(comp.right, binding)
        # normalise to  x - y  op  const  with  net coefficients from left - right
        net: dict = dict(left.coeffs)
        for v, k in right.coeffs.items():
            net[v] = net.get(v, 0) - k
        net = {v: k for v, k in net.items() if k}
        pos = [v for v, k in net.items() if k == 1]; neg = [v for v, k in net.items() if k == -1]
        if len(pos) + len(neg) != len(net) or len(pos) > 1 or len(neg) > 1:
            raise TranspileError("Order sorts: the comparison is not a difference constraint (at most one value on each side, coefficient 1); declare the sort DefDOM for enumeration")
        x = pos[0] if pos else None; y = neg[0] if neg else None
        const = self._sub(right.const, left.const)
        op = comp.op if positive else {"==": "!=", "!=": "==", "<": ">=", ">=": "<", ">": "<=", "<=": ">"}[comp.op]
        sort = self._sort_of(x or y, binding)
        if self.mode(sort) == "rel":
            return self._relational(x, y, const, op, binding, sort)
        # each alternative: (x, y, c, sign) meaning  sign * (x - y <= c)
        if op == "<=": alts = [[(x, y, const, True)]]
        elif op == "<": alts = [[(x, y, self._sub(const, "1"), True)]]
        elif op == ">=": alts = [[(y, x, self._neg(const), True)]]
        elif op == ">": alts = [[(y, x, self._sub(self._neg(const), "1"), True)]]
        elif op == "==": alts = [[(x, y, const, True), (y, x, self._neg(const), True)]]
        elif op == "!=": alts = [[(x, y, self._sub(const, "1"), True)], [(y, x, self._sub(self._neg(const), "1"), True)]]
        else: raise TranspileError(f"Order sorts: unsupported comparison {op}")
        out: list = []
        for conj in alts:
            lits = [self._reified(x_, y_, c_, s_, binding, bound_args, var_types) for x_, y_, c_, s_ in conj]
            out.append(lits)
        # a conjunction of two reified literals inside one cube: flatten by returning a marker list
        return [_Conj(l) if len(l) > 1 else l[0] for l in out]

    def _sort_of(self, var: str, binding: dict) -> str:
        f = binding[var].split("(")[0]
        return self.functions[f][1]

    def _relational(self, x, y, const: str, op: str, binding: dict, sort: str) -> list:
        """Literals over the sort's preorder ``__le_S`` (no values): admitted only
        for comparisons between two function terms of the sort with no offset."""
        if x is None or y is None or const != "0":
            raise NeedsTheory(sort, f"Order sorts: sort {sort} is lowered relationally, which admits only comparisons between two values without offsets; use the difference-logic lowering for it")
        if self._sort_of(y, binding) != sort:
            raise TranspileError("Order sorts: comparison between values of different sorts")
        le = f"__le_{sort}"
        tx, ty = binding[x], binding[y]
        def lit(a, b, sign): return Lit(PredA(le, (nodes.Identifier(name=a), nodes.Identifier(name=b))), sign)
        if op == "<=": return [lit(tx, ty, True)]
        if op == ">=": return [lit(ty, tx, True)]
        if op == "<": return [_Conj([lit(tx, ty, True), lit(ty, tx, False)])]
        if op == ">": return [_Conj([lit(ty, tx, True), lit(tx, ty, False)])]
        if op == "==": return [_Conj([lit(tx, ty, True), lit(ty, tx, True)])]
        if op == "!=": return [lit(tx, ty, False), lit(ty, tx, False)]   # two alternatives: not (x <= y), or not (y <= x)
        raise TranspileError(f"Order sorts: unsupported comparison {op}")

    def _reified(self, x, y, c: str, sign: bool, binding: dict, bound_args: dict, var_types: dict) -> Lit:
        """Boolean ``__dl_k(vars)`` with  __dl_k <-> (x - y <= c)."""
        tx = binding[x] if x else "0"; ty = binding[y] if y else "0"
        vars_ = []
        for name in self._vars_of(tx) + self._vars_of(ty) + self._vars_in_const(c):
            if name not in vars_:
                vars_.append(name)
        k = self.next_id; self.next_id += 1
        head = f"__dl_{k}({', '.join(vars_)})" if vars_ else f"__dl_{k}"
        guards = []
        for v in vars_:
            s = bound_args.get(v) or var_types.get(v) or self.var_types_of(v)
            if s is None:
                raise TranspileError(f"Order sorts: cannot determine the sort of variable {v} in a comparison")
            guards.append(f"dom_{s}({v})")
        body = f" :- {', '.join(guards)}" if guards else ""
        self.theory_rules.append(f"{{ {head} }}{body}.")
        self.theory_rules.append(f"&diff{{ {tx} - {ty} }} <= {c} :- {head}.")
        self.theory_rules.append(f"&diff{{ {ty} - {tx} }} <= {self._sub(self._neg(c), '1')} :- not {head}{', ' + ', '.join(guards) if guards else ''}.")
        return Lit(PredA(f"__dl_{k}", tuple(nodes.Variable(name=v) for v in vars_)), sign)

    # --- helpers ----------------------------------------------------------------

    def _linear(self, t: Any, binding: dict) -> LinearTerm:
        if isinstance(t, nodes.Variable):
            if t.name in binding:
                return LinearTerm({t.name: 1}, "0")
            return LinearTerm({}, t.name)
        if isinstance(t, nodes.Constant):
            return LinearTerm({}, str(t.value))
        if isinstance(t, nodes.Identifier):
            return LinearTerm({}, t.name)
        if isinstance(t, nodes.BinaryExpr) and t.op in ("+", "-"):
            a, b = self._linear(t.left, binding), self._linear(t.right, binding)
            coeffs = dict(a.coeffs)
            for v, k in b.coeffs.items():
                coeffs[v] = coeffs.get(v, 0) + (k if t.op == "+" else -k)
            return LinearTerm({v: k for v, k in coeffs.items() if k}, self._add(a.const, b.const) if t.op == "+" else self._sub(a.const, b.const))
        if isinstance(t, nodes.BinaryExpr):
            a, b = self._linear(t.left, binding), self._linear(t.right, binding)
            if a.coeffs or b.coeffs:
                raise TranspileError("Order sorts: a value may not be multiplied or divided")
            return LinearTerm({}, f"({a.const} {t.op} {b.const})")
        raise TranspileError(f"Order sorts: unsupported term {t!r}")

    @staticmethod
    def _add(a: str, b: str) -> str:
        if a == "0": return b
        if b == "0": return a
        return f"({a} + {b})"

    @staticmethod
    def _sub(a: str, b: str) -> str:
        if b == "0": return a
        if a == "0": return f"(-{b})" if not b.lstrip("-").isdigit() else str(-int(b))
        if a.lstrip("-").isdigit() and b.lstrip("-").isdigit(): return str(int(a) - int(b))
        return f"({a} - {b})"

    @staticmethod
    def _neg(a: str) -> str:
        if a.lstrip("-").isdigit(): return str(-int(a))
        return f"(-{a})"

    @staticmethod
    def _term_text(f: str, args: list) -> str:
        def t(a):
            if isinstance(a, nodes.Variable): return a.name
            if isinstance(a, nodes.Constant): return str(a.value)
            if isinstance(a, nodes.Identifier): return a.name
            raise TranspileError(f"Order sorts: unsupported function argument {a!r}")
        return f"{f}({', '.join(t(a) for a in args)})" if args else f

    @staticmethod
    def _vars_of(text: str) -> list[str]:
        import re
        return [v for v in re.findall(r"\b[A-Z][A-Za-z0-9_']*", text)]

    _vars_in_const = _vars_of

    @staticmethod
    def _mentions(comp: CompA, binding: dict) -> bool:
        def walk(t):
            if isinstance(t, nodes.Variable): return t.name in binding
            if isinstance(t, nodes.BinaryExpr): return walk(t.left) or walk(t.right)
            return False
        return walk(comp.left) or walk(comp.right)

    @staticmethod
    def _touches(it: Any, binding: dict) -> bool:
        from .formula import all_vars
        try:
            return any(v in binding for v in all_vars(it))
        except TranspileError:
            return False


class _Conj(list):
    """A conjunction of reified literals standing in for one cube item."""
