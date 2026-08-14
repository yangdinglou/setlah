"""
Python-AST Helpers
==================

Utilities for working with Python AST parsed from egg expressions.
"""

from __future__ import annotations

import ast as pyast
from typing import Any

from .ir import IRRule, IRConstraint, TranspileError


# =============================================================================
# 6. PYTHON-AST HELPERS
# =============================================================================


def _is_name(n: pyast.AST, name: str) -> bool:
    return isinstance(n, pyast.Name) and n.id == name


def _is_attr(n: pyast.AST, base: str, attr: str) -> bool:
    return (
        isinstance(n, pyast.Attribute)
        and isinstance(n.value, pyast.Name)
        and n.value.id == base
        and n.attr == attr
    )


def _call_func_name(n: pyast.Call) -> str | None:
    f = n.func
    if isinstance(f, pyast.Name):
        return f.id
    if isinstance(f, pyast.Attribute) and isinstance(f.value, pyast.Name):
        return f"{f.value.id}.{f.attr}"
    if isinstance(f, pyast.Subscript) and isinstance(f.value, pyast.Name):
        return f.value.id
    return None


def _const_str(n: pyast.AST) -> str:
    if isinstance(n, pyast.Constant) and isinstance(n.value, str):
        return n.value
    raise TranspileError(f"Expected string constant, got: {pyast.dump(n)}")


def _const_bool(n: pyast.AST) -> bool:
    if isinstance(n, pyast.Constant) and isinstance(n.value, bool):
        return n.value
    raise TranspileError(f"Expected bool constant, got: {pyast.dump(n)}")


def _parse_vec_call(n: pyast.AST) -> list[pyast.AST]:
    if not isinstance(n, pyast.Call):
        raise TranspileError(f"Expected Vec[...] call, got: {pyast.dump(n)}")
    # Vec[T](a,b,c) or Vec[T]()
    return list(n.args)


def _parse_set_call(n: pyast.AST) -> list[pyast.AST]:
    # egglog sometimes pretty-prints set unions using Python's `|` operator:
    #   Set[T]() | Set(x, y)
    if isinstance(n, pyast.BinOp) and isinstance(n.op, pyast.BitOr):
        return _parse_set_call(n.left) + _parse_set_call(n.right)
    if not isinstance(n, pyast.Call):
        raise TranspileError(f"Expected Set[...] call, got: {pyast.dump(n)}")
    return list(n.args)


def _unroll_conslist(n: pyast.AST) -> list[pyast.AST]:
    # cons_constraint(head, tail) ... nil_constraint()
    items: list[pyast.AST] = []
    cur = n
    while True:
        if isinstance(cur, pyast.Call) and _call_func_name(cur) == "nil_constraint":
            return items
        if isinstance(cur, pyast.Call) and _call_func_name(cur) == "cons_constraint":
            if len(cur.args) != 2:
                raise TranspileError("cons_constraint expects 2 args")
            head, tail = cur.args
            items.append(head)
            cur = tail
            continue
        if isinstance(cur, pyast.List):
            # In case it printed as a Python list
            items.extend(cur.elts)
            return items
        raise TranspileError(f"Unsupported constraint list form: {pyast.dump(cur)}")
