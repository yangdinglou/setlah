"""
Rewrite
=======

Pattern detection and count rewrites for ASP optimization.
"""

from __future__ import annotations

import ast as pyast
import re
from collections import Counter
from typing import Any

from .ir import IRConstraint, TranspileError
from .pyast_utils import (
    _is_name, _is_attr,
    _const_str, _const_bool,
)
from .rendering import _term_to_asp, _general_lit_to_body_lit
from .normalize import _split_top_level_commas, _alpha_normalize_var_in_lit
from .safety import _extract_vars_from_lit
from .entailment import (
    _eliminate_entailed_general_lits,
    _pos_pred_literal,
    _term_var_name,
    _term_contains_var,
    _general_lit_mentions_var,
    _pred_lit_key,
    _term_key,
)


# =============================================================================
# 10. COUNT AGGREGATE REWRITES
# =============================================================================


def _collect_existing_count_agg_cores(
    constraints: list[IRConstraint],
    *,
    entailment_specs: Any = None,
) -> set[tuple[str, ...]]:
    """Collect normalized count-aggregate cores already present in integrity constraints.

    We only handle the single-var `#count{X : ...}` shape here.
    The returned key ignores the comparison operator and RHS value, and alpha-normalizes
    the counted variable to `__X__`.
    """
    cores: set[tuple[str, ...]] = set()
    for c in constraints:
        if c.kind != "integrity" or c.lits is None:
            continue
        glits = c.lits
        if entailment_specs:
            glits = _eliminate_entailed_general_lits(glits, entailment_specs)
        lits = [_general_lit_to_body_lit(gl) for gl in glits]
        for lit in lits:
            core = _count_agg_core_from_body_lit(lit)
            if core is not None:
                cores.add(core)
    return cores


def _count_agg_core_from_body_lit(lit: str) -> tuple[str, ...] | None:
    """Normalize `#count{X : conds} <op> val` into a comparable core key.

    Returns a tuple of normalized condition literals (sorted), where the counted variable
    is alpha-normalized to `__X__`.
    """
    lit = lit.strip()
    if not lit.startswith("#count{"):
        return None

    close = lit.find("}")
    if close == -1:
        return None

    inner = lit[len("#count{") : close].strip()
    # For now, only support single element aggregates (no ';').
    if ";" in inner:
        return None

    if ":" in inner:
        tuple_part, cond_part = inner.split(":", 1)
        tuple_part = tuple_part.strip()
        cond_part = cond_part.strip()
    else:
        tuple_part = inner.strip()
        cond_part = ""

    # Single-var only (no tuple).
    if not tuple_part or "," in tuple_part:
        return None
    counted_var = tuple_part

    cond_lits = [c.strip() for c in _split_top_level_commas(cond_part) if c.strip()] if cond_part else []
    if not cond_lits:
        return None

    normalized = [_alpha_normalize_var_in_lit(s, counted_var, "__X__") for s in cond_lits]
    return tuple(sorted(normalized))


def _extract_existence_pattern(
    body_lits: list[str],
    *,
    pred_arg_types: Any,
) -> tuple[str, list[str], list[str]] | None:
    """Detect pattern: `not pred(..., _)` → `#count{X : pred(..., X)} = 0`.

    Returns (counted_var, shared_lits, cond_lits) if pattern matches.
    """
    if not isinstance(pred_arg_types, dict):
        return None

    # Look for a single negated predicate with exactly one anonymous variable
    negated_pred_idx = None
    anon_pos = None
    pred_name = None

    for idx, lit in enumerate(body_lits):
        lit = lit.strip()
        if not lit.startswith("not "):
            continue

        inner = lit[4:].strip()
        # Parse predicate call
        match = re.match(r'([a-z_][a-z0-9_]*)\s*\((.*)\)', inner, re.IGNORECASE)
        if not match:
            continue

        p_name = match.group(1)
        args_str = match.group(2)
        args = [a.strip() for a in args_str.split(',') if a.strip()]

        # Check if exactly one arg is '_'
        anon_positions = [i for i, arg in enumerate(args) if arg == '_']
        if len(anon_positions) != 1:
            continue

        if negated_pred_idx is not None:
            return None  # Multiple candidates, ambiguous

        negated_pred_idx = idx
        anon_pos = anon_positions[0]
        pred_name = p_name

    if negated_pred_idx is None or pred_name is None or anon_pos is None:
        return None

    # Infer the type of the anonymous variable from predicate signature
    types = pred_arg_types.get(pred_name)
    if not types or not isinstance(types, (list, tuple)) or anon_pos >= len(types):
        return None

    var_type = types[anon_pos]
    if not isinstance(var_type, str) or var_type in ("UNKNOWN", "CONST"):
        return None

    # Generate a fresh variable name for the counted variable
    # Use the type name to make it readable
    counted_var = var_type[0].upper() if var_type else "X"
    # Make sure it's unique (check all literals for conflicts)
    existing_vars = set()
    for lit in body_lits:
        existing_vars.update(_extract_vars_from_lit(lit))
    base_var = counted_var
    counter = 1
    while counted_var in existing_vars:
        counted_var = f"{base_var}{counter}"
        counter += 1

    # Reconstruct the positive literal with the counted variable
    negated_lit = body_lits[negated_pred_idx].strip()[4:].strip()  # Remove "not "
    match = re.match(r'([a-z_][a-z0-9_]*)\s*\((.*)\)', negated_lit, re.IGNORECASE)
    if not match:
        return None

    args_str = match.group(2)
    args = [a.strip() for a in args_str.split(',') if a.strip()]
    args[anon_pos] = counted_var
    positive_lit = f"{pred_name}({', '.join(args)})"

    cond_lits = [positive_lit]
    shared_lits = [lit for i, lit in enumerate(body_lits) if i != negated_pred_idx]

    return (counted_var, shared_lits, cond_lits)


def _is_existence_pattern(body_lits: list[str]) -> bool:
    """Check if the constraint matches the existence pattern (not pred(_))."""
    for lit in body_lits:
        lit = lit.strip()
        if lit.startswith("not ") and "_" in lit:
            return True
    return False


def _maybe_rewrite_equiv_neq_to_count(
    glits: list[pyast.AST],
    *,
    grounding: bool,
    existing_count_cores: set[tuple[str, ...]] | None,
    pred_arg_types: Any,
) -> list[str] | None:
    """Rewrite a symmetric `X1 != X2` uniqueness constraint into `#count{X : ...} > 1`.

    Pattern (single counted variable):
      shared, G(X1, ...), ..., G(X2, ...), ..., (X1 != X2)
    where the group of positive predicate atoms containing X1 matches the group
    containing X2 under X1<->X2 substitution.

    If grounding=False, only apply when a matching count aggregate core already exists
    somewhere in the block (to enable later merging).
    """
    cand = _extract_equiv_neq_candidate(glits, pred_arg_types=pred_arg_types)
    if cand is None:
        return None
    counted_var, shared_lits, cond_lits = cand

    core = tuple(sorted(_alpha_normalize_var_in_lit(s, counted_var, "__X__") for s in cond_lits))
    if not grounding:
        if not existing_count_cores or core not in existing_count_cores:
            return None

    cond = ", ".join(cond_lits)
    agg = f"#count{{{counted_var} : {cond}}} > 1"
    # De-duplicate while preserving order: guards/shared first, aggregate last.
    out: list[str] = []
    seen: set[str] = set()
    for lit in list(shared_lits) + [agg]:
        if lit in seen:
            continue
        seen.add(lit)
        out.append(lit)
    return out


def _extract_equiv_neq_candidate(
    glits: list[pyast.AST],
    *,
    pred_arg_types: Any,
) -> tuple[str, list[str], list[str]] | None:
    """Return (counted_var, shared_body_lits, cond_body_lits) if the pattern matches.

    `shared_body_lits` will include inferred `dom_<Type>(Var)` guards for the aggregate's
    global variables (those that appear in the counted predicate body but are *not* the
    counted variable itself).
    """
    # Find a single inequality between two Term.Var names.
    ineq_idx = None
    v1 = None
    v2 = None

    for i, gl in enumerate(glits):
        vars_pair = _ineq_var_pair(gl)
        if vars_pair is None:
            continue
        if ineq_idx is not None:
            return None  # ambiguous: multiple inequalities
        ineq_idx = i
        v1, v2 = vars_pair

    if ineq_idx is None or v1 is None or v2 is None or v1 == v2:
        return None

    # Partition positive predicate lits mentioning v1 vs v2.
    group1: list[int] = []
    group2: list[int] = []
    mentions_v1_elsewhere = False
    mentions_v2_elsewhere = False

    for i, gl in enumerate(glits):
        if i == ineq_idx:
            continue

        # Only allow predicate literals (positive) in the groups.
        pred = _pos_pred_literal(gl)
        if pred is not None:
            _pred_name, args = pred
            has_v1 = any(_term_contains_var(a, v1) for a in args)
            has_v2 = any(_term_contains_var(a, v2) for a in args)
            if has_v1 and has_v2:
                return None
            if has_v1:
                group1.append(i)
                continue
            if has_v2:
                group2.append(i)
                continue
            continue

        # If it's a non-predicate literal, it must not mention v1/v2.
        if _general_lit_mentions_var(gl, v1):
            mentions_v1_elsewhere = True
        if _general_lit_mentions_var(gl, v2):
            mentions_v2_elsewhere = True

    if mentions_v1_elsewhere or mentions_v2_elsewhere:
        return None
    if not group1 or not group2 or len(group1) != len(group2):
        return None

    # Check alpha-equivalence between groups under v1<->v2 substitution.
    key1 = Counter(_pred_lit_key(glits[i], rename={v1: "__X__"}) for i in group1)
    key2 = Counter(_pred_lit_key(glits[i], rename={v2: "__X__"}) for i in group2)
    if key1 != key2:
        return None

    # Build output pieces.
    cond_lits = [_general_lit_to_body_lit(glits[i]) for i in group1]
    shared_lits = [_general_lit_to_body_lit(gl) for i, gl in enumerate(glits) if i not in set(group1 + group2 + [ineq_idx])]

    return (v1, shared_lits, cond_lits)


def _ineq_var_pair(gl: pyast.AST) -> tuple[str, str] | None:
    """If gl is `X != Y` or `not X = Y` for Term.Var X,Y, return (X,Y)."""
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
    sign_b = _const_bool(sign)

    if not (isinstance(atom, pyast.Call) and _is_attr(atom.func, "Atom", "Comp") and len(atom.args) == 3):
        return None
    op = _const_str(atom.args[0])
    if op == "==":
        op = "="

    l = atom.args[1]
    r = atom.args[2]
    l_name = _term_var_name(l)
    r_name = _term_var_name(r)
    if l_name is None or r_name is None:
        return None

    # Either explicit inequality, or default-negated equality.
    if op == "!=" and sign_b is True:
        return (l_name, r_name)
    if op == "=" and sign_b is False:
        return (l_name, r_name)
    return None


def _eq_var_pair(gl: pyast.AST) -> tuple[str, str] | None:
    """If gl is a positive equality `V1 = V2` between two Term.Var, return (V1, V2)."""
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
    sign_b = _const_bool(sign)

    if not (isinstance(atom, pyast.Call) and _is_attr(atom.func, "Atom", "Comp") and len(atom.args) == 3):
        return None
    op = _const_str(atom.args[0])

    l_name = _term_var_name(atom.args[1])
    r_name = _term_var_name(atom.args[2])
    if l_name is None or r_name is None:
        return None

    # Positive equality: op is "=" or "==" with sign True
    if op in ("=", "==") and sign_b is True:
        return (l_name, r_name)
    return None


def _subst_var_in_pyast(node: pyast.AST, old: str, new: str) -> pyast.AST:
    """Deep-copy a pyast node, replacing Term.Var(old) with Term.Var(new)."""
    import copy
    node = copy.deepcopy(node)
    for n in pyast.walk(node):
        if isinstance(n, pyast.Call) and _is_attr(n.func, "Term", "Var") and len(n.args) == 1:
            if isinstance(n.args[0], pyast.Constant) and n.args[0].value == old:
                n.args[0] = pyast.Constant(value=new)
    return node


def _substitute_var_equalities_pyast(glits: list[pyast.AST]) -> list[pyast.AST]:
    """Substitute V1 = V2 equalities at the pyast level.

    For each positive equality between two variables, replace the
    lexicographically-later variable with the earlier one in all other
    literals and drop the equality.  This enables downstream Phase 1
    detection of ``!=`` patterns for ``--grounding`` aggregate conversion.
    """
    subst: dict[str, str] = {}
    eq_indices: set[int] = set()

    for i, gl in enumerate(glits):
        pair = _eq_var_pair(gl)
        if pair is None:
            continue
        v1, v2 = pair
        if v1 == v2:
            eq_indices.add(i)  # tautology, just drop it
            continue
        old, new = (v2, v1) if v1 < v2 else (v1, v2)
        # Chase substitution chain
        while new in subst:
            new = subst[new]
        subst[old] = new
        eq_indices.add(i)

    if not subst:
        return glits

    # Resolve chains once, then copy each literal once and rename in one walk
    # (one deep copy per literal per equality was quadratic and dominated the
    # compile of constraints with many equalities).
    resolved = {old: new for old, new in subst.items()}
    for old in list(resolved):
        new = resolved[old]
        while new in resolved:
            new = resolved[new]
        resolved[old] = new

    import copy
    result: list[pyast.AST] = []
    for i, gl in enumerate(glits):
        if i in eq_indices:
            continue
        node = copy.deepcopy(gl)
        for n in pyast.walk(node):
            if isinstance(n, pyast.Call) and _is_attr(n.func, "Term", "Var") and len(n.args) == 1:
                arg = n.args[0]
                if isinstance(arg, pyast.Constant) and arg.value in resolved:
                    n.args[0] = pyast.Constant(value=resolved[arg.value])
        result.append(node)
    return result


def _extract_count_constraint_pattern(lits: list[str]) -> tuple[list[str], str, list[str], str, str, list[str]] | None:
    """Extract count constraint pattern from constraint body literals.

    Pattern: shared_lits, #count{vars : pred(args)} op val

    Returns: (counted_vars, pred_name, pred_args, comp_op, val, shared_lits)
    """
    count_lit_idx = None
    for idx, lit in enumerate(lits):
        if lit.strip().startswith("#count{"):
            count_lit_idx = idx
            break

    if count_lit_idx is None:
        return None

    count_lit = lits[count_lit_idx].strip()
    shared_lits = [lits[i] for i in range(len(lits)) if i != count_lit_idx]

    # Parse #count{vars : pred(args)} op val
    match = re.match(r'#count\{([^}]+)\}\s*([!<>=]+)\s*(.+)', count_lit)
    if not match:
        return None

    inner = match.group(1).strip()
    comp_op = match.group(2).strip()
    val = match.group(3).strip()

    # Parse inner: "vars : pred(args)" or just "pred(args)"
    if ":" in inner:
        vars_part, cond_part = inner.split(":", 1)
        counted_vars = [v.strip() for v in vars_part.split(",")]
        cond_part = cond_part.strip()
    else:
        # No explicit vars, infer from condition
        cond_part = inner.strip()
        counted_vars = []

    # Parse condition predicate
    pred_match = re.match(r'([a-z_][a-z0-9_]*)\s*\((.*)\)', cond_part, re.IGNORECASE)
    if not pred_match:
        return None

    pred_name = pred_match.group(1)
    args_str = pred_match.group(2).strip()
    pred_args = [a.strip() for a in args_str.split(",")] if args_str else []

    # If no explicit counted vars, infer them from pred args
    if not counted_vars:
        counted_vars = pred_args.copy()

    return (counted_vars, pred_name, pred_args, comp_op, val, shared_lits)
