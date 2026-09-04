"""
Safety Guards
=============

Safety guard inference (Phase 4) and singleton variable replacement (Phase 5).
"""

from __future__ import annotations

import ast as pyast
import re
from typing import Any

from .ir import TranspileError
from .pyast_utils import _is_attr, _const_str
from .rendering import _term_to_asp, _parse_varlist
from .normalize import _split_top_level_commas
from .entailment import _pos_pred_literal, _term_var_name


# =============================================================================
# 11. SAFETY GUARD INFERENCE
# =============================================================================


def _infer_safety_guards(
    body_lits: list[str], *, pred_arg_types: Any, head_lits: list[str] | None = None
) -> list[str]:
    """Infer `dom_<Type>(V)` guards for variables that don't appear in positive literals.

    A variable is unsafe if it appears in the constraint but never in a positive
    (non-negated, non-aggregate) predicate literal. Variables inside aggregates are
    local to the aggregate and don't make external occurrences safe.

    `head_lits` carries the head of a rule. A head variable must be bound by the
    body too, and one that is not is just as unsafe as an unbound body variable --
    Clingo rejects the program either way. This matters for the auxiliary rules
    generated from a disjunctive body: the auxiliary predicate's arguments are the
    free variables of the whole disjunction, so a variable occurring in one
    disjunct heads every rule, including the rules of the disjuncts that do not
    mention it. Its domain is read from the auxiliary predicate's own inferred
    signature, i.e. from the sibling rule where it is bound.
    See `docs/known-issues.md` (B3).
    """
    if not isinstance(pred_arg_types, dict):
        return []

    head_lits = head_lits or []

    # Collect all variables in the constraint (excluding counted vars in aggregates)
    all_vars: set[str] = set()
    for lit in body_lits:
        lit_stripped = lit.strip()
        # For aggregates: extract vars but exclude the counted variable
        if lit_stripped.startswith("#count{"):
            close_brace = lit_stripped.find("}")
            if close_brace != -1:
                inner = lit_stripped[len("#count{"):close_brace]
                # Parse: X : pred(...) or just pred(...)
                if ":" in inner:
                    counted_part, cond_part = inner.split(":", 1)
                    counted_vars = {v.strip() for v in counted_part.split(",") if v.strip()}
                    # Extract vars from condition (but exclude counted vars)
                    cond_vars = _extract_vars_from_lit(cond_part)
                    all_vars.update(cond_vars - counted_vars)
                # Extract vars from comparison part (after })
                after_agg = lit_stripped[close_brace+1:]
                all_vars.update(_extract_vars_from_lit(after_agg))
        else:
            all_vars.update(_extract_vars_from_lit(lit))

    # Collect variables that appear in positive predicate literals (non-aggregate)
    safe_vars: set[str] = set()
    # Also track variable types from all predicates (even negated ones)
    var_types: dict[str, str] = {}

    for lit in body_lits:
        lit = lit.strip()
        is_aggregate = lit.startswith("#count{")

        if is_aggregate:
            # Extract type info from condition predicates (may have multiple predicates)
            close_brace = lit.find("}")
            if close_brace != -1:
                inner = lit[len("#count{"):close_brace]
                if ":" in inner:
                    cond_part = inner.split(":", 1)[1].strip()
                    # Split condition into individual predicates and extract type info from each
                    cond_lits = _split_top_level_commas(cond_part)
                    for cond_lit in cond_lits:
                        cond_lit = cond_lit.strip()
                        pred_info = _extract_pred_info_from_lit(cond_lit)
                        if pred_info is not None:
                            pred_name, arg_vars = pred_info
                            types = pred_arg_types.get(pred_name)
                            if types and isinstance(types, (list, tuple)):
                                for pos, var in enumerate(arg_vars):
                                    if pos < len(types) and var and var not in ("_",):
                                        tname = types[pos]
                                        if isinstance(tname, str) and tname not in ("UNKNOWN", "CONST"):
                                            var_types.setdefault(var, tname)
            continue

        is_negated = lit.startswith("not ")
        if is_negated:
            lit = lit[4:].strip()

        if not is_negated:
            # Only real predicate literals (pred(args)) make variables safe.
            # Comparisons like X != Y, X < Y, not X = Y do NOT ground variables.
            pred_info_check = _extract_pred_info_from_lit(lit)
            if pred_info_check is not None:
                safe_vars.update(_extract_vars_from_lit(lit))

        # Try to infer types from predicate signatures
        pred_info = _extract_pred_info_from_lit(lit)
        if pred_info is not None:
            pred_name, arg_vars = pred_info
            types = pred_arg_types.get(pred_name)
            if types and isinstance(types, (list, tuple)):
                for pos, var in enumerate(arg_vars):
                    if pos < len(types) and var and var not in ("_",):
                        tname = types[pos]
                        if isinstance(tname, str) and tname not in ("UNKNOWN", "CONST"):
                            var_types.setdefault(var, tname)

    # Head variables need binding by the body, and never provide it; take their
    # types from the head predicate's signature.
    for lit in head_lits:
        all_vars.update(_extract_vars_from_lit(lit))
        pred_info = _extract_pred_info_from_lit(lit.strip())
        if pred_info is not None:
            pred_name, arg_vars = pred_info
            types = pred_arg_types.get(pred_name)
            if types and isinstance(types, (list, tuple)):
                for pos, var in enumerate(arg_vars):
                    if pos < len(types) and var and var not in ("_",):
                        tname = types[pos]
                        if isinstance(tname, str) and tname not in ("UNKNOWN", "CONST"):
                            var_types.setdefault(var, tname)

    # Propagate types through comparisons: if X != Y (or X = Y) and one side's
    # type is known, infer the other side's type (e.g. N' != N → N gets type of N')
    changed = True
    while changed:
        changed = False
        for lit in body_lits:
            bare = lit.strip()
            if bare.startswith("not "):
                bare = bare[4:].strip()
            cmp_match = re.match(
                r"^([A-Z][A-Za-z0-9_']*)\s*(?:!=|\\=|==|=)\s*([A-Z][A-Za-z0-9_']*)$",
                bare,
            )
            if cmp_match:
                v1, v2 = cmp_match.group(1), cmp_match.group(2)
                if v1 in var_types and v2 not in var_types:
                    var_types[v2] = var_types[v1]
                    changed = True
                elif v2 in var_types and v1 not in var_types:
                    var_types[v1] = var_types[v2]
                    changed = True

            # Arithmetic comparisons can connect more than two variables, for
            # example (R1 - R2) != (C1 - C2). If every known variable in the
            # comparison has the same domain, the checker has established one
            # numeric domain for the expression and we can type the rest.
            if _extract_pred_info_from_lit(bare) is None and re.search(r"(?:!=|==|=|<=|>=|<|>)", bare):
                expr_vars = _extract_vars_from_lit(bare)
                known_types = {var_types[var] for var in expr_vars if var in var_types}
                if len(known_types) == 1:
                    inferred_type = next(iter(known_types))
                    for var in expr_vars:
                        if var not in var_types:
                            var_types[var] = inferred_type
                            changed = True

    # Find unsafe variables
    unsafe_vars = all_vars - safe_vars

    # Generate guards for unsafe variables
    guards: list[str] = []
    for var in sorted(unsafe_vars):
        if var == "_":  # Skip anonymous variables
            continue
        tname = var_types.get(var)
        if tname:
            guards.append(f"dom_{tname}({var})")

    return guards


def _extract_vars_from_lit(lit: str) -> set[str]:
    """Extract all variable names (including primed, e.g. N') from a literal string."""
    vars: set[str] = set()
    # Match uppercase-starting identifiers that may include trailing primes (e.g. N', D'').
    # Negative lookbehind prevents matching mid-token (e.g. inside predicate names).
    for match in re.finditer(r"(?<![A-Za-z0-9_'])([A-Z][A-Za-z0-9_']*)", lit):
        var = match.group(1)
        if var not in ("TRUE", "FALSE"):
            vars.add(var)
    return vars


def _extract_pred_info_from_lit(lit: str) -> tuple[str, list[str]] | None:
    """Extract predicate name and argument variables from a literal string.

    Returns (pred_name, [arg_vars]) where arg_vars are variable names or None for non-vars.
    """
    # Match: pred_name(arg1, arg2, ...)
    match = re.match(r'([a-z_][a-z0-9_]*)\s*\((.*)\)', lit, re.IGNORECASE)
    if not match:
        return None

    pred_name = match.group(1)
    args_str = match.group(2)

    # Split arguments (simple comma split, doesn't handle nested parens)
    arg_strs = [a.strip() for a in args_str.split(',') if a.strip()]
    arg_vars: list[str] = []
    for arg in arg_strs:
        # Check if it's a variable (starts with uppercase, may include trailing primes)
        if re.match(r"^[A-Z][A-Za-z0-9_']*$", arg):
            arg_vars.append(arg)
        else:
            arg_vars.append("")  # Not a simple variable

    return (pred_name, arg_vars)


def _infer_domain_guards_for_group(
    glits: list[pyast.AST],
    group_idxs: list[int],
    *,
    counted_var: str,
    pred_arg_types: Any,
) -> list[str]:
    """Infer `dom_<Type>(V)` guards for variables in the group (excluding counted_var)."""
    if not isinstance(pred_arg_types, dict):
        return []

    var_to_dom: dict[str, str] = {}
    for i in group_idxs:
        pred = _pos_pred_literal(glits[i])
        if pred is None:
            continue
        pred_name, args = pred
        types = pred_arg_types.get(pred_name)
        if not types or not isinstance(types, (list, tuple)):
            continue

        for pos, term in enumerate(args):
            vname = _term_var_name(term)
            if vname is None or vname == counted_var:
                continue
            if pos >= len(types):
                continue
            tname = types[pos]
            if not isinstance(tname, str) or tname in ("UNKNOWN", "CONST"):
                continue
            dom_pred = f"dom_{tname}"
            var_to_dom.setdefault(vname, dom_pred)

    # Stable order by variable name for deterministic output.
    guards = [f"{var_to_dom[v]}({v})" for v in sorted(var_to_dom.keys())]
    return guards
