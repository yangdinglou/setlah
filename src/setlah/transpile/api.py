"""
Public API
==========

Entry points for transpilation and execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

import clingo
import clingo.ast

from .ir import TranspileError, IRRule, IRConstraint, PrintedBlock, LoweredBlock
from .normalize import _split_top_level_commas
from .aux import AuxNamer, _extract_aux_pred_types
from .safety import _infer_safety_guards
from .pipeline import transpile_block_expr_to_asp, transpile_printed_block_to_asp, _lower_block


# =============================================================================
# 1. PUBLIC API
# =============================================================================


@dataclass(frozen=True)
class TranspileResult:
    source: str
    ast: list[clingo.ast.AST]


def transpile_program_to_asp(program: Any, *, grounding: bool = False) -> str:
    """Transpile a rewritten Program to ASP source (no clingo parsing)."""
    parts: list[str] = []

    entailment_specs = getattr(program, "_entailment_specs", None)
    pred_arg_types = getattr(program, "_pred_arg_types", None)

    # Get aux rules collected during rewriting, and continue its auxiliary
    # numbering so the names minted here cannot collide with them (B7).
    rewriter_aux_rules = getattr(program, "_aux_rules", [])
    aux_namer = AuxNamer(getattr(program, "_aux_next", 0))

    blocks = getattr(program, "blocks", None)
    if blocks is None:
        raise TranspileError("Expected Program with .blocks")

    for block in blocks:
        if isinstance(block, LoweredBlock):
            parts.append(
                _lower_block(
                    block.rules,
                    block.constraints,
                    [],
                    entailment_specs=entailment_specs,
                    pred_arg_types=pred_arg_types,
                    grounding=grounding,
                    rewriter_aux_rules=rewriter_aux_rules,
                )
            )
            continue
        if isinstance(block, PrintedBlock):
            parts.append(
                transpile_printed_block_to_asp(
                    block,
                    entailment_specs=entailment_specs,
                    pred_arg_types=pred_arg_types,
                    grounding=grounding,
                    rewriter_aux_rules=rewriter_aux_rules,
                    aux_namer=aux_namer,
                )
            )
            continue
        if isinstance(block, tuple) and len(block) == 2 and isinstance(block[1], int):
            block_expr = block[0]
        else:
            block_expr = block
        parts.append(
            transpile_block_expr_to_asp(
                str(block_expr),
                entailment_specs=entailment_specs,
                pred_arg_types=pred_arg_types,
                grounding=grounding,
                rewriter_aux_rules=rewriter_aux_rules,
                aux_namer=aux_namer,
            )
        )

    # Prepend aux rules from rewriter (they define predicates used in constraints).
    # Apply safety guards: variables that appear only in negative/comparison literals need
    # dom_<Type>(V) guards so Clingo can ground them.
    if rewriter_aux_rules:
        # Build pred_arg_types extended with types inferred from the aux rules themselves
        # (needed for nested aux predicates).
        aux_pred_types = _extract_aux_pred_types(rewriter_aux_rules, pred_arg_types or {})
        merged_aux_types = dict(pred_arg_types or {})
        merged_aux_types.update(aux_pred_types)

        guarded_aux_rules: list[str] = []
        for rule in rewriter_aux_rules:
            rule = rule.strip()
            if ":-" in rule and not rule.startswith(":-"):
                head, _, body_raw = rule.partition(":-")
                head = head.strip()
                body_raw = body_raw.rstrip(".").strip()
                body_lits = [lit.strip() for lit in _split_top_level_commas(body_raw) if lit.strip()]
                guards = _infer_safety_guards(
                    body_lits, pred_arg_types=merged_aux_types, head_lits=[head]
                )
                if guards:
                    guarded_aux_rules.append(f"{head} :- {', '.join(guards + body_lits)}.")
                else:
                    guarded_aux_rules.append(rule)
            else:
                guarded_aux_rules.append(rule)
        aux_section = "\n".join(guarded_aux_rules)
        parts.insert(0, aux_section)

    # Theory rules of the order-sort lowering (docs/order-sorts.md), emitted verbatim:
    # reified comparison Booleans with their &diff atoms and the sorts' ranges.
    theory_rules = getattr(program, "_theory_rules", None)
    if theory_rules:
        parts.append("% order sorts: lowering rules (difference logic where &diff atoms occur: run with clingo-dl)\n" + "\n".join(theory_rules))

    # Allow empty lines between blocks for readability.
    return "\n\n".join(p for p in parts if p.strip()) + "\n"


def transpile_program_to_clingo(
    program: Any,
    *,
    grounding: bool = False,
) -> TranspileResult:
    """Transpile a rewritten Program (whose blocks are extracted egg expressions) to Clingo AST."""
    source = transpile_program_to_asp(program, grounding=grounding)
    ast_nodes = _parse_asp_to_clingo_ast(source)
    return TranspileResult(source=source, ast=ast_nodes)


def run_clingo_ast(
    ast_nodes: Iterable[clingo.ast.AST],
    *,
    extra_files: list[str] | None = None,
    arguments: list[str] | None = None,
    on_model: Callable[[clingo.Model], None] | None = None,
) -> clingo.SolveResult:
    """Execute a clingo program represented as AST nodes.

    Args:
        ast_nodes:   The compiled SetLaH program as clingo AST nodes.
        extra_files: Optional list of .lp fact/instance files to load into
                     the same clingo session (e.g. domain facts, puzzle inputs).
        arguments:   Extra clingo command-line arguments (e.g. ["-n", "0"]).
        on_model:    Callback invoked for each answer set.
    """
    ctl = clingo.Control(arguments or [])
    with clingo.ast.ProgramBuilder(ctl) as builder:
        for node in ast_nodes:
            builder.add(node)
    for path in (extra_files or []):
        ctl.load(path)
    ctl.ground([("base", [])])
    return ctl.solve(on_model=on_model)


# =============================================================================
# 14. CLINGO AST PARSING
# =============================================================================


def _parse_asp_to_clingo_ast(source: str) -> list[clingo.ast.AST]:
    nodes: list[clingo.ast.AST] = []

    def on_ast(node: clingo.ast.AST) -> None:
        nodes.append(node)

    clingo.ast.parse_string(source, on_ast)
    return nodes


def run_clingodl_source(
    source: str,
    *,
    extra_files: list[str] | None = None,
    arguments: list[str] | None = None,
    on_model: Callable[[Any], None] | None = None,
) -> Any:
    """Execute a program with ``&diff`` atoms under clingo-dl (the order-sort lowering)."""
    try:
        from clingodl import ClingoDLTheory
    except ImportError as e:  # pragma: no cover
        raise TranspileError("The program uses order sorts (difference logic); install clingo-dl (pip install clingo-dl)") from e
    thy = ClingoDLTheory()
    ctl = clingo.Control(arguments or [])
    thy.register(ctl)
    with clingo.ast.ProgramBuilder(ctl) as builder:
        clingo.ast.parse_string(source, lambda stm: thy.rewrite_ast(stm, builder.add))
    for path in (extra_files or []):
        ctl.load(path)
    ctl.ground([("base", [])])
    thy.prepare(ctl)

    def _on_model(m):
        thy.on_model(m)
        if on_model is not None:
            on_model((m, [(str(k), v) for k, v in thy.assignment(m.thread_id)]))

    return ctl.solve(on_model=_on_model)
