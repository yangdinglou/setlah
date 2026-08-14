"""
Egg Parsing
===========

Parse egg expressions to IR: block, rules, constraints, Let expressions.
"""

from __future__ import annotations

import ast as pyast
import re
from typing import Any

from .ir import IRRule, IRConstraint, TranspileError
from .pyast_utils import (
    _is_name, _is_attr, _call_func_name,
    _const_str, _const_bool,
    _parse_vec_call, _parse_set_call, _unroll_conslist,
)
from .rendering import (
    _formula_to_body_lits, _term_to_asp, _parse_varlist,
    _extract_pred_atom_info,
)
from .normalize import _split_top_level_commas


# =============================================================================
# 7. PARSING: BLOCK, RULES, CONSTRAINTS
# =============================================================================


def _parse_block(n: pyast.AST) -> tuple[list[IRRule], list[IRConstraint]]:
    if not isinstance(n, pyast.Call):
        raise TranspileError(f"Expected Block(...) call, got: {pyast.dump(n)}")

    # Block(rules=..., constraints=...) OR Block(rules, constraints)
    func = n.func
    if not (_is_name(func, "Block") or (isinstance(func, pyast.Name) and func.id.endswith("Block"))):
        # Sometimes repr can be schema-qualified; still usually Name('Block')
        if not _is_name(func, "Block"):
            raise TranspileError(f"Expected Block(...) call, got func={pyast.dump(func)}")

    rules_node: pyast.AST | None = None
    constraints_node: pyast.AST | None = None

    if n.keywords:
        for kw in n.keywords:
            if kw.arg == "rules":
                rules_node = kw.value
            elif kw.arg == "constraints":
                constraints_node = kw.value
    else:
        if len(n.args) != 2:
            raise TranspileError("Block(...) expected 2 positional args")
        rules_node, constraints_node = n.args

    if rules_node is None or constraints_node is None:
        raise TranspileError("Block missing rules/constraints")

    rules = _parse_rules_set(rules_node)
    constraints = _parse_constraints_list(constraints_node)
    return rules, constraints


def _parse_rules_set(n: pyast.AST) -> list[IRRule]:
    # Use _parse_set_call which already handles BinOp | for set unions
    rule_nodes = _parse_set_call(n)
    rules: list[IRRule] = []
    for rn in rule_nodes:
        rules.append(_parse_rule(rn))
    return rules


def _parse_rule(n: pyast.AST) -> IRRule:
    if not isinstance(n, pyast.Call) or not _is_name(n.func, "Rule"):
        raise TranspileError(f"Expected Rule(...) call, got: {pyast.dump(n)}")

    head = None
    body = None
    is_choice = None

    if n.keywords:
        for kw in n.keywords:
            if kw.arg == "head":
                head = kw.value
            elif kw.arg == "body":
                body = kw.value
            elif kw.arg == "is_choice":
                is_choice = kw.value
    else:
        if len(n.args) != 3:
            raise TranspileError("Rule(...) expected 3 positional args")
        head, body, is_choice = n.args

    if head is None or body is None or is_choice is None:
        raise TranspileError("Rule missing head/body/is_choice")

    body_items = _parse_set_call(body)
    return IRRule(head=head, body=list(body_items), is_choice=_const_bool(is_choice))


def _parse_constraints_list(n: pyast.AST) -> list[IRConstraint]:
    items = _unroll_conslist(n)
    return [_parse_constraint(ci) for ci in items]


def _parse_let_exprs_to_rules(lets_node: pyast.AST) -> list[str]:
    """Parse Vec[LetExpr](...) and generate ASP rules for each Let expression.

    Let {ClKey}(I) = { (t, I) | (I, L1, L2) in {Cl}, \\true }

    Generates:
        clKey(t, I) :- cl(I, L1, L2).
    """
    # Parse Vec[LetExpr](expr1, expr2, ...)
    if not isinstance(lets_node, pyast.Call):
        raise TranspileError(f"Expected Vec[LetExpr](...), got: {pyast.dump(lets_node)}")

    # Check it's a Vec[LetExpr] call
    fn = lets_node.func
    if not (isinstance(fn, pyast.Subscript) and isinstance(fn.value, pyast.Name) and fn.value.id == "Vec"):
        raise TranspileError(f"Expected Vec[LetExpr](...), got: {pyast.dump(lets_node)}")

    rules: list[str] = []
    for let_expr in lets_node.args:
        rule = _parse_single_let_expr(let_expr)
        if rule:
            rules.append(rule)

    return rules


def _parse_single_let_expr(n: pyast.AST) -> str | None:
    """Parse LetExpr(SetVar, SetComprehension) and generate an ASP rule.

    LetExpr(
        SetExpr.SetVar("ClKey", cons_var(Term.Var("I"), nil_var())),
        SetExpr.Set_Comprehension(
            cons_var(Term.Symbol("t"), cons_var(Term.Var("I"), nil_var())),
            Vec[String]("I", "L1", "L2"),
            SetExpr.SetVar("Cl", nil_var()),
            Formula.Bool(True)
        )
    )

    Generates: clKey(t, I) :- cl(I, L1, L2).
    """
    if not isinstance(n, pyast.Call) or not _is_name(n.func, "LetExpr"):
        raise TranspileError(f"Expected LetExpr(...), got: {pyast.dump(n)}")

    if len(n.args) != 2:
        raise TranspileError(f"LetExpr expects 2 args, got {len(n.args)}")

    set_var_node, set_expr_node = n.args

    # Parse SetExpr.SetVar("Name", params)
    if not (isinstance(set_var_node, pyast.Call) and _is_attr(set_var_node.func, "SetExpr", "SetVar")):
        raise TranspileError(f"Expected SetExpr.SetVar(...), got: {pyast.dump(set_var_node)}")

    if len(set_var_node.args) < 1:
        raise TranspileError("SetVar expects at least 1 arg (name)")

    set_var_name = _const_str(set_var_node.args[0])
    head_pred = set_var_name.lower()  # ClKey -> clkey

    # Parse SetExpr.Set_Comprehension(term, dom_vars, dom_set, condition)
    if not (isinstance(set_expr_node, pyast.Call) and _is_attr(set_expr_node.func, "SetExpr", "Set_Comprehension")):
        raise TranspileError(f"Expected SetExpr.Set_Comprehension(...), got: {pyast.dump(set_expr_node)}")

    if len(set_expr_node.args) != 4:
        raise TranspileError(f"Set_Comprehension expects 4 args, got {len(set_expr_node.args)}")

    term_node, dom_vars_node, dom_set_node, condition_node = set_expr_node.args

    # Parse term (output tuple)
    term_args = _parse_varlist(term_node)
    head_args = ", ".join(_term_to_asp(t) for t in term_args)

    # Parse domain set (SetExpr.SetVar("Cl", ...))
    if not (isinstance(dom_set_node, pyast.Call) and _is_attr(dom_set_node.func, "SetExpr", "SetVar")):
        raise TranspileError(f"Expected SetExpr.SetVar for domain set, got: {pyast.dump(dom_set_node)}")

    dom_set_name = _const_str(dom_set_node.args[0])
    body_pred = dom_set_name.lower()  # Cl -> cl

    # Parse domain vars (Vec[String]("I", "L1", "L2"))
    dom_var_names = _parse_string_vec(dom_vars_node)
    body_args = ", ".join(dom_var_names)

    # Parse condition
    condition_lits = _formula_to_body_lits(condition_node)

    # Build the rule
    head = f"{head_pred}({head_args})"
    body_parts = [f"{body_pred}({body_args})"]
    # Add condition if not trivially true
    if condition_lits and condition_lits != []:
        body_parts.extend(condition_lits)

    body = ", ".join(body_parts)
    return f"{head} :- {body}."


def _parse_string_vec(n: pyast.AST) -> list[str]:
    """Parse Vec[String]("a", "b", "c") -> ["a", "b", "c"]."""
    if not isinstance(n, pyast.Call):
        raise TranspileError(f"Expected Vec[String](...), got: {pyast.dump(n)}")

    return [_const_str(arg) for arg in n.args]


def _parse_constraint(n: pyast.AST) -> IRConstraint:
    # Constraint.integrity_constraints(vars, formulas)
    if isinstance(n, pyast.Call) and _is_attr(n.func, "Constraint", "integrity_constraints"):
        if len(n.args) != 2:
            raise TranspileError("integrity_constraints expects 2 args")
        vars_set, lits_set = n.args
        vars_items = _parse_set_call(vars_set)
        lits_items = _parse_set_call(lits_set)
        return IRConstraint(kind="integrity", vars=vars_items, lits=lits_items, body=None)

    # Constraint(lets, body)
    if isinstance(n, pyast.Call) and _is_name(n.func, "Constraint"):
        lets = None
        body = None
        if n.keywords:
            for kw in n.keywords:
                if kw.arg == "lets":
                    lets = kw.value
                elif kw.arg == "body":
                    body = kw.value
        else:
            if len(n.args) != 2:
                raise TranspileError("Constraint(...) expected 2 args")
            lets, body = n.args

        if lets is None or body is None:
            raise TranspileError("Constraint missing lets/body")

        # Check if lets is empty or has Let expressions
        is_empty_vec_ctor = (
            isinstance(lets, pyast.Call)
            and isinstance(lets.func, pyast.Subscript)
            and isinstance(lets.func.value, pyast.Name)
            and lets.func.value.id == "Vec"
            and len(lets.args) == 0
        )
        is_empty_vec_method = (
            isinstance(lets, pyast.Call)
            and isinstance(lets.func, pyast.Attribute)
            and lets.func.attr == "empty"
            and isinstance(lets.func.value, pyast.Subscript)
            and isinstance(lets.func.value.value, pyast.Name)
            and lets.func.value.value.id == "Vec"
            and len(lets.args) == 0
        )

        let_rules: list[str] = []
        if not (is_empty_vec_ctor or is_empty_vec_method):
            # Try to parse Let expressions
            let_rules = _parse_let_exprs_to_rules(lets)

        return IRConstraint(kind="raw", vars=None, lits=None, body=body, let_rules=let_rules if let_rules else None)

    raise TranspileError(f"Unsupported constraint node: {pyast.dump(n)}")


def _extract_pred_patterns_from_block(
    rules: list[IRRule],
    constraints: list[IRConstraint],
) -> dict[str, list[str]]:
    """Extract predicate argument patterns from rules and Let-generated rules.

    Returns a dict mapping predicate name to list of argument strings.
    E.g., for "clkey(t, I) :- ..." returns {"clkey": ["t", "I"]}

    This preserves constants in their positions, allowing correct partition constraint generation.
    """
    patterns: dict[str, list[str]] = {}

    # Extract from rules
    for r in rules:
        pred_info = _extract_pred_atom_info(r.head)
        if pred_info:
            name, args_tuple = pred_info
            patterns[name] = list(args_tuple)

    # Extract from Let-generated rules in constraints
    for c in constraints:
        if c.let_rules:
            for rule_str in c.let_rules:
                # Parse rule like "clkey(t, I) :- cl(I, L1, L2)."
                info = _extract_pred_pattern_from_rule_str(rule_str)
                if info:
                    name, args = info
                    patterns[name] = args

    return patterns


def _extract_pred_pattern_from_rule_str(rule_str: str) -> tuple[str, list[str]] | None:
    """Extract predicate name and argument pattern from a rule string.

    "clkey(t, I) :- cl(I, L1, L2)." -> ("clkey", ["t", "I"])
    """
    # Match "pred(arg1, arg2, ...)" pattern at the start
    match = re.match(r'^(\w+)\(([^)]*)\)', rule_str.strip())
    if not match:
        return None

    pred_name = match.group(1)
    args_str = match.group(2).strip()

    if not args_str:
        return (pred_name, [])

    # Split arguments
    args = [a.strip() for a in args_str.split(',')]
    return (pred_name, args)
