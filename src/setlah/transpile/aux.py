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

class AuxNamer:
    """Mints ``__aux_N`` names for one compilation unit.

    The rewriter numbers the auxiliaries it lowers itself and reports the next
    free index as ``program._aux_next``; the transpiler continues from there,
    so an auxiliary the rewriter left in place (its recursion depth exhausted)
    never reuses a name the rewriter already gave out.  See
    ``docs/known-issues.md`` (B7).
    """

    def __init__(self, start: int = 0) -> None:
        self.next = start

    def mint(self) -> str:
        name = f"__aux_{self.next}"
        self.next += 1
        return name


def _preprocess_aux_calls(block_expr_str: str, namer: AuxNamer | None = None) -> tuple[str, list[str]]:
    """Pre-process AuxCall patterns in the block expression.

    Two spellings occur, and both are lowered to auxiliary rules here:

    * ``GeneralLit.AuxCall(body_lits, qvars, free_vars)`` -- one rule.
    * ``Literal.AuxCall(body_cubes, qvars)`` -- the form the rewrite schema
      emits (``rewrite/egg_schema.py``); ``body_cubes`` is a ``Vec[Formula]``
      of DNF cubes and one rule is generated per cube, with the free variables
      computed as (variables in the cubes) minus the quantified ones.

    The call is replaced by ``Literal(Atom.Pred("__aux_N", free_vars), True)``.
    Handling the second spelling here is a fallback: the rewriter normally
    lowers those calls itself, and only leaves one in place when its recursive
    pass gives up (for example at maximum recursion depth). Without this the
    call reaches the renderer, which raises ``Expected Literal(atom, sign)``.
    See ``docs/known-issues.md`` (B1).

    ``namer`` supplies the names; a fresh one starting at ``__aux_0`` is used
    when none is given (standalone use, tests).

    Returns:
        (modified_expr_str, list_of_aux_rules)
    """
    if namer is None:
        namer = AuxNamer()

    aux_rules: list[str] = []
    result = block_expr_str

    # Either spelling; the prefix decides how the arguments are read.
    auxcall_pattern = r'(GeneralLit|Literal)\.AuxCall\('

    while True:
        match = re.search(auxcall_pattern, result)
        if not match:
            break

        start = match.start()
        prefix = match.group(1)
        # Extract the full AuxCall(...) expression
        call_str = _extract_balanced_call(result, start + len(prefix) + 1)
        call_full = prefix + "." + call_str

        # Parse the AuxCall arguments
        try:
            if prefix == "GeneralLit":
                aux_info = _parse_aux_call(call_full)
                cubes = None if aux_info is None else [aux_info[0]]
                free_vars = None if aux_info is None else aux_info[2]
            else:
                parsed = _parse_literal_aux_call(call_full)
                cubes, free_vars = (None, None) if parsed is None else parsed
            if cubes is None:
                # Can't parse, skip this match
                break

            # Generate aux predicate name
            aux_name = namer.mint()

            # Generate one aux rule per cube: aux_name(free_vars) :- cube
            for cube in cubes:
                aux_rules.append(_generate_aux_rule(aux_name, cube, free_vars))

            # Generate replacement: Literal(Atom.Pred("aux_name", free_vars_list), True)
            replacement = _generate_aux_call_replacement(aux_name, free_vars)

            # Replace in result
            end = start + len(call_full)
            result = result[:start] + replacement + result[end:]

        except Exception:
            # If parsing fails, skip this AuxCall (leave as is for error reporting later)
            break

    return result, aux_rules


def _parse_literal_aux_call(call_str: str) -> tuple[list[list[str]], list[str]] | None:
    """Parse ``Literal.AuxCall(body_cubes, qvars)``.

    Returns ``(cubes_as_asp, free_vars)``, where each cube is a list of ASP body
    literals, or None if the call cannot be read.
    """
    try:
        expr = pyast.parse(call_str, mode="eval").body
    except SyntaxError:
        return None

    if not isinstance(expr, pyast.Call) or not _is_attr(expr.func, "Literal", "AuxCall"):
        return None
    if len(expr.args) != 2:
        return None

    cubes_node, qvars_node = expr.args
    cubes: list[list[str]] = []
    all_vars: list[str] = []
    for cube_node in _parse_vec_elements(cubes_node):
        lit_nodes = _parse_conjunction_of_literals(cube_node)
        if lit_nodes is None:
            return None
        cubes.append([_literal_to_body_lit(lit) for lit in lit_nodes])
        all_vars.extend(_vars_in_nodes(lit_nodes))

    qvars = {v for v in (_extract_var_name(n) for n in _parse_set_call(qvars_node)) if v}
    free_vars: list[str] = []
    for v in all_vars:
        if v not in qvars and v not in free_vars:
            free_vars.append(v)
    return cubes, free_vars


def _parse_vec_elements(node: pyast.AST) -> list:
    """Elements of ``Vec[T](...)`` or ``Vec[T].empty()``."""
    if isinstance(node, pyast.Call):
        if isinstance(node.func, pyast.Attribute) and node.func.attr == "empty":
            return []
        return list(node.args)
    return []


def _parse_conjunction_of_literals(node: pyast.AST) -> list | None:
    """Literal nodes of one DNF cube, in any of the forms the extractor picks."""
    if not isinstance(node, pyast.Call) or not isinstance(node.func, pyast.Attribute):
        return None
    cls_name = node.func.value.id if isinstance(node.func.value, pyast.Name) else None
    method = node.func.attr
    if cls_name != "Formula":
        return None

    if method == "grouped_and_lit" and len(node.args) == 1:
        return _parse_set_call(node.args[0])

    if method == "And" and len(node.args) == 2:
        left = _parse_conjunction_of_literals(node.args[0])
        right = _parse_conjunction_of_literals(node.args[1])
        if left is None or right is None:
            return None
        return left + right

    if method == "Lit" and len(node.args) == 1:
        inner = node.args[0]
        if isinstance(inner, pyast.Call) and _is_attr(inner.func, "GeneralLit", "from_literal"):
            if len(inner.args) == 1:
                return [inner.args[0]]
        return None

    return None


def _vars_in_nodes(nodes: list) -> list[str]:
    """Variable names appearing in the given AST nodes, in order of appearance."""
    out: list[str] = []
    for node in nodes:
        for sub in pyast.walk(node):
            name = _extract_var_name(sub)
            if name and name not in out:
                out.append(name)
    return out


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

        # An auxiliary predicate defined by several rules (one per disjunct) is typed
        # by merging them: a rule whose body does not mention one of the arguments
        # types it UNKNOWN, while a sibling rule that does mention it knows the type.
        # Keep the known one, so a head variable unbound in this rule can still be
        # guarded (docs/known-issues.md, B3).
        previous = aux_types.get(aux_name)
        if previous and len(previous) == len(aux_arg_types):
            aux_arg_types = [
                old if new in ("UNKNOWN", "CONST") and old not in ("UNKNOWN", "CONST") else new
                for old, new in zip(previous, aux_arg_types)
            ]
        aux_types[aux_name] = aux_arg_types

    return aux_types
