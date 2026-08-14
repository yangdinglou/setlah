"""
ASP Rendering
=============

Convert IR to ASP strings.
"""

from __future__ import annotations

import ast as pyast
from typing import Any

from .ir import IRRule, IRConstraint, TranspileError
from .pyast_utils import (
    _is_name, _is_attr, _call_func_name,
    _const_str, _const_bool,
    _parse_vec_call, _parse_set_call,
)


# =============================================================================
# 8. ASP RENDERING
# =============================================================================


def _rule_to_asp(r: IRRule) -> str:
    # Handle head: now it's an Atom, not a Formula
    head_str = _atom_to_asp(r.head)
    body_lits = []
    for b in r.body:
        body_lits.extend(_formula_to_body_lits(b))

    body_str = ", ".join(body_lits)

    if r.is_choice:
        head_str = "{" + head_str + "}"

    if body_str:
        return f"{head_str} :- {body_str}."
    return f"{head_str}."


def _formula_to_asp_head(n: pyast.AST) -> str:
    # Expecting a literal-like formula
    # Formula.Lit(GeneralLit.from_literal(Literal(Atom.Pred(...), True)))
    # Or Formula.Lit(Literal(...)) via converters in repr.
    lits = _formula_to_body_lits(n)
    if len(lits) != 1:
        raise TranspileError(f"Rule head expected 1 literal, got {lits}")
    lit = lits[0]
    if lit.startswith("not "):
        raise TranspileError("Rule head cannot be negated")
    if lit.startswith("#"):
        raise TranspileError("Rule head cannot be aggregate")
    return lit


def _formula_to_body_lits(n: pyast.AST) -> list[str]:
    # grouped_and(Set[GeneralLit](...))
    if isinstance(n, pyast.Call) and _is_attr(n.func, "Formula", "grouped_and"):
        if len(n.args) != 1:
            raise TranspileError("grouped_and expects 1 arg")
        gl_set = n.args[0]
        items = _parse_set_call(gl_set)
        return [_general_lit_to_body_lit(x) for x in items]

    # grouped_and_lit(Set[GeneralLit](...))
    if isinstance(n, pyast.Call) and _is_attr(n.func, "Formula", "grouped_and_lit"):
        if len(n.args) != 1:
            raise TranspileError("grouped_and_lit expects 1 arg")
        gl_set = n.args[0]
        items = _parse_set_call(gl_set)
        return [_general_lit_to_body_lit(x) for x in items]

    # Formula.Lit(x)
    if isinstance(n, pyast.Call) and _is_attr(n.func, "Formula", "Lit"):
        if len(n.args) != 1:
            raise TranspileError("Formula.Lit expects 1 arg")
        return [_general_lit_to_body_lit(n.args[0])]

    # Formula.And(a,b)
    if isinstance(n, pyast.Call) and _is_attr(n.func, "Formula", "And"):
        if len(n.args) != 2:
            raise TranspileError("And expects 2 args")
        return _formula_to_body_lits(n.args[0]) + _formula_to_body_lits(n.args[1])

    # Bool(True/False)
    if isinstance(n, pyast.Call) and _is_attr(n.func, "Formula", "Bool"):
        val = n.args[0] if n.args else None
        if isinstance(val, pyast.Constant) and val.value is True:
            return []
        if isinstance(val, pyast.Constant) and val.value is False:
            return ["#false"]

    raise TranspileError(f"Unsupported Formula in body: {pyast.dump(n)}")


def _general_lit_to_body_lit(n: pyast.AST) -> str:
    # GeneralLit.from_literal(Literal(...))
    if isinstance(n, pyast.Call) and _is_attr(n.func, "GeneralLit", "from_literal"):
        if len(n.args) != 1:
            raise TranspileError("from_literal expects 1 arg")
        return _literal_to_body_lit(n.args[0])

    # GeneralLit.general_agg(...)
    if isinstance(n, pyast.Call) and _is_attr(n.func, "GeneralLit", "general_agg"):
        if len(n.args) != 4:
            raise TranspileError("general_agg expects 4 args")
        op, body, comp, val = n.args
        op_s = _const_str(op)
        comp_s = _const_str(comp)
        if comp_s == "==":
            comp_s = "="
        if op_s != "count":
            raise TranspileError(f"Only count aggregate supported, got {op_s}")
        agg = _agg_body_to_asp_count(body)
        return f"{agg} {comp_s} {_term_to_asp(val)}"

    # Allow Literal(...) directly (due to converters)
    if isinstance(n, pyast.Call) and _is_name(n.func, "Literal"):
        return _literal_to_body_lit(n)

    raise TranspileError(f"Unsupported GeneralLit: {pyast.dump(n)}")


def _literal_to_body_lit(n: pyast.AST) -> str:
    if not isinstance(n, pyast.Call) or not _is_name(n.func, "Literal"):
        raise TranspileError(f"Expected Literal(atom, sign), got {pyast.dump(n)}")
    if len(n.args) != 2:
        raise TranspileError("Literal expects 2 args")

    atom, sign = n.args
    sign_b = _const_bool(sign)
    atom_s = _atom_to_asp(atom)
    if sign_b:
        return atom_s
    # default negation
    if atom_s.startswith("("):
        return f"not {atom_s}"
    return f"not {atom_s}"


def _atom_to_asp(n: pyast.AST) -> str:
    # Atom.Pred(name, args)
    if isinstance(n, pyast.Call) and _is_attr(n.func, "Atom", "Pred"):
        if len(n.args) != 2:
            raise TranspileError("Atom.Pred expects 2 args")
        name = _const_str(n.args[0])
        args_node = n.args[1]
        args = _parse_varlist(args_node)
        if not args:
            return f"{name}"
        return f"{name}({', '.join(_term_to_asp(t) for t in args)})"

    # Atom.Comp(op, l, r)
    if isinstance(n, pyast.Call) and _is_attr(n.func, "Atom", "Comp"):
        if len(n.args) != 3:
            raise TranspileError("Atom.Comp expects 3 args")
        op = _const_str(n.args[0])
        if op == "==":
            op = "="
        l = _term_to_asp(n.args[1])
        r = _term_to_asp(n.args[2])
        return f"{l} {op} {r}"

    raise TranspileError(f"Unsupported Atom: {pyast.dump(n)}")


def _parse_varlist(n: pyast.AST) -> list[pyast.AST]:
    # VarList converters mean we might see list([...]) in repr
    if isinstance(n, pyast.List):
        return list(n.elts)
    # Handle empty varlist: nil_var()
    if isinstance(n, pyast.Call) and _call_func_name(n) == "nil_var":
        return []
    if isinstance(n, pyast.Call) and _call_func_name(n) == "cons_var":
        # cons_var(head, tail) chain
        out: list[pyast.AST] = []
        cur = n
        while True:
            if isinstance(cur, pyast.Call) and _call_func_name(cur) == "nil_var":
                return out
            if isinstance(cur, pyast.Call) and _call_func_name(cur) == "cons_var":
                if len(cur.args) != 2:
                    raise TranspileError("cons_var expects 2 args")
                out.append(cur.args[0])
                cur = cur.args[1]
                continue
            raise TranspileError(f"Unsupported VarList: {pyast.dump(cur)}")
    if isinstance(n, pyast.Call) and isinstance(n.func, pyast.Subscript) and isinstance(n.func.value, pyast.Name) and n.func.value.id == "Vec":
        # sometimes args are Vec[Term](...)
        return list(n.args)

    raise TranspileError(f"Unsupported VarList form: {pyast.dump(n)}")


def _term_to_asp(n: pyast.AST) -> str:
    if isinstance(n, pyast.Call) and _is_attr(n.func, "Term", "Var"):
        if len(n.args) != 1:
            raise TranspileError("Term.Var expects 1 arg")
        return _const_str(n.args[0])

    if isinstance(n, pyast.Call) and _is_attr(n.func, "Term", "Int"):
        if len(n.args) != 1:
            raise TranspileError("Term.Int expects 1 arg")
        v = n.args[0]
        if isinstance(v, pyast.Constant) and isinstance(v.value, int):
            return str(v.value)
        raise TranspileError("Term.Int expected int")

    if isinstance(n, pyast.Call) and _is_attr(n.func, "Term", "Symbol"):
        if len(n.args) != 1:
            raise TranspileError("Term.Symbol expects 1 arg")
        return _const_str(n.args[0])

    if isinstance(n, pyast.Call) and _is_attr(n.func, "Term", "Anon"):
        return "_"

    if isinstance(n, pyast.Call) and _is_attr(n.func, "Term", "BinaryExpr"):
        if len(n.args) != 3:
            raise TranspileError("BinaryExpr expects 3 args")
        op = _const_str(n.args[0])
        l = _term_to_asp(n.args[1])
        r = _term_to_asp(n.args[2])
        return f"({l} {op} {r})"

    raise TranspileError(f"Unsupported Term: {pyast.dump(n)}")


def _extract_pred_atom_info(head: pyast.AST) -> tuple[str, tuple[str, ...]] | None:
    """Extract (pred_name, args_tuple) from Atom.Pred(name, args)."""
    if not isinstance(head, pyast.Call):
        return None
    if not _is_attr(head.func, "Atom", "Pred"):
        return None
    if len(head.args) != 2:
        return None

    pred_name = _const_str(head.args[0])
    args = _parse_varlist(head.args[1])
    args_tuple = tuple(_term_to_asp(t) for t in args)
    return (pred_name, args_tuple)


def _agg_body_to_asp_count(n: pyast.AST) -> str:
    # AggBody.set_comprehension(vars, cubes) or lowered form set_comp_lower(vars, cubes)
    # Also handle set_comp_costly (high-cost version used by cost_conversion rules)
    if isinstance(n, pyast.Call) and (
        _is_attr(n.func, "AggBody", "set_comprehension")
        or _is_attr(n.func, "AggBody", "set_comp_costly")
    ):
        if len(n.args) != 2:
            raise TranspileError("set_comprehension/set_comp_lower/set_comp_costly expects 2 args")
        vars_set, cubes_vec = n.args
        vars_items = _parse_set_call(vars_set)
        cube_nodes = _parse_vec_call(cubes_vec)

        # Each cube should become an aggregate element: Vars : cube-lits
        elems: list[str] = []
        vars_terms = [ _term_to_asp(v) for v in vars_items ]
        tuple_part = ",".join(vars_terms) if vars_terms else ""

        for cube in cube_nodes:
            cube_lits = _formula_to_body_lits(cube)
            # Disallow nested aggregates inside aggregate bodies.
            # If this happens, the right fix is to introduce an auxiliary predicate
            # for the nested subformula (see TODO.md #2) rather than nesting #count.
            for cl in cube_lits:
                if cl.startswith("#count{"):
                    raise TranspileError(
                        "Nested aggregates inside aggregate bodies are not supported; generate an aux predicate (see TODO.md #2)."
                    )
            cond = ", ".join(x for x in cube_lits if x != "#false")
            if cond:
                elems.append(f"{tuple_part} : {cond}" if tuple_part else f": {cond}")
            else:
                elems.append(f"{tuple_part}" if tuple_part else "")

        inner = "; ".join(elems)
        return f"#count{{{inner}}}"

    raise TranspileError(f"Unsupported aggregate body: {pyast.dump(n)}")
