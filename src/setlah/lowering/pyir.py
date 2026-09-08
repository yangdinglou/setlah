"""
IR node builders
================

The transpiler's kept passes (``transpile/rendering.py``, ``constraint.py``,
``merge.py``, ``safety.py``, ``rewrite.py``) consume Python ``ast`` nodes in
the shape of egglog's printed terms: ``Term.Var("X")``, ``Atom.Pred("p",
cons_var(...))``, ``GeneralLit.from_literal(Literal(atom, True))`` and so on.
These helpers build exactly those nodes, so the direct lowering can hand the
kept passes the IR they already understand without printing or parsing any
text.
"""

from __future__ import annotations

import ast as pyast
from typing import Any


def _load(name: str) -> pyast.Name:
    return pyast.Name(id=name, ctx=pyast.Load())


def _attr(base: str, attr: str) -> pyast.Attribute:
    return pyast.Attribute(value=_load(base), attr=attr, ctx=pyast.Load())


def _call(func: pyast.expr, args: list[pyast.expr]) -> pyast.Call:
    return pyast.Call(func=func, args=list(args), keywords=[])


def const(value: Any) -> pyast.Constant:
    return pyast.Constant(value=value)


def _generic_call(container: str, elem: str, items: list[pyast.expr]) -> pyast.Call:
    """``Set[T](...)`` / ``Vec[T](...)``."""
    func = pyast.Subscript(value=_load(container), slice=_load(elem), ctx=pyast.Load())
    return _call(func, items)


def set_of(elem: str, items: list[pyast.expr]) -> pyast.Call:
    return _generic_call("Set", elem, items)


def vec_of(elem: str, items: list[pyast.expr]) -> pyast.Call:
    return _generic_call("Vec", elem, items)


# --- terms -------------------------------------------------------------------

def term_var(name: str) -> pyast.Call:
    return _call(_attr("Term", "Var"), [const(name)])


def term_int(value: int) -> pyast.Call:
    return _call(_attr("Term", "Int"), [const(value)])


def term_symbol(name: str) -> pyast.Call:
    return _call(_attr("Term", "Symbol"), [const(name)])


def term_anon() -> pyast.Call:
    return _call(_attr("Term", "Anon"), [])


def term_binexpr(op: str, left: pyast.expr, right: pyast.expr) -> pyast.Call:
    return _call(_attr("Term", "BinaryExpr"), [const(op), left, right])


def varlist(terms: list[pyast.expr]) -> pyast.Call:
    """``cons_var(t1, cons_var(t2, nil_var()))``."""
    out: pyast.Call = _call(_load("nil_var"), [])
    for t in reversed(terms):
        out = _call(_load("cons_var"), [t, out])
    return out


# --- atoms and literals ------------------------------------------------------

def atom_pred(name: str, terms: list[pyast.expr]) -> pyast.Call:
    return _call(_attr("Atom", "Pred"), [const(name), varlist(terms)])


def atom_comp(op: str, left: pyast.expr, right: pyast.expr) -> pyast.Call:
    return _call(_attr("Atom", "Comp"), [const(op), left, right])


def literal(atom: pyast.expr, sign: bool) -> pyast.Call:
    return _call(_load("Literal"), [atom, const(bool(sign))])


def general_lit(lit: pyast.expr) -> pyast.Call:
    return _call(_attr("GeneralLit", "from_literal"), [lit])


def general_agg(op: str, body: pyast.expr, comp: str, value: pyast.expr) -> pyast.Call:
    return _call(_attr("GeneralLit", "general_agg"), [const(op), body, const(comp), value])


def agg_body(counted: list[pyast.expr], cubes: list[pyast.expr]) -> pyast.Call:
    return _call(_attr("AggBody", "set_comprehension"), [set_of("Term", counted), vec_of("Formula", cubes)])


# --- formulas ----------------------------------------------------------------

def formula_lit(glit: pyast.expr) -> pyast.Call:
    return _call(_attr("Formula", "Lit"), [glit])


def formula_and(left: pyast.expr, right: pyast.expr) -> pyast.Call:
    return _call(_attr("Formula", "And"), [left, right])


def formula_or(left: pyast.expr, right: pyast.expr) -> pyast.Call:
    return _call(_attr("Formula", "Or"), [left, right])


def formula_not(inner: pyast.expr) -> pyast.Call:
    return _call(_attr("Formula", "Not"), [inner])


def formula_forall(var: pyast.expr, body: pyast.expr) -> pyast.Call:
    return _call(_attr("Formula", "Forall"), [var, body])


def formula_partition(target: pyast.expr, parts: list[pyast.expr]) -> pyast.Call:
    return _call(_attr("Formula", "Partition"), [target, vec_of("Term", parts)])


def formula_agg(op: str, set_expr: pyast.expr, comp: str, value: pyast.expr) -> pyast.Call:
    return _call(_attr("Formula", "Agg"), [const(op), set_expr, const(comp), value])


def setexpr_setvar(name: str, terms: list[pyast.expr]) -> pyast.Call:
    return _call(_attr("SetExpr", "SetVar"), [const(name), varlist(terms)])
