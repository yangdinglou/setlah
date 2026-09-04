"""
Main Transpilation Pipeline
============================

Multi-phase pipeline that converts egg Block expressions to ASP source.
"""

from __future__ import annotations

import ast as pyast
from dataclasses import replace as _dc_replace
from typing import Any

from .ir import IRRule, IRConstraint, TranspileError
from .normalize import (
    _normalize_extracted_egg_str,
    _split_top_level_commas,
    _replace_singleton_vars_in_line,
    _alpha_normalize_var_in_lit,
)
from .aux import _preprocess_aux_calls, _extract_aux_pred_types
from .egg_parsing import _parse_block, _extract_pred_patterns_from_block
from .rendering import _rule_to_asp, _general_lit_to_body_lit
from .constraint import _constraint_to_asp_lines
from .entailment import _eliminate_entailed_general_lits
from .safety import _infer_safety_guards
from .rewrite import (
    _substitute_var_equalities_pyast,
    _extract_equiv_neq_candidate,
    _extract_existence_pattern,
    _is_existence_pattern,
    _maybe_rewrite_equiv_neq_to_count,
)
from .merge import (
    _merge_choice_partition,
    _merge_choice_with_detected_counts,
    _apply_symmetry_breaking,
)


# =============================================================================
# 2. MAIN TRANSPILATION PIPELINE
# =============================================================================


def transpile_block_expr_to_asp(
    block_expr_str: str,
    *,
    entailment_specs: Any = None,
    pred_arg_types: Any = None,
    grounding: bool = False,
    rewriter_aux_rules: list[str] | None = None,
) -> str:
    """Convert a single extracted egg `Block(...)` expression (string form) to ASP source."""
    original_str = block_expr_str
    block_expr_str = _normalize_extracted_egg_str(block_expr_str)

    # Pre-process: extract AuxCall patterns and generate aux rules
    block_expr_str, aux_rules = _preprocess_aux_calls(block_expr_str)

    # Combine local aux rules with rewriter-level aux rules for type inference
    all_aux_rules = list(aux_rules)
    if rewriter_aux_rules:
        all_aux_rules.extend(rewriter_aux_rules)

    try:
        expr = pyast.parse(block_expr_str, mode="eval").body
    except SyntaxError as e:
        raise TranspileError(f"Failed to parse extracted egg expression as Python AST: {e}\n{block_expr_str}") from e

    try:
        rules, constraints = _parse_block(expr)
    except TranspileError as e:
        raise TranspileError(
            f"{e}\n\n--- original extracted ---\n{original_str}\n\n--- normalized ---\n{block_expr_str}"
        ) from e

    # Extract predicate argument patterns from rules and Let-generated rules
    # This info is used to generate correct partition constraints with constants preserved
    block_pred_patterns = _extract_pred_patterns_from_block(rules, constraints)

    # Phase 0: Detect and merge choice rules + partition constraints
    rules, constraints, merged_choice_lines = _merge_choice_partition(rules, constraints)

    lines: list[str] = list(aux_rules) + list(merged_choice_lines)
    convertible_to_count: dict[int, tuple[str, list[str], list[str]]] = {}  # constraint_idx -> (var, shared, cond)

    # Phase 0.5: Substitute V1 = V2 equalities at pyast level (before neq detection)
    for idx, c in enumerate(constraints):
        if c.kind != "integrity" or c.lits is None:
            continue
        new_lits = _substitute_var_equalities_pyast(c.lits)
        if new_lits is not c.lits:
            constraints[idx] = _dc_replace(c, lits=new_lits)

    # Phase 1: Detect all constraints convertible to count aggregates
    for idx, c in enumerate(constraints):
        if c.kind != "integrity" or c.lits is None:
            continue
        glits = c.lits
        if entailment_specs:
            glits = _eliminate_entailed_general_lits(glits, entailment_specs)

        # Check for X1 != X2 pattern
        cand = _extract_equiv_neq_candidate(glits, pred_arg_types=pred_arg_types)
        if cand is not None:
            convertible_to_count[idx] = cand
            continue

        # Check for not pred(_) pattern (existence check)
        lits = [_general_lit_to_body_lit(gl) for gl in glits]
        existence_pattern = _extract_existence_pattern(lits, pred_arg_types=pred_arg_types)
        if existence_pattern is not None:
            convertible_to_count[idx] = existence_pattern
            continue

    # Phase 2: Group constraints by core and identify mergeable groups
    core_to_constraints: dict[tuple[str, ...], list[int]] = {}
    for idx, (var, shared, cond) in convertible_to_count.items():
        core = tuple(sorted(_alpha_normalize_var_in_lit(s, var, "__X__") for s in cond))
        core_to_constraints.setdefault(core, []).append(idx)

    # Identify which cores can be merged (have both existence and uniqueness)
    mergeable_cores: set[tuple[str, ...]] = set()
    for core, constraint_group in core_to_constraints.items():
        if len(constraint_group) >= 2:
            has_existence = False
            has_uniqueness = False
            for idx in constraint_group:
                c = constraints[idx]
                if c.kind == "integrity" and c.lits is not None:
                    glits = c.lits
                    if entailment_specs:
                        glits = _eliminate_entailed_general_lits(glits, entailment_specs)
                    lits = [_general_lit_to_body_lit(gl) for gl in glits]
                    if _is_existence_pattern(lits):
                        has_existence = True
                    else:
                        has_uniqueness = True
            if has_existence and has_uniqueness:
                mergeable_cores.add(core)

    # Track which constraints have been merged (to skip them later)
    merged_constraints: set[int] = set()

    # Phase 2a: Try to merge choice rules with count constraints (after detection)
    choice_count_merged_lines, choice_merged_rules, choice_merged_constraints = _merge_choice_with_detected_counts(
        rules, convertible_to_count, constraints, core_to_constraints, mergeable_cores
    )
    lines.extend(choice_count_merged_lines)
    merged_constraints.update(choice_merged_constraints)

    for idx, r in enumerate(rules):
        if idx not in choice_merged_rules:
            lines.append(_rule_to_asp(r))

    # Phase 3: Generate output
    for idx, c in enumerate(constraints):
        # Skip if already merged
        if idx in merged_constraints:
            continue

        # Check if this constraint is part of a mergeable group
        if idx in convertible_to_count:
            var, shared, cond = convertible_to_count[idx]
            core = tuple(sorted(_alpha_normalize_var_in_lit(s, var, "__X__") for s in cond))

            if core in mergeable_cores:
                # Merge: emit merged form once (from the first constraint in the group)
                constraint_group = core_to_constraints[core]
                if idx == min(constraint_group):
                    cond_str = ", ".join(cond)
                    agg = f"#count{{{var} : {cond_str}}} != 1"
                    output_lits = list(shared) + [agg]
                    # Emit as a well-formed integrity constraint; Phase 4 will add guards
                    lines.append(f":- {', '.join(output_lits)}.")
                    merged_constraints.update(constraint_group)
                continue

            elif grounding:
                # Convert: with --grounding, convert non-mergeable patterns
                glits = c.lits
                if entailment_specs:
                    glits = _eliminate_entailed_general_lits(glits, entailment_specs)
                lits = [_general_lit_to_body_lit(gl) for gl in glits]
                is_existence = _is_existence_pattern(lits)

                cond_str = ", ".join(cond)
                if not is_existence:

                    agg = f"#count{{{var} : {cond_str}}} > 1"
                    output_lits = list(shared) + [agg]
                    # Emit as a well-formed integrity constraint; Phase 4 will add guards
                    lines.append(f":- {', '.join(output_lits)}.")
                    continue

        # Default: render as-is
        lines.extend(
            _constraint_to_asp_lines(
                c,
                entailment_specs=entailment_specs,
                pred_arg_types=pred_arg_types,
                pred_patterns=block_pred_patterns,
            )
        )

    # Phase 4: Apply safety guards and symmetry-breaking optimization
    # First pass: collect aux predicate type info from aux rules (local + rewriter-level)
    aux_pred_arg_types = _extract_aux_pred_types(all_aux_rules, pred_arg_types)
    # Merge with existing pred_arg_types
    merged_pred_arg_types = dict(pred_arg_types) if pred_arg_types else {}
    merged_pred_arg_types.update(aux_pred_arg_types)

    final_lines: list[str] = []
    for line in lines:
        line = line.strip()  # Remove any leading/trailing whitespace
        if not line:
            continue

        # Check if it's already a well-formed constraint or rule
        if line.startswith(":- "):
            # Extract body literals using top-level comma split (handles aggregates)
            body = line[3:].rstrip(".")
            body_lits = [lit.strip() for lit in _split_top_level_commas(body) if lit.strip()]

            # Apply symmetry-breaking: not X1 = X2 → X1 < X2 (when symmetric uniqueness detected)
            body_lits = _apply_symmetry_breaking(body_lits, core_to_constraints, convertible_to_count, constraints)

            # Add safety guards (use merged types including aux predicates)
            safety_guards = _infer_safety_guards(body_lits, pred_arg_types=merged_pred_arg_types)
            if safety_guards:
                all_lits = safety_guards + body_lits
                final_lines.append(f":- {', '.join(all_lits)}.")
            else:
                final_lines.append(f":- {', '.join(body_lits)}.")
        elif ":-" in line:
            # It's a rule (head :- body). Apply safety guards to body if needed.
            head, _, body_raw = line.partition(":-")
            head = head.strip()
            body_raw = body_raw.rstrip(".").strip()
            body_lits = [lit.strip() for lit in _split_top_level_commas(body_raw) if lit.strip()]
            safety_guards = _infer_safety_guards(
                body_lits, pred_arg_types=merged_pred_arg_types, head_lits=[head]
            )
            if safety_guards:
                all_lits = safety_guards + body_lits
                final_lines.append(f"{head} :- {', '.join(all_lits)}.")
            else:
                final_lines.append(line)
        elif line.startswith("{") and line.endswith("}."):
            # It's a choice rule with no body, keep as-is
            final_lines.append(line)
        else:
            # Fact (no ":-") — keep it instead of turning it into a constraint
            final_lines.append(line if line.endswith(".") else f"{line}.")

    # Phase 5: Replace singleton variables with _ across head+body
    final_lines = [_replace_singleton_vars_in_line(line) for line in final_lines]

    return "\n".join(final_lines)
