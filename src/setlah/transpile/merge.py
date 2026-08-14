"""
Merge
=====

Choice+partition merge (Phase 0) and choice+count merge (Phase 2).
"""

from __future__ import annotations

import ast as pyast
import re
from typing import Any

from .ir import IRRule, IRConstraint, TranspileError
from .pyast_utils import _is_attr, _const_str
from .rendering import _formula_to_body_lits, _term_to_asp, _extract_pred_atom_info, _parse_varlist
from .constraint import _extract_partition_info, _set_name_to_pred
from .egg_parsing import _extract_pred_pattern_from_rule_str
from .normalize import _split_top_level_commas
from .entailment import _eliminate_entailed_general_lits
from .rendering import _general_lit_to_body_lit
from .rewrite import (
    _alpha_normalize_var_in_lit,
    _extract_count_constraint_pattern,
)


def _substitute_vars_in_lit(lit: str, var_map: dict[str, str]) -> str:
    """Substitute variables in a literal according to var_map.

    Example: _substitute_vars_in_lit("dom_Index(I)", {"I": "B"}) -> "dom_Index(B)"
    """
    def replacer(match: re.Match) -> str:
        var = match.group(0)
        return var_map.get(var, var)

    # Replace whole-word variable occurrences (uppercase identifiers)
    return re.sub(r'\b([A-Z][A-Za-z0-9_]*)\b', replacer, lit)


# =============================================================================
# 4. CHOICE + PARTITION MERGE OPTIMIZATION
# =============================================================================


def _merge_choice_partition(
    rules: list["IRRule"],
    constraints: list["IRConstraint"],
) -> tuple[list["IRRule"], list["IRConstraint"], list[str]]:
    """Detect choice rules + partition constraints that can be merged into bounded choice rules.

    Pattern:
        {a(X)} :- f(X).
        {b(X)} :- f(X).
        {c(X)} :- f(X).
        :- f(X), #count{1,a:a(X); 1,b:b(X); 1,c:c(X)} != 1.

    Merged into:
        1{a(X); b(X); c(X)}1 :- f(X).

    With Let expressions:
        {c(t,I)} :- cl(I,L1,L2).
        {ac(t,I)} :- cl(I,L1,L2).
        {dc(t,I)} :- cl(I,L1,L2).
        Let {ClKey}(I) = {(t,I) | (I,L1,L2) in {Cl}, true} in
            partition(Set_clKey, {{Set_c, Set_ac, Set_dc}})

    The Let generates: clkey(t,I) :- cl(I,_,_).
    Merged into: 1{c(t,I); ac(t,I); dc(t,I)}1 :- cl(I,_,_).

    Returns: (remaining_rules, remaining_constraints, merged_lines)
    """
    merged_lines: list[str] = []

    # Build a map from Let-generated predicates to their body patterns
    # This allows matching partition targets defined via Let expressions
    let_pred_bodies: dict[str, str] = {}  # pred_name -> body_key (normalized)
    for c in constraints:
        if c.let_rules:
            for rule_str in c.let_rules:
                info = _extract_pred_pattern_from_rule_str(rule_str)
                if info:
                    pred_name, _ = info
                    # Extract body from rule string
                    if " :- " in rule_str:
                        body_part = rule_str.split(" :- ", 1)[1].rstrip(".")
                        # Normalize body for matching (use top-level comma split)
                        body_lits = [lit.strip() for lit in _split_top_level_commas(body_part)]
                        let_pred_bodies[pred_name] = str(tuple(sorted(body_lits)))

    # Group choice rules by normalized body
    # body_key -> list of (rule_idx, head_pred, head_args, body_str)
    choice_groups: dict[str, list[tuple[int, str, str, str]]] = {}

    for idx, r in enumerate(rules):
        if not r.is_choice:
            continue
        # Extract head predicate info
        head_info = _extract_pred_atom_info(r.head)
        if head_info is None:
            continue
        pred_name, args_tuple = head_info
        args_str = ", ".join(args_tuple)

        # Normalize body for grouping
        body_lits = []
        for b in r.body:
            body_lits.extend(_formula_to_body_lits(b))
        body_key = tuple(sorted(body_lits))
        body_str = ", ".join(body_lits)

        choice_groups.setdefault(str(body_key), []).append((idx, pred_name, args_str, body_str))

    # Find partition constraints
    partition_constraints: dict[int, tuple[str, list[str]]] = {}  # idx -> (target_pred, part_preds)
    for idx, c in enumerate(constraints):
        if c.kind != "raw" or c.body is None:
            continue
        partition_info = _extract_partition_info(c.body)
        if partition_info is not None:
            partition_constraints[idx] = partition_info

    # Try to match choice groups with partition constraints
    merged_rule_indices: set[int] = set()
    merged_constraint_indices: set[int] = set()

    for body_key, choice_list in choice_groups.items():
        if len(choice_list) < 2:
            continue

        # Get head predicates and check they share the same args pattern
        head_preds = set()
        common_args: str | None = None
        body_str: str | None = None
        body_lits_list: list[str] = []
        valid_group = True

        for rule_idx, pred_name, args_str, b_str in choice_list:
            head_preds.add(pred_name)
            if common_args is None:
                common_args = args_str
                body_str = b_str
                body_lits_list = [lit.strip() for lit in b_str.split(",")]
            elif common_args != args_str:
                valid_group = False
                break

        if not valid_group or common_args is None or body_str is None:
            continue

        # Extract the first body predicate name for matching with partition target
        first_body_pred = None
        if body_lits_list:
            first_lit = body_lits_list[0]
            paren_idx = first_lit.find("(")
            if paren_idx > 0:
                first_body_pred = first_lit[:paren_idx]

        # Check if there's a matching partition constraint
        for c_idx, (target_pred, part_preds) in partition_constraints.items():
            if c_idx in merged_constraint_indices:
                continue

            # Check if partition target matches:
            # 1. Direct match: target_pred == first_body_pred (e.g., Set_person with body person(X))
            # 2. Let-based match: target_pred is defined by Let with same body as choice rules
            target_matches = False
            if first_body_pred is not None and target_pred == first_body_pred:
                target_matches = True
            elif target_pred in let_pred_bodies:
                # Check if Let-generated predicate has same body as choice rules
                if let_pred_bodies[target_pred] == body_key:
                    target_matches = True

            if not target_matches:
                continue

            # Check if partition parts match head predicates exactly
            if set(part_preds) == head_preds:
                # Match found! Create merged bounded choice rule
                # 1{c(t,I); ac(t,I); dc(t,I)}1 :- cl(I, L1, L2).
                choice_elements = "; ".join(f"{p}({common_args})" for p in sorted(part_preds))
                merged_line = f"1{{{choice_elements}}}1 :- {body_str}."
                merged_lines.append(merged_line)

                # Mark as merged
                for rule_idx, _, _, _ in choice_list:
                    merged_rule_indices.add(rule_idx)
                merged_constraint_indices.add(c_idx)
                break

    # Filter out merged rules and constraints
    remaining_rules = [r for i, r in enumerate(rules) if i not in merged_rule_indices]
    remaining_constraints = [c for i, c in enumerate(constraints) if i not in merged_constraint_indices]

    return remaining_rules, remaining_constraints, merged_lines


def _merge_choice_with_detected_counts(
    rules: list["IRRule"],
    convertible_to_count: dict[int, tuple[str, list[str], list[str]]],
    constraints: list["IRConstraint"],
    core_to_constraints: dict[tuple[str, ...], list[int]],
    mergeable_cores: set[tuple[str, ...]],
) -> tuple[list[str], set[int], set[int]]:
    """Merge choice rules with detected count-convertible constraints.

    When we have:
        {h(X, Y, Z)} :- shared_body, extra_body
        :- shared_body, #count{Z : h(X, Y, Z)} != 1

    Merge into:
        1{h(X, Y, Z) : extra_body}1 :- shared_body.

    Returns: (merged_lines, merged_rule_indices, merged_constraint_indices)
    """
    merged_lines: list[str] = []
    merged_rules: set[int] = set()
    merged_constraints: set[int] = set()

    # Group choice rules by head predicate
    choice_by_pred: dict[str, list[tuple[int, str, list[str]]]] = {}
    # pred_name -> [(rule_idx, args_str, body_lits)]

    for idx, r in enumerate(rules):
        if not r.is_choice:
            continue
        head_info = _extract_pred_atom_info(r.head)
        if head_info is None:
            continue
        pred_name, args_tuple = head_info
        args_str = ", ".join(args_tuple)

        body_lits = []
        for b in r.body:
            body_lits.extend(_formula_to_body_lits(b))

        choice_by_pred.setdefault(pred_name, []).append((idx, args_str, body_lits))

    # Check each count-convertible constraint for merging with choice rules
    for c_idx, (counted_var, shared_lits, cond_lits) in convertible_to_count.items():
        if c_idx in merged_constraints:
            continue

        # Check if this is a mergeable existence+uniqueness pattern
        core = tuple(sorted(_alpha_normalize_var_in_lit(s, counted_var, "__X__") for s in cond_lits))
        if core not in mergeable_cores:
            continue

        # Extract predicate from condition literals
        if len(cond_lits) != 1:
            continue

        cond_lit = cond_lits[0]
        match = re.match(r'([a-z_][a-z0-9_]*)\s*\((.*)\)', cond_lit, re.IGNORECASE)
        if not match:
            continue

        pred_name = match.group(1)
        args_str = match.group(2).strip()

        # Check if there's a matching choice rule
        if pred_name not in choice_by_pred:
            continue

        for rule_idx, rule_args_str, rule_body_lits in choice_by_pred[pred_name]:
            if rule_idx in merged_rules:
                continue

            # Try to unify: check if we can map constraint variables to rule variables
            cond_args = [a.strip() for a in args_str.split(",")]
            rule_args = [a.strip() for a in rule_args_str.split(",")]

            if len(cond_args) != len(rule_args):
                continue

            # Build variable substitution map: cond_var -> rule_var
            var_map: dict[str, str] = {}
            for cond_arg, rule_arg in zip(cond_args, rule_args):
                if cond_arg in var_map:
                    if var_map[cond_arg] != rule_arg:
                        break  # Inconsistent mapping
                else:
                    var_map[cond_arg] = rule_arg
            else:
                # Mapping succeeded, now check if shared literals match after substitution
                renamed_shared = [_substitute_vars_in_lit(lit, var_map) for lit in shared_lits]

                rule_body_set = set(rule_body_lits)
                renamed_shared_set = set(renamed_shared)

                if not renamed_shared_set.issubset(rule_body_set):
                    continue

                # Extract extra literals (those not in shared)
                extra_lits = [lit for lit in rule_body_lits if lit not in renamed_shared_set]

                # Build merged bounded choice rule using rule's variable names
                head_atom = f"{pred_name}({rule_args_str})"
                if extra_lits:
                    head_part = f"{head_atom} : {', '.join(extra_lits)}"
                else:
                    head_part = head_atom

                bounded_head = f"1{{{head_part}}}1"

                if renamed_shared:
                    merged_line = f"{bounded_head} :- {', '.join(renamed_shared)}."
                else:
                    merged_line = f"{bounded_head}."

                merged_lines.append(merged_line)
                merged_rules.add(rule_idx)

                # Mark all constraints in this core group as merged
                if core in core_to_constraints:
                    for idx in core_to_constraints[core]:
                        merged_constraints.add(idx)

                break

    return (merged_lines, merged_rules, merged_constraints)


def _merge_choice_count(
    rules: list["IRRule"],
    constraints: list["IRConstraint"],
    *,
    pred_arg_types: Any = None,
    entailment_specs: Any = None,
) -> tuple[list["IRRule"], list["IRConstraint"], list[str]]:
    """Merge choice rules with count constraints (without requiring explicit partition).

    Pattern:
        {h(X1, X2, ...)} :- b1(X1), b2(X2), c1(Y1), c2(Y2), ...
        :- b1(X1), b2(X2), #count{Y1, Y2, ... : h(X1, X2, ...)} op val

    Where:
        - b1, b2, ... are the "shared" body literals (appear in both)
        - c1, c2, ... are correlated with the counted variables Y1, Y2, ...

    Merged into:
        {h(X1, X2, ...) : c1(Y1), c2(Y2), ...} op val :- b1(X1), b2(X2).

    Returns: (remaining_rules, remaining_constraints, merged_lines)
    """
    merged_lines: list[str] = []
    merged_rule_indices: set[int] = set()
    merged_constraint_indices: set[int] = set()

    # Group choice rules by head predicate
    choice_by_pred: dict[str, list[tuple[int, IRRule, str, list[str], list[str]]]] = {}
    # pred_name -> [(rule_idx, rule, args_str, shared_lits, extra_lits)]

    for idx, r in enumerate(rules):
        if not r.is_choice:
            continue
        head_info = _extract_pred_atom_info(r.head)
        if head_info is None:
            continue
        pred_name, args_tuple = head_info
        args_str = ", ".join(args_tuple)

        body_lits = []
        for b in r.body:
            body_lits.extend(_formula_to_body_lits(b))

        choice_by_pred.setdefault(pred_name, []).append((idx, r, args_str, body_lits, []))

    # Find count constraints and try to match with choice rules
    for c_idx, c in enumerate(constraints):
        if c.kind != "integrity" or c.lits is None:
            continue

        glits = c.lits
        if entailment_specs:
            glits = _eliminate_entailed_general_lits(glits, entailment_specs)

        lits = [_general_lit_to_body_lit(gl) for gl in glits]

        # Try to extract count aggregate pattern
        count_info = _extract_count_constraint_pattern(lits)
        if count_info is None:
            continue

        counted_vars, cond_pred, cond_args, comp_op, val, shared_lits = count_info

        # Check if this matches a choice rule
        if cond_pred not in choice_by_pred:
            continue

        for rule_idx, rule, rule_args_str, rule_body_lits, _ in choice_by_pred[cond_pred]:
            if rule_idx in merged_rule_indices:
                continue

            # Check if the condition arguments match the rule head arguments
            if ", ".join(cond_args) != rule_args_str:
                continue

            # Check if shared literals match part of the rule body
            rule_body_set = set(rule_body_lits)
            shared_set = set(shared_lits)

            if not shared_set.issubset(rule_body_set):
                continue

            # Extract the "extra" literals (those correlated with counted vars)
            extra_lits = [lit for lit in rule_body_lits if lit not in shared_set]

            # Build merged bounded choice rule with conditions
            # {h(args) : extra_lits} op val :- shared_lits.
            head_atom = f"{cond_pred}({rule_args_str})"
            if extra_lits:
                cond_str = ", ".join(extra_lits)
                head_part = f"{head_atom} : {cond_str}"
            else:
                head_part = head_atom

            # Convert comparison for bounded choice syntax
            bounds = _compute_choice_bounds(comp_op, val)
            if bounds is None:
                continue

            lower, upper = bounds
            bounded_head = f"{lower}{{{head_part}}}{upper}"

            if shared_lits:
                merged_line = f"{bounded_head} :- {', '.join(shared_lits)}."
            else:
                merged_line = f"{bounded_head}."

            merged_lines.append(merged_line)
            merged_rule_indices.add(rule_idx)
            merged_constraint_indices.add(c_idx)
            break

    # Filter out merged rules and constraints
    remaining_rules = [r for i, r in enumerate(rules) if i not in merged_rule_indices]
    remaining_constraints = [c for i, c in enumerate(constraints) if i not in merged_constraint_indices]

    return remaining_rules, remaining_constraints, merged_lines


def _compute_choice_bounds(comp_op: str, val: str) -> tuple[str, str] | None:
    """Convert comparison operator + value to choice bounds (lower, upper).

    Examples:
        != 1 → (1, 1) — for existence+uniqueness merge
        = 1 → (1, 1)
        >= 1 → (1, inf) represented as (1, "")
        <= 1 → (0, 1) represented as ("", 1)
    """
    comp_op = comp_op.strip()
    if comp_op == "==":
        comp_op = "="

    if comp_op == "=":
        return (val, val)
    elif comp_op == "!=" and val == "1":
        # Special case: != 1 for merged existence+uniqueness → = 1
        return ("1", "1")
    elif comp_op == ">=":
        return (val, "")
    elif comp_op == "<=":
        return ("", val)
    elif comp_op == ">":
        # Increment val by 1 (if it's a number)
        try:
            lower = str(int(val) + 1)
            return (lower, "")
        except ValueError:
            return None
    elif comp_op == "<":
        # Decrement val by 1
        try:
            upper = str(int(val) - 1)
            return ("", upper)
        except ValueError:
            return None
    elif comp_op == "!=":
        # Can't express directly in bounded choice (except != 1 handled above)
        return None

    return None


def _apply_symmetry_breaking(
    body_lits: list[str],
    core_to_constraints: dict[tuple[str, ...], list[int]],
    convertible_to_count: dict[int, tuple[str, list[str], list[str]]],
    constraints: list["IRConstraint"],
) -> list[str]:
    """Apply symmetry-breaking optimization: not X1 = X2 → X1 < X2.

    Only applies when the pattern is detected as symmetric uniqueness constraint
    (i.e., it has a count-convertible core with multiple instances).
    """
    # Check if this constraint has the pattern: pred(..., V1, ...), pred(..., V2, ...), not V1 = V2
    # where V1 and V2 are variables in symmetric positions

    # Find all "not X = Y" literals
    ineq_indices = []
    for idx, lit in enumerate(body_lits):
        lit = lit.strip()
        if re.match(r'not\s+\w+\s*=\s*\w+', lit):
            ineq_indices.append(idx)

    if not ineq_indices:
        return body_lits

    # Check if this constraint belongs to a symmetric uniqueness pattern
    # (detected during Phase 1-2 as convertible to count with multiple cores)
    is_symmetric = False
    for core, constraint_idxs in core_to_constraints.items():
        if len(constraint_idxs) > 1:
            # Multiple constraints with same core = symmetric pattern
            is_symmetric = True
            break

    if not is_symmetric:
        return body_lits

    # Replace "not X = Y" with "X < Y"
    result = []
    for idx, lit in enumerate(body_lits):
        if idx in ineq_indices:
            lit = lit.strip()
            match = re.match(r'not\s+(\w+)\s*=\s*(\w+)', lit)
            if match:
                var1, var2 = match.groups()
                # Use lexicographic ordering to ensure deterministic symmetry breaking
                result.append(f"{var1} < {var2}")
            else:
                result.append(lit)
        else:
            result.append(lit)

    return result
