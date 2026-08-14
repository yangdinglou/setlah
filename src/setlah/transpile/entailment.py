"""
Entailment-Based Simplification
================================

Eliminate redundant literals based on entailment.
"""

from __future__ import annotations

import ast as pyast
from typing import Any

from .ir import TranspileError
from .pyast_utils import (
    _is_name, _is_attr,
    _const_str, _const_bool,
    _parse_set_call, _parse_vec_call,
)
from .rendering import _term_to_asp, _parse_varlist


# =============================================================================
# 12. ENTAILMENT-BASED SIMPLIFICATION
# =============================================================================


def _eliminate_entailed_general_lits(glits: list[pyast.AST], entailment_specs: Any) -> list[pyast.AST]:
    """Remove redundant entailed positive predicate literals from an integrity constraint.

    `entailment_specs` is expected to be a dict of:
      entailing_pred -> list[(entailed_pred, (pos0, pos1, ...))]

    Each position is the 0-based argument index in the entailing predicate.
    """
    if not isinstance(entailment_specs, dict):
        return glits

    # Index positive predicate literals by (pred, args-as-ASP-terms)
    pos_preds: dict[tuple[str, tuple[str, ...]], int] = {}
    for idx, gl in enumerate(glits):
        info = _positive_pred_sig(gl)
        if info is None:
            continue
        pos_preds[info] = idx

    to_remove: set[int] = set()
    for (pred_name, args_sig), idx_entailing in pos_preds.items():
        ent_list = entailment_specs.get(pred_name)
        if not ent_list:
            continue
        for entailed_pred, positions in ent_list:
            try:
                entailed_args = tuple(args_sig[p] for p in positions)
            except Exception:
                continue
            idx_entailed = pos_preds.get((entailed_pred, entailed_args))
            if idx_entailed is not None:
                to_remove.add(idx_entailed)

    if not to_remove:
        return glits
    return [gl for i, gl in enumerate(glits) if i not in to_remove]


def _positive_pred_sig(gl: pyast.AST) -> tuple[str, tuple[str, ...]] | None:
    """If `gl` is a positive predicate literal, return (pred_name, (arg0,...))."""
    lit = None

    # GeneralLit.from_literal(Literal(...))
    if isinstance(gl, pyast.Call) and _is_attr(gl.func, "GeneralLit", "from_literal") and len(gl.args) == 1:
        lit = gl.args[0]
    # Literal(...) directly
    elif isinstance(gl, pyast.Call) and _is_name(gl.func, "Literal"):
        lit = gl
    else:
        return None

    if not isinstance(lit, pyast.Call) or not _is_name(lit.func, "Literal") or len(lit.args) != 2:
        return None

    atom, sign = lit.args
    if not _const_bool(sign):
        return None

    if not (isinstance(atom, pyast.Call) and _is_attr(atom.func, "Atom", "Pred") and len(atom.args) == 2):
        return None

    pred_name = _const_str(atom.args[0])
    args = _parse_varlist(atom.args[1])
    args_sig = tuple(_term_to_asp(t) for t in args)
    return (pred_name, args_sig)


def _pred_lit_key(gl: pyast.AST, *, rename: dict[str, str]) -> tuple[str, tuple[str, ...]]:
    pred = _pos_pred_literal(gl)
    if pred is None:
        raise TranspileError("Internal error: expected positive predicate literal")
    pred_name, args = pred
    return (pred_name, tuple(_term_key(a, rename=rename) for a in args))


def _term_key(t: pyast.AST, *, rename: dict[str, str]) -> str:
    if isinstance(t, pyast.Call) and _is_attr(t.func, "Term", "Var") and len(t.args) == 1:
        name = _const_str(t.args[0])
        return f"Var({rename.get(name, name)})"
    if isinstance(t, pyast.Call) and _is_attr(t.func, "Term", "Int") and len(t.args) == 1:
        v = t.args[0]
        if isinstance(v, pyast.Constant) and isinstance(v.value, int):
            return f"Int({v.value})"
        return "Int(?)"
    if isinstance(t, pyast.Call) and _is_attr(t.func, "Term", "Symbol") and len(t.args) == 1:
        return f"Sym({_const_str(t.args[0])})"
    if isinstance(t, pyast.Call) and _is_attr(t.func, "Term", "BinaryExpr") and len(t.args) == 3:
        op = _const_str(t.args[0])
        return f"Bin({op},{_term_key(t.args[1], rename=rename)},{_term_key(t.args[2], rename=rename)})"
    # Fall back to ASP-ish rendering for unhandled term shapes.
    return _term_to_asp(t)


def _pos_pred_literal(gl: pyast.AST) -> tuple[str, list[pyast.AST]] | None:
    """If gl is a positive predicate literal, return (pred_name, args_terms)."""
    lit = None
    if isinstance(gl, pyast.Call) and _is_attr(gl.func, "GeneralLit", "from_literal") and len(gl.args) == 1:
        lit = gl.args[0]
    elif isinstance(gl, pyast.Call) and _is_name(gl.func, "Literal"):
        lit = gl
    else:
        return None

    if not (isinstance(lit, pyast.Call) and _is_name(lit.func, "Literal") and len(lit.args) == 2):
        return None
    atom, sign = lit.args
    if _const_bool(sign) is not True:
        return None

    if not (isinstance(atom, pyast.Call) and _is_attr(atom.func, "Atom", "Pred") and len(atom.args) == 2):
        return None
    pred_name = _const_str(atom.args[0])
    args = _parse_varlist(atom.args[1])
    return (pred_name, args)


def _term_var_name(t: pyast.AST) -> str | None:
    if isinstance(t, pyast.Call) and _is_attr(t.func, "Term", "Var") and len(t.args) == 1:
        return _const_str(t.args[0])
    return None


def _term_contains_var(t: pyast.AST, var_name: str) -> bool:
    if isinstance(t, pyast.Call) and _is_attr(t.func, "Term", "Var") and len(t.args) == 1:
        return _const_str(t.args[0]) == var_name
    if isinstance(t, pyast.Call) and _is_attr(t.func, "Term", "BinaryExpr") and len(t.args) == 3:
        return _term_contains_var(t.args[1], var_name) or _term_contains_var(t.args[2], var_name)
    return False


def _general_lit_mentions_var(gl: pyast.AST, var_name: str) -> bool:
    """Conservatively detect whether a GeneralLit contains a given Term.Var."""
    pred = _pos_pred_literal(gl)
    if pred is not None:
        _pred_name, args = pred
        return any(_term_contains_var(a, var_name) for a in args)

    # Comparisons: Atom.Comp(op, l, r)
    lit = None
    if isinstance(gl, pyast.Call) and _is_attr(gl.func, "GeneralLit", "from_literal") and len(gl.args) == 1:
        lit = gl.args[0]
    elif isinstance(gl, pyast.Call) and _is_name(gl.func, "Literal"):
        lit = gl

    if isinstance(lit, pyast.Call) and _is_name(lit.func, "Literal") and len(lit.args) == 2:
        atom = lit.args[0]
        if isinstance(atom, pyast.Call) and _is_attr(atom.func, "Atom", "Pred") and len(atom.args) == 2:
            args = _parse_varlist(atom.args[1])
            return any(_term_contains_var(arg, var_name) for arg in args)
        if isinstance(atom, pyast.Call) and _is_attr(atom.func, "Atom", "Comp") and len(atom.args) == 3:
            return _term_contains_var(atom.args[1], var_name) or _term_contains_var(atom.args[2], var_name)
    return False
