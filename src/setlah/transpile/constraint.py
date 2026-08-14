"""
Constraint Rendering
====================

Constraint rendering: partition, aggregate, and general constraint handling.
"""

from __future__ import annotations

import ast as pyast
import re
from typing import Any

from .ir import IRConstraint, TranspileError
from .pyast_utils import (
    _is_name, _is_attr, _call_func_name,
    _const_str, _const_bool,
    _parse_vec_call, _parse_set_call,
)
from .rendering import (
    _formula_to_body_lits, _term_to_asp, _parse_varlist,
    _general_lit_to_body_lit, _atom_to_asp,
)
from .safety import _infer_safety_guards
from .entailment import _eliminate_entailed_general_lits


# =============================================================================
# 9. PARTITION CONSTRAINT HANDLING
# =============================================================================


def _extract_term_var_name(n: pyast.AST) -> str | None:
    """Extract variable name from Term.Var("X") -> "X"."""
    if not isinstance(n, pyast.Call):
        return None
    if not _is_attr(n.func, "Term", "Var"):
        return None
    if len(n.args) != 1:
        return None
    return _const_str(n.args[0])


def _extract_vec_term_var_names(n: pyast.AST) -> list[str] | None:
    """Extract list of variable names from Vec[Term](Term.Var("A"), Term.Var("B"), ...)."""
    if not isinstance(n, pyast.Call):
        return None
    # Check for Vec[Term](...) pattern
    fn = n.func
    if not (isinstance(fn, pyast.Subscript) and isinstance(fn.value, pyast.Name) and fn.value.id == "Vec"):
        return None

    names: list[str] = []
    for arg in n.args:
        name = _extract_term_var_name(arg)
        if name is None:
            return None
        names.append(name)
    return names


def _set_name_to_pred(name: str) -> str:
    """Convert set name to predicate name: Set_foo -> foo, Set_dom_Foo -> dom_Foo."""
    stem = name[4:] if name.startswith("Set_") else name
    # Preserve case for domain predicates (dom_Type)
    if stem.startswith("dom_"):
        return stem
    return stem.lower()


def _extract_partition_info(body: pyast.AST) -> tuple[str, list[str]] | None:
    """Extract (target_pred, [part_preds]) from Formula.Partition(...).

    Naming convention: Set_pred refers to the set of atoms making pred(...) true.
    E.g., Set_student -> predicate 'student', Set_f -> predicate 'f'.
    """
    if not isinstance(body, pyast.Call):
        return None
    if not _is_attr(body.func, "Formula", "Partition"):
        return None
    if len(body.args) != 2:
        return None

    target_term, parts_vec = body.args

    target_name = _extract_term_var_name(target_term)
    if target_name is None:
        return None

    part_names = _extract_vec_term_var_names(parts_vec)
    if part_names is None:
        return None

    # Convert Set_X -> predicate x (strip 'Set_' prefix and lowercase)
    target_pred = _set_name_to_pred(target_name)
    part_preds = [_set_name_to_pred(p) for p in part_names]

    return (target_pred, part_preds)


def _try_partition_to_asp(
    body: pyast.AST,
    *,
    pred_arg_types: Any = None,
    pred_patterns: dict[str, list[str]] | None = None,
) -> list[str] | None:
    r"""Try to convert Formula.Partition(...) to ASP constraint.

    (\partition F {{A B C}}) means:
    For each tuple where f(...) holds, exactly one of a(...), b(...), c(...) holds.

    The argument pattern is taken from pred_patterns to preserve constants.
    E.g., if f has pattern ["t", "I"], generates:
        :- f(t, I), #count{1,a:a(t, I); 1,b:b(t, I); 1,c:c(t, I)} != 1.
    """
    if not isinstance(body, pyast.Call):
        return None
    if not _is_attr(body.func, "Formula", "Partition"):
        return None
    if len(body.args) != 2:
        return None

    target_term, parts_vec = body.args

    # Extract target set name (e.g., Term.Var("F") -> "f")
    target_name = _extract_term_var_name(target_term)
    if target_name is None:
        return None

    # Extract partition parts (e.g., Vec[Term](Term.Var("A"), ...) -> ["a", "b", "c"])
    part_names = _extract_vec_term_var_names(parts_vec)
    if part_names is None or len(part_names) == 0:
        return None

    # Convert Set_X -> predicate x (strip 'Set_' prefix and lowercase)
    target_pred = _set_name_to_pred(target_name)
    part_preds = [_set_name_to_pred(p) for p in part_names]

    # Get the argument pattern from pred_patterns
    # First check the target, then the parts
    arg_pattern: list[str] | None = None
    if pred_patterns:
        if target_pred in pred_patterns:
            arg_pattern = pred_patterns[target_pred]
        else:
            # Try to infer from parts
            for p in part_preds:
                if p in pred_patterns:
                    arg_pattern = pred_patterns[p]
                    break

    # Build the argument string
    if arg_pattern:
        var_str = ", ".join(arg_pattern)
    else:
        # Fallback to single variable X if no pattern found
        var_str = "X"

    # Build the count aggregate elements
    # #count{1,a:a(t, I); 1,b:b(t, I); 1,c:c(t, I)}
    agg_elements = [f"1,{p}:{p}({var_str})" for p in part_preds]
    agg_body = "; ".join(agg_elements)

    # Build the constraint: :- f(t, I), #count{...} != 1.
    lits = [f"{target_pred}({var_str})", f"#count{{{agg_body}}} != 1"]

    # Add safety guards if needed
    safety_guards = _infer_safety_guards(lits, pred_arg_types=pred_arg_types)
    all_lits = list(safety_guards) + lits

    return [f":- {', '.join(all_lits)}."]


# =============================================================================
# 9b. AGGREGATE CONSTRAINT HANDLING
# =============================================================================


def _extract_pred_atom_info_simple(head: pyast.AST) -> tuple[str, tuple[str, ...]] | None:
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


def _invert_comparison_op(op: str) -> str | None:
    """Invert a comparison operator for integrity constraint conversion."""
    op = op.strip()
    if op == "==":
        op = "="
    inversions = {
        ">=": "<",
        ">": "<=",
        "<=": ">",
        "<": ">=",
        "=": "!=",
        "!=": "=",
    }
    return inversions.get(op)


def _flatten_or(n: pyast.AST) -> list[pyast.AST] | None:
    """Flatten nested Formula.Or(a, b) into a list of operands. Returns None if not an Or."""
    if not isinstance(n, pyast.Call) or not _is_attr(n.func, "Formula", "Or"):
        return None
    if len(n.args) != 2:
        return None
    result: list[pyast.AST] = []
    for arg in n.args:
        sub = _flatten_or(arg)
        if sub is not None:
            result.extend(sub)
        else:
            result.append(arg)
    return result


def _extract_agg_var_types(
    agg_body_node: pyast.AST,
    pred_arg_types: dict[str, list[str]],
) -> dict[str, str]:
    """Extract variable-to-type mapping from an aggregate body's predicate calls.

    Parses set_comprehension/set_comp_costly cubes to find Atom.Pred calls,
    then matches variable positions against pred_arg_types.
    """
    var_types: dict[str, str] = {}
    if not isinstance(agg_body_node, pyast.Call):
        return var_types
    if not (_is_attr(agg_body_node.func, "AggBody", "set_comprehension")
            or _is_attr(agg_body_node.func, "AggBody", "set_comp_costly")):
        return var_types
    if len(agg_body_node.args) != 2:
        return var_types

    _, cubes_vec = agg_body_node.args
    cube_nodes = _parse_vec_call(cubes_vec)

    for cube in cube_nodes:
        # Each cube may be grouped_and_lit, grouped_and, Lit, or And
        cube_lits_nodes = _collect_literal_nodes(cube)
        for lit_node in cube_lits_nodes:
            # Extract Atom.Pred from Literal(Atom.Pred(name, args), sign)
            if not isinstance(lit_node, pyast.Call) or not _is_name(lit_node.func, "Literal"):
                continue
            if len(lit_node.args) != 2:
                continue
            atom = lit_node.args[0]
            if not isinstance(atom, pyast.Call) or not _is_attr(atom.func, "Atom", "Pred"):
                continue
            if len(atom.args) != 2:
                continue
            pred_name = _const_str(atom.args[0])
            if not pred_name or pred_name not in pred_arg_types:
                continue
            arg_types = pred_arg_types[pred_name]
            args = _parse_varlist(atom.args[1])
            for i, arg in enumerate(args):
                if i >= len(arg_types):
                    break
                try:
                    vn = _term_to_asp(arg)
                    # Only map simple variables (uppercase start)
                    if vn and vn[0].isupper() and vn not in var_types:
                        var_types[vn] = arg_types[i]
                except Exception:
                    pass

    return var_types


def _collect_literal_nodes(cube: pyast.AST) -> list[pyast.AST]:
    """Recursively collect Literal(...) nodes from a cube formula."""
    results: list[pyast.AST] = []
    if isinstance(cube, pyast.Call):
        if _is_name(cube.func, "Literal"):
            results.append(cube)
            return results
        # GeneralLit.from_literal(Literal(...))
        if _is_attr(cube.func, "GeneralLit", "from_literal") and len(cube.args) == 1:
            results.append(cube.args[0])
            return results
        # Formula.Lit(GeneralLit.from_literal(Literal(...)))
        if _is_attr(cube.func, "Formula", "Lit") and len(cube.args) == 1:
            return _collect_literal_nodes(cube.args[0])
        # grouped_and_lit(Set[Literal](...)) or grouped_and(Set[GeneralLit](...))
        if (_is_attr(cube.func, "Formula", "grouped_and_lit")
                or _is_attr(cube.func, "Formula", "grouped_and")):
            if len(cube.args) == 1:
                for item in _parse_set_call(cube.args[0]):
                    results.extend(_collect_literal_nodes(item))
            return results
        # Formula.And(a, b)
        if _is_attr(cube.func, "Formula", "And") and len(cube.args) == 2:
            results.extend(_collect_literal_nodes(cube.args[0]))
            results.extend(_collect_literal_nodes(cube.args[1]))
            return results
    return results


def _try_agg_constraint_to_asp(
    body: pyast.AST,
    *,
    pred_arg_types: Any = None,
) -> list[str] | None:
    r"""Try to convert Formula.Agg to ASP constraint.

    Handles pattern:
        Formula.Agg("#count", SetExpr.SetVar("Set_pred", vars), comp_op, val)

    Where:
        - "Set_pred" is the set name (predicate is "pred" after stripping "Set_")
        - vars is cons_var(Term.Var("X"), ...) representing the counting variables
        - comp_op is ">=", "<=", "==", etc.
        - val is the comparison value

    Generates:
        :- #count{X : pred(X)} <inverted_op> val.

    For example:
        #count {Set_in_clique}(X) >= k
    becomes:
        :- #count{X : in_clique(X)} < k.
    """
    if not isinstance(body, pyast.Call):
        return None
    if not _is_attr(body.func, "Formula", "Agg"):
        return None
    if len(body.args) != 4:
        return None

    op_node, set_expr_node, comp_op_node, val_node = body.args

    # Check that it's a count aggregate
    op = _const_str(op_node)
    if op != "#count":
        return None

    # Extract set name and variables from SetExpr.SetVar("Set_pred", vars)
    if not isinstance(set_expr_node, pyast.Call):
        return None
    if not _is_attr(set_expr_node.func, "SetExpr", "SetVar"):
        return None
    if len(set_expr_node.args) != 2:
        return None

    set_name_node, vars_node = set_expr_node.args
    set_name = _const_str(set_name_node)
    if not set_name or not set_name.startswith("Set_"):
        return None

    # Extract predicate name (strip "Set_" prefix and lowercase)
    pred_name = set_name[4:].lower()  # "Set_in_clique" -> "in_clique"

    # Extract variable names from cons_var chain
    var_names = _extract_varlist_names(vars_node)
    if not var_names:
        return None

    # Get comparison operator and value
    comp_op = _const_str(comp_op_node)
    val_str = _term_to_asp(val_node)

    # Invert the comparison for the integrity constraint
    # If original is "count >= k", violation is "count < k"
    inverted_op = _invert_comparison_op(comp_op)
    if inverted_op is None:
        return None

    # Build the aggregate
    var_str = ", ".join(var_names)
    pred_call = f"{pred_name}({var_str})"
    agg = f"#count{{{var_str} : {pred_call}}}"

    constraint = f":- {agg} {inverted_op} {val_str}."
    return [constraint]


def _extract_varlist_names(n: pyast.AST) -> list[str] | None:
    """Extract variable names from cons_var(Term.Var("X"), cons_var(...)) chain."""
    if not isinstance(n, pyast.Call):
        return None

    names: list[str] = []
    cur = n

    while True:
        if isinstance(cur, pyast.Call):
            func = cur.func
            if isinstance(func, pyast.Name) and func.id == "nil_var":
                break
            if isinstance(func, pyast.Name) and func.id == "cons_var":
                if len(cur.args) != 2:
                    return None
                head, tail = cur.args
                name = _extract_term_var_name(head)
                if name:
                    names.append(name)
                cur = tail
                continue
        return None if not names else names

    return names if names else None


def _try_general_agg_raw_to_asp(
    body: pyast.AST,
    *,
    pred_arg_types: Any = None,
) -> list[str] | None:
    r"""Try to convert a raw constraint containing GeneralLit.general_agg to ASP.

    Handles patterns where the desugared aggregation formula was not extracted
    as an integrity constraint (e.g., standalone positive aggregates without
    outer quantifiers).

    Patterns handled:
        - Formula.Lit(GeneralLit.general_agg(...))
        - Formula.grouped_and(Set(GeneralLit.general_agg(...)))
        - Formula.grouped_forall(vars, <inner containing general_agg>)
    """
    from .rendering import _agg_body_to_asp_count

    agg_node = None
    forall_var_names: list[str] = []

    # Unwrap grouped_forall layers to collect universally quantified vars
    cur = body
    while isinstance(cur, pyast.Call) and _is_attr(cur.func, "Formula", "grouped_forall"):
        if len(cur.args) != 2:
            break
        vars_set, inner = cur.args
        for v in _parse_set_call(vars_set):
            vn = _term_to_asp(v)
            if vn not in forall_var_names:
                forall_var_names.append(vn)
        cur = inner

    # Unwrap single Forall layers
    while isinstance(cur, pyast.Call) and _is_attr(cur.func, "Formula", "Forall"):
        if len(cur.args) != 2:
            break
        var_node, inner = cur.args
        vn = _term_to_asp(var_node)
        if vn not in forall_var_names:
            forall_var_names.append(vn)
        cur = inner

    # Collect guard literals from Or(Not(guard1), Not(guard2), ..., agg)
    # This handles the normalized form of: impl(and(guards), agg)
    guard_lits: list[str] = []

    # Unwrap Or layers to find general_agg and negated guards
    or_operands = _flatten_or(cur)
    if or_operands is not None and len(or_operands) >= 2:
        # Separate negated guards from the aggregate
        for operand in or_operands:
            if isinstance(operand, pyast.Call) and _is_attr(operand.func, "Formula", "Not"):
                if len(operand.args) == 1:
                    inner = operand.args[0]
                    # Not(Lit(from_literal(Literal(Atom.Pred(...), True)))) → positive guard
                    try:
                        guard_str = _formula_to_body_lits(inner)
                        if len(guard_str) == 1:
                            guard_lits.append(guard_str[0])
                            continue
                    except Exception:
                        pass
            elif isinstance(operand, pyast.Call) and _is_attr(operand.func, "Formula", "Lit"):
                # Not(Lit(from_literal(Literal(atom, False)))) normalized to Lit(Literal(atom, True))
                # Also check for Lit(GeneralLit.general_agg(...))
                if len(operand.args) == 1:
                    inner_gl = operand.args[0]
                    if isinstance(inner_gl, pyast.Call) and _is_attr(inner_gl.func, "GeneralLit", "general_agg"):
                        agg_node = inner_gl
                        continue
                    # Check for negated literal (Lit(from_literal(Literal(atom, False))))
                    if isinstance(inner_gl, pyast.Call) and _is_attr(inner_gl.func, "GeneralLit", "from_literal"):
                        if len(inner_gl.args) == 1:
                            lit_node = inner_gl.args[0]
                            if isinstance(lit_node, pyast.Call) and _is_name(lit_node.func, "Literal"):
                                if len(lit_node.args) == 2:
                                    sign = _const_bool(lit_node.args[1])
                                    if not sign:
                                        # Negated literal in Or = positive guard
                                        try:
                                            pos_atom = _atom_to_asp(lit_node.args[0])
                                            guard_lits.append(pos_atom)
                                            continue
                                        except Exception:
                                            pass
        if agg_node is not None and guard_lits:
            # Successfully extracted agg + guards from Or pattern
            pass
        elif agg_node is None:
            # Reset guards if we didn't find the agg
            guard_lits = []

    # Try to extract general_agg from the inner formula (non-Or case)
    if agg_node is None:
        # Pattern: Formula.Lit(GeneralLit.general_agg(...))
        if isinstance(cur, pyast.Call) and _is_attr(cur.func, "Formula", "Lit"):
            if len(cur.args) == 1:
                inner_gl = cur.args[0]
                if isinstance(inner_gl, pyast.Call) and _is_attr(inner_gl.func, "GeneralLit", "general_agg"):
                    agg_node = inner_gl

        # Pattern: Formula.grouped_and(Set(single_general_agg))
        if agg_node is None and isinstance(cur, pyast.Call) and _is_attr(cur.func, "Formula", "grouped_and"):
            if len(cur.args) == 1:
                items = _parse_set_call(cur.args[0])
                if len(items) == 1:
                    item = items[0]
                    if isinstance(item, pyast.Call) and _is_attr(item.func, "GeneralLit", "general_agg"):
                        agg_node = item

    if agg_node is None:
        return None

    # Parse the general_agg: general_agg(op, body, comp, val)
    if len(agg_node.args) != 4:
        return None
    op_node, agg_body_node, comp_node, val_node = agg_node.args

    op_s = _const_str(op_node)
    if op_s != "count":
        return None
    comp_s = _const_str(comp_node)
    if comp_s == "==":
        comp_s = "="
    val_s = _term_to_asp(val_node)

    # Invert the comparison for the integrity constraint
    inverted_op = _invert_comparison_op(comp_s)
    if inverted_op is None:
        return None

    # Render the aggregate body
    agg_str = _agg_body_to_asp_count(agg_body_node)

    # Build body literals
    lits: list[str] = []

    # Add guards from Or(Not(guard), ..., agg) pattern (from impl normalization)
    lits.extend(guard_lits)

    # Add domain guards for forall-quantified variables not already guarded.
    # These must appear in the outer body to ground them — otherwise Clingo
    # treats them as local to the aggregate.
    guarded_vars = set()
    for gl in guard_lits:
        # Extract variable from dom_Type(Var) patterns
        m = re.match(r'^(\w+)\(([A-Z]\w*)\)$', gl)
        if m:
            guarded_vars.add(m.group(2))

    if forall_var_names and pred_arg_types:
        var_types = _extract_agg_var_types(agg_body_node, pred_arg_types)
        for vn in forall_var_names:
            if vn not in guarded_vars and vn in var_types:
                lits.append(f"dom_{var_types[vn]}({vn})")

    lits.append(f"{agg_str} {inverted_op} {val_s}")

    return [f":- {', '.join(lits)}."]


def _constraint_to_asp_lines(
    c: IRConstraint,
    *,
    entailment_specs: Any = None,
    pred_arg_types: Any = None,
    pred_patterns: dict[str, list[str]] | None = None,
    constraint_idx: int = -1,
) -> list[str]:
    result: list[str] = []

    # First, emit any rules generated from Let expressions
    if c.let_rules:
        result.extend(c.let_rules)

    if c.kind == "integrity":
        assert c.lits is not None
        glits = c.lits
        if entailment_specs:
            glits = _eliminate_entailed_general_lits(glits, entailment_specs)

        # Render as-is
        lits = [_general_lit_to_body_lit(gl) for gl in glits]
        # Safety check: add domain guards for unsafe variables
        safety_guards = _infer_safety_guards(lits, pred_arg_types=pred_arg_types)
        all_lits = list(safety_guards) + lits
        body = ", ".join(all_lits)
        result.append(f":- {body}.")
        return result

    if c.kind == "raw":
        assert c.body is not None
        # Try to handle known formula types
        partition_result = _try_partition_to_asp(c.body, pred_arg_types=pred_arg_types, pred_patterns=pred_patterns)
        if partition_result is not None:
            result.extend(partition_result)
            return result

        # Try aggregate constraint (e.g., #count {Set_X}(Y) >= k)
        agg_result = _try_agg_constraint_to_asp(c.body, pred_arg_types=pred_arg_types)
        if agg_result is not None:
            result.extend(agg_result)
            return result

        # Try general_agg form (from desugared projected aggregation)
        gagg_result = _try_general_agg_raw_to_asp(c.body, pred_arg_types=pred_arg_types)
        if gagg_result is not None:
            result.extend(gagg_result)
            return result

        # Fallback: emit as comment for unsupported formulas
        try:
            rendered = pyast.unparse(c.body)
        except Exception:
            rendered = pyast.dump(c.body)
        result.append(f":- % raw-constraint {rendered}.")
        return result

    raise TranspileError(f"Unknown constraint kind: {c.kind}")
