"""
Aux Predicate Preprocessing
============================

Aux predicate preprocessing: extract AuxCall patterns and generate aux rules.
"""

from __future__ import annotations

import ast as pyast
import re
from typing import Any

from .ir import TranspileError
from .pyast_utils import _is_attr, _const_str, _parse_set_call
from .rendering import _literal_to_body_lit
from .normalize import _extract_balanced_call, _split_top_level_commas


# =============================================================================
# 2b. AUX PREDICATE PREPROCESSING
# =============================================================================

# Counter for generating unique aux predicate names (module-level)
_aux_counter = 0


def _preprocess_aux_calls(block_expr_str: str) -> tuple[str, list[str]]:
    """Pre-process AuxCall patterns in the block expression.

    GeneralLit.AuxCall(body_lits, qvars, free_vars) patterns are:
    1. Extracted and converted to aux predicate rules
    2. Replaced with Literal(Atom.Pred("__aux_N", free_vars_list), True)

    Returns:
        (modified_expr_str, list_of_aux_rules)
    """
    global _aux_counter

    aux_rules: list[str] = []
    result = block_expr_str

    # Find all Literal.AuxCall(...) patterns
    # Pattern: Literal.AuxCall(body_lits_set, qvars_set, free_vars_set)
    auxcall_pattern = r'GeneralLit\.AuxCall\('

    while True:
        match = re.search(auxcall_pattern, result)
        if not match:
            break

        start = match.start()
        # Extract the full AuxCall(...) expression
        call_str = _extract_balanced_call(result, start + len("GeneralLit."))
        call_full = "GeneralLit." + call_str

        # Parse the AuxCall arguments
        try:
            aux_info = _parse_aux_call(call_full)
            if aux_info is None:
                # Can't parse, skip this match
                break

            body_lits, qvars, free_vars = aux_info

            # Generate aux predicate name
            aux_name = f"__aux_{_aux_counter}"
            _aux_counter += 1

            # Generate aux rule: aux_name(free_vars) :- body_lits
            aux_rule = _generate_aux_rule(aux_name, body_lits, free_vars)
            aux_rules.append(aux_rule)

            # Generate replacement: Formula.Lit(GeneralLit.from_literal(GeneralLit.AuxCall(Atom.Pred("aux_name", free_vars_list), True)))
            replacement = _generate_aux_call_replacement(aux_name, free_vars)

            # Replace in result
            end = start + len(call_full)
            result = result[:start] + replacement + result[end:]

        except Exception as e:
            # If parsing fails, skip this AuxCall (leave as is for error reporting later)
            break

    return result, aux_rules


def _parse_aux_call(call_str: str) -> tuple[list[str], list[str], list[str]] | None:
    """Parse GeneralLit.AuxCall(body_lits, qvars, free_vars).

    Returns (body_lits_as_asp, qvars, free_vars) or None if can't parse.
    """
    try:
        expr = pyast.parse(call_str, mode="eval").body
    except SyntaxError:
        return None

    if not isinstance(expr, pyast.Call) or not _is_attr(expr.func, "GeneralLit", "AuxCall"):
        return None

    if len(expr.args) != 3:
        return None

    body_lits_node, qvars_node, free_vars_node = expr.args

    # Parse body_lits (Set[Literal])
    body_lit_nodes = _parse_set_call(body_lits_node)
    body_lits = [_literal_to_body_lit(lit) for lit in body_lit_nodes]

    # Parse free_vars (Set[Term])
    free_var_nodes = _parse_set_call(free_vars_node)
    free_vars = [_extract_var_name(v) for v in free_var_nodes]
    free_vars = [v for v in free_vars if v is not None]  # Filter out failures

    return body_lits, [], free_vars


def _extract_var_name(n: pyast.AST) -> str | None:
    """Extract variable name from Term.Var("X") node."""
    if isinstance(n, pyast.Call) and _is_attr(n.func, "Term", "Var"):
        if len(n.args) == 1:
            return _const_str(n.args[0])
    return None


def _generate_aux_rule(aux_name: str, body_lits: list[str], free_vars: list[str]) -> str:
    """Generate aux predicate rule: aux_name(free_vars) :- body_lits."""
    if free_vars:
        head = f"{aux_name}({', '.join(free_vars)})"
    else:
        head = aux_name

    if body_lits:
        body = ", ".join(body_lits)
        return f"{head} :- {body}."
    else:
        return f"{head}."


def _generate_aux_call_replacement(aux_name: str, free_vars: list[str]) -> str:
    """Generate replacement expression for AuxCall.

    Returns: Literal(Atom.Pred("aux_name", varlist), True)
    (This is a Literal so it can participate in further rewrites like aggregates)
    """
    if free_vars:
        # Build varlist: cons_var(Term.Var("X"), cons_var(Term.Var("Y"), nil_var()))
        varlist = "nil_var()"
        for v in reversed(free_vars):
            varlist = f'cons_var(Term.Var("{v}"), {varlist})'
    else:
        varlist = "nil_var()"

    return f'Literal(Atom.Pred("{aux_name}", {varlist}), True)'


def _extract_aux_pred_types(lines: list[str], pred_arg_types: Any) -> dict[str, list[str]]:
    """Extract type information for aux predicates from their defining rules.

    For aux rules like: __aux_0(A, B) :- greek(R, C, A), latin(R, C, B).
    We infer: __aux_0 has arg types [type_of_A, type_of_B] based on greek and latin predicates.
    """
    if not isinstance(pred_arg_types, dict):
        return {}

    aux_types: dict[str, list[str]] = {}

    for line in lines:
        line = line.strip()
        # Look for aux rules: __aux_N(...) :- ...
        match = re.match(r'(__aux_\d+)\s*\(([^)]*)\)\s*:-\s*(.*)\.', line)
        if not match:
            continue

        aux_name = match.group(1)
        args_str = match.group(2)
        body_str = match.group(3)

        # Parse aux predicate arguments (the head args)
        head_args = [a.strip() for a in args_str.split(',') if a.strip()]

        # Build mapping from variable name to type by analyzing body predicates
        var_types: dict[str, str] = {}

        # Split body into literals
        body_lits = _split_top_level_commas(body_str)
        for body_lit in body_lits:
            body_lit = body_lit.strip()
            # Strip negation to handle negated predicates (e.g. "not bb_date(BB1, N', D')")
            bare_lit = body_lit[4:].strip() if body_lit.startswith("not ") else body_lit
            # Parse predicate: pred_name(args...)
            pred_match = re.match(r'([a-z_][a-z0-9_]*)\s*\((.*)\)', bare_lit, re.IGNORECASE)
            if not pred_match:
                continue

            pred_name = pred_match.group(1)
            pred_args_str = pred_match.group(2)
            pred_args = [a.strip() for a in pred_args_str.split(',') if a.strip()]

            # Get type info for this predicate
            types = pred_arg_types.get(pred_name)
            if not types or not isinstance(types, (list, tuple)):
                continue

            # Map each arg variable to its type (including primed vars like N')
            for pos, arg in enumerate(pred_args):
                if pos >= len(types):
                    break
                if re.match(r"^[A-Z][A-Za-z0-9_']*$", arg):
                    tname = types[pos]
                    if isinstance(tname, str) and tname not in ("UNKNOWN", "CONST"):
                        var_types.setdefault(arg, tname)

        # Propagate types through comparisons: if X != Y (or X = Y) and one side's
        # type is known, infer the other side's type (e.g. N' != N → N gets type of N')
        changed = True
        while changed:
            changed = False
            for body_lit in body_lits:
                bare_lit = body_lit.strip()
                if bare_lit.startswith("not "):
                    bare_lit = bare_lit[4:].strip()
                cmp_match = re.match(
                    r"^([A-Z][A-Za-z0-9_']*)\s*(?:!=|\\=|==|=)\s*([A-Z][A-Za-z0-9_']*)$",
                    bare_lit,
                )
                if cmp_match:
                    v1, v2 = cmp_match.group(1), cmp_match.group(2)
                    if v1 in var_types and v2 not in var_types:
                        var_types[v2] = var_types[v1]
                        changed = True
                    elif v2 in var_types and v1 not in var_types:
                        var_types[v1] = var_types[v2]
                        changed = True

        # Now build the type list for aux predicate based on head args
        aux_arg_types: list[str] = []
        for head_arg in head_args:
            tname = var_types.get(head_arg, "UNKNOWN")
            aux_arg_types.append(tname)

        aux_types[aux_name] = aux_arg_types

    return aux_types
