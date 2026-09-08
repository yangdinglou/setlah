"""
Formula core for the direct lowering
====================================

A small first-order formula representation in negation normal form (NNF),
built directly from the parser's AST (``ast/nodes.py``) by a syntax-directed
walk. Quantified subformulas are kept as nodes; the lowering treats them as
opaque items of a cube and turns them into auxiliary predicates.

Atoms keep the parser's terms (``Variable``, ``Constant``, ``Identifier``,
``BinaryExpr``) unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from typing import Iterable

from ..ast import nodes
from ..transpile.ir import TranspileError


# --- atoms -------------------------------------------------------------------

@dataclass(frozen=True)
class PredA:
    name: str
    args: tuple  # parser terms


@dataclass(frozen=True)
class CompA:
    op: str      # "==", "!=", "<", "<=", ">", ">="
    left: object
    right: object


@dataclass(frozen=True)
class AggA:
    """A projected count aggregate ``#count {Set_p}(counted) comp value``.

    ``pred`` is the full atom over the predicate's canonical argument list
    (the converter's desugaring); ``counted`` names the projected variables.
    """
    op: str
    counted: tuple  # parser terms
    pred: PredA
    comp: str
    value: object


# --- formulas ----------------------------------------------------------------

@dataclass(frozen=True)
class Lit:
    atom: object          # PredA | CompA | AggA
    positive: bool


@dataclass(frozen=True)
class Const:
    value: bool


@dataclass(frozen=True)
class And:
    items: tuple


@dataclass(frozen=True)
class Or:
    items: tuple


@dataclass(frozen=True)
class Exists:
    vars: tuple  # variable names
    body: object


@dataclass(frozen=True)
class Forall:
    vars: tuple
    body: object


TRUE = Const(True)
FALSE = Const(False)

_COMP_NEG = {"==": "!=", "!=": "==", "<": ">=", ">=": "<", ">": "<=", "<=": ">"}


def negate_comp(op: str) -> str:
    try:
        return _COMP_NEG[op]
    except KeyError:
        raise TranspileError(f"Cannot negate comparison operator {op!r}")


def make_and(items: Iterable) -> object:
    flat: list = []
    for it in items:
        if isinstance(it, Const):
            if not it.value:
                return FALSE
            continue
        if isinstance(it, And):
            flat.extend(it.items)
        else:
            flat.append(it)
    if not flat:
        return TRUE
    if len(flat) == 1:
        return flat[0]
    return And(tuple(flat))


def make_or(items: Iterable) -> object:
    flat: list = []
    for it in items:
        if isinstance(it, Const):
            if it.value:
                return TRUE
            continue
        if isinstance(it, Or):
            flat.extend(it.items)
        else:
            flat.append(it)
    if not flat:
        return FALSE
    if len(flat) == 1:
        return flat[0]
    return Or(tuple(flat))


def make_exists(vars: tuple, body: object) -> object:
    if isinstance(body, Const):
        return body
    if isinstance(body, Exists):
        return Exists(tuple(vars) + body.vars, body.body)
    return Exists(tuple(vars), body)


def make_forall(vars: tuple, body: object) -> object:
    if isinstance(body, Const):
        return body
    if isinstance(body, Forall):
        return Forall(tuple(vars) + body.vars, body.body)
    return Forall(tuple(vars), body)


def negate(f: object) -> object:
    """Negation of an NNF formula, in NNF."""
    if isinstance(f, Lit):
        return Lit(f.atom, not f.positive)
    if isinstance(f, Const):
        return Const(not f.value)
    if isinstance(f, And):
        return make_or(negate(x) for x in f.items)
    if isinstance(f, Or):
        return make_and(negate(x) for x in f.items)
    if isinstance(f, Exists):
        return make_forall(f.vars, negate(f.body))
    if isinstance(f, Forall):
        return make_exists(f.vars, negate(f.body))
    raise TranspileError(f"negate: unexpected formula {f!r}")


# --- variables ---------------------------------------------------------------

def term_vars(t: object, out: dict) -> None:
    """Variable names of a parser term, in order of first occurrence."""
    if isinstance(t, nodes.Variable):
        out.setdefault(t.name, None)
    elif isinstance(t, nodes.BinaryExpr):
        term_vars(t.left, out)
        term_vars(t.right, out)
    elif isinstance(t, nodes.TupleVar):
        for e in t.elements:
            term_vars(e, out)


def atom_vars(a: object) -> list[str]:
    out: dict = {}
    if isinstance(a, PredA):
        for t in a.args:
            term_vars(t, out)
    elif isinstance(a, CompA):
        term_vars(a.left, out)
        term_vars(a.right, out)
    elif isinstance(a, AggA):
        counted: dict = {}
        for t in a.counted:
            term_vars(t, counted)
        for t in a.pred.args:
            term_vars(t, out)
        term_vars(a.value, out)
        for c in counted:
            out.pop(c, None)
    return list(out)


def free_vars(f: object) -> list[str]:
    """Free variables of an NNF formula, in order of first occurrence."""
    out: dict = {}

    def walk(g: object, bound: frozenset) -> None:
        if isinstance(g, Lit):
            for v in atom_vars(g.atom):
                if v not in bound:
                    out.setdefault(v, None)
        elif isinstance(g, (And, Or)):
            for x in g.items:
                walk(x, bound)
        elif isinstance(g, (Exists, Forall)):
            walk(g.body, bound | frozenset(g.vars))
        elif isinstance(g, Const):
            pass
        else:
            raise TranspileError(f"free_vars: unexpected formula {g!r}")

    walk(f, frozenset())
    return list(out)


def all_vars(f: object) -> list[str]:
    """Every variable name occurring in ``f``, free or bound, in order of first occurrence."""
    out: dict = {}

    def walk(g: object) -> None:
        if isinstance(g, Lit):
            for v in atom_vars(g.atom):
                out.setdefault(v, None)
            if isinstance(g.atom, AggA):
                for t in g.atom.counted:
                    term_vars(t, out)
        elif isinstance(g, (And, Or)):
            for x in g.items:
                walk(x)
        elif isinstance(g, (Exists, Forall)):
            for v in g.vars:
                out.setdefault(v, None)
            walk(g.body)

    walk(f)
    return list(out)


def var_occurrences(f: object, name: str) -> int:
    """Number of occurrences of variable ``name`` in the atoms of ``f`` (no binders crossed)."""
    n = 0

    def count_term(t: object) -> None:
        nonlocal n
        if isinstance(t, nodes.Variable):
            if t.name == name:
                n += 1
        elif isinstance(t, nodes.BinaryExpr):
            count_term(t.left)
            count_term(t.right)

    def walk(g: object) -> None:
        if isinstance(g, Lit):
            a = g.atom
            if isinstance(a, PredA):
                for t in a.args:
                    count_term(t)
            elif isinstance(a, CompA):
                count_term(a.left)
                count_term(a.right)
            elif isinstance(a, AggA):
                for t in a.pred.args:
                    count_term(t)
                count_term(a.value)
        elif isinstance(g, (And, Or)):
            for x in g.items:
                walk(x)
        elif isinstance(g, (Exists, Forall)):
            if name not in g.vars:
                walk(g.body)

    walk(f)
    return n


# --- NNF from the parser's AST ----------------------------------------------

class NNFBuilder:
    """Builds NNF formulas from ``nodes.FoSet``; ``canonical_args`` (from the
    checker) expands projected aggregates to the predicate's full argument
    list, as the converter does."""

    def __init__(self, canonical_args: dict[str, list[str]]):
        self.canonical_args = canonical_args

    def build(self, node: nodes.FoSet, positive: bool = True) -> object:
        if isinstance(node, nodes.PredAtom):
            return Lit(PredA(node.predicate.name, tuple(node.args)), positive)
        if isinstance(node, nodes.Comparison):
            return Lit(CompA(node.op, node.left, node.right), positive)
        if isinstance(node, nodes.BooleanConst):
            return Const(bool(node.val) == positive)
        if isinstance(node, nodes.LogicalOp):
            op = node.op
            if op == "and":
                items = [self.build(x, positive) for x in node.operands]
                return make_and(items) if positive else make_or(items)
            if op == "or":
                items = [self.build(x, positive) for x in node.operands]
                return make_or(items) if positive else make_and(items)
            if op == "not":
                if len(node.operands) != 1:
                    raise TranspileError("not requires exactly one operand")
                return self.build(node.operands[0], not positive)
            if op == "impl":
                if len(node.operands) != 2:
                    raise TranspileError("impl requires exactly two operands")
                a, b = node.operands
                if positive:
                    return make_or([self.build(a, False), self.build(b, True)])
                return make_and([self.build(a, True), self.build(b, False)])
            raise TranspileError(f"Unknown logical operator {op!r}")
        if isinstance(node, nodes.QuantifiedFormula):
            q = node.quantifier
            body = self.build(node.body, positive)
            universal = q in ("forall", "∀")
            if q not in ("forall", "∀", "exists", "∃"):
                raise TranspileError(f"Unknown quantifier {q!r}")
            if universal == positive:
                return make_forall((node.variable.name,), body)
            return make_exists((node.variable.name,), body)
        if isinstance(node, nodes.Aggregation):
            return Lit(self.aggregate(node), positive)
        raise TranspileError(
            f"The direct lowering does not support {type(node).__name__} inside a formula: {node}"
        )

    def aggregate(self, node: nodes.Aggregation) -> AggA:
        if not node.set_var.parameters:
            raise TranspileError(
                "The direct lowering supports aggregates only in the projected form #count {Set_p}(vars) op value"
            )
        set_name = node.set_var.name
        pred_name = set_name[4:] if set_name.startswith("Set_") else set_name
        pred_name = pred_name.lower()
        counted = tuple(node.set_var.parameters.elements)
        counted_names = {p.name for p in counted if isinstance(p, nodes.Variable)}
        canonical = self.canonical_args.get(pred_name, [])
        if canonical and len(counted) < len(canonical):
            full: list = []
            for arg_name in canonical:
                if arg_name in counted_names:
                    full.append(next(p for p in counted if isinstance(p, nodes.Variable) and p.name == arg_name))
                else:
                    full.append(nodes.Variable(name=arg_name))
            args = tuple(full)
        else:
            args = counted
        op = node.op.lstrip("#") if node.op.startswith("#") else node.op
        return AggA(op, counted, PredA(pred_name, args), node.comp_op, node.value)


# --- DNF over cubes ----------------------------------------------------------

def dnf(f: object) -> list[list]:
    """Cubes of an NNF formula; quantified subformulas are atomic items.

    ``[[]]`` is the single empty cube (true); ``[]`` is no cube (false).
    """
    if isinstance(f, (Lit, Exists, Forall)):
        return [[f]]
    if isinstance(f, Const):
        return [[]] if f.value else []
    if isinstance(f, Or):
        out: list[list] = []
        for x in f.items:
            out.extend(dnf(x))
        return out
    if isinstance(f, And):
        cubes: list[list] = [[]]
        for x in f.items:
            part = dnf(x)
            cubes = [c + d for c in cubes for d in part]
            if not cubes:
                return []
        return cubes
    raise TranspileError(f"dnf: unexpected formula {f!r}")


def dnf_size(f: object) -> int:
    """Number of cubes ``dnf`` would produce, without building them."""
    if isinstance(f, (Lit, Exists, Forall)):
        return 1
    if isinstance(f, Const):
        return 1 if f.value else 0
    if isinstance(f, Or):
        return sum(dnf_size(x) for x in f.items)
    if isinstance(f, And):
        return reduce(lambda a, b: a * b, (dnf_size(x) for x in f.items), 1)
    raise TranspileError(f"dnf_size: unexpected formula {f!r}")
