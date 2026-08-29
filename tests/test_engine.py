from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import subprocess
import sys

import pytest

from setlah.engine import (
    CompileOptions,
    EngineError,
    ErrorCategory,
    SolveOptions,
    SolveStatus,
    SymbolKind,
    compile_source,
    solve_source,
)


CHOICE = r"""
ExtDOM Item: INT.
ExtPred available: (Item).
[
    selected(X)? :- available(X).
    (\exists X. selected(X)).
]
"""


def _solve_choice_subprocess(_: int) -> str:
    request = json.dumps({
        "protocol": 1,
        "operation": "solve",
        "source": CHOICE,
        "facts": ["dom_Item(1..3). available(1..3)."],
    })
    completed = subprocess.run(
        [sys.executable, "-m", "setlah", "protocol"],
        input=request,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)["status"]


def test_compile_source_includes_in_memory_facts() -> None:
    result = compile_source(CHOICE, ["dom_Item(1..3). available(1..3)."])
    assert "{selected(X)}" in result.asp
    assert "available(1..3)." in result.asp


def test_solve_source_defaults_to_one_structured_model() -> None:
    result = solve_source(
        CHOICE,
        ['dom_Item(1..3). available(1..3). metadata("x",f(2)). -negative(1).'],
    )
    assert result.status is SolveStatus.SATISFIABLE
    assert len(result.models) == 1
    symbols = result.models[0].symbols
    metadata = next(symbol for symbol in symbols if symbol.name == "metadata")
    assert metadata.kind is SymbolKind.FUNCTION
    assert metadata.arguments[0].kind is SymbolKind.STRING
    assert metadata.arguments[1].name == "f"
    negative = next(symbol for symbol in symbols if symbol.name == "negative")
    assert not negative.positive


def test_unsatisfiable_status() -> None:
    result = solve_source(CHOICE, ["dom_Item(1..3)."])
    assert result.status is SolveStatus.UNSATISFIABLE
    assert result.models == ()


def test_all_models_must_be_requested_explicitly() -> None:
    default = solve_source(CHOICE, ["dom_Item(1..2). available(1..2)."])
    all_models = solve_source(
        CHOICE,
        ["dom_Item(1..2). available(1..2)."],
        SolveOptions(max_models=0),
    )
    assert len(default.models) == 1
    assert len(all_models.models) == 3


def test_clingo_model_argument_remains_compatible() -> None:
    result = solve_source(
        CHOICE,
        ["dom_Item(1..2). available(1..2)."],
        SolveOptions(clingo_arguments=("-n", "0")),
    )
    assert len(result.models) == 3


def test_invalid_clingo_arguments_are_structured_errors() -> None:
    with pytest.raises(EngineError) as caught:
        solve_source(CHOICE, [], SolveOptions(clingo_arguments=("--bad-option",)))
    assert caught.value.category is ErrorCategory.SOLVE


def test_invalid_fact_source_is_a_grounding_error() -> None:
    with pytest.raises(EngineError) as caught:
        solve_source(CHOICE, ["broken("])
    assert caught.value.category is ErrorCategory.GROUNDING


def test_semantic_errors_are_not_ignored() -> None:
    source = "ExtPred bad: (Missing). [ bad(X)? :- bad(X). ]"
    with pytest.raises(EngineError) as caught:
        compile_source(source)
    assert caught.value.category is ErrorCategory.SEMANTIC_CHECK
    assert "Missing" in caught.value.message


def test_literal_fact_head_refines_against_existing_signature() -> None:
    source = """
    ExtDOM ID: INT.
    ExtDOM Value: Symbol.
    ExtPred is_id: (ID).
    ExtPred is_value: (Value).
    [
      relation(X, Y)? :- is_id(X), is_value(Y).
      relation(1, fixed).
    ]
    """
    assert "relation(1, fixed)." in compile_source(source).asp


def test_domains_with_same_primitive_representation_are_compatible() -> None:
    source = """
    ExtDOM Left: INT.
    ExtDOM Right: INT.
    ExtPred left: (Left).
    ExtPred right: (Right).
    [both(X) :- left(X), right(X).]
    """
    assert "both(X)" in compile_source(source).asp


def test_domains_with_different_primitive_representations_conflict() -> None:
    source = """
    ExtDOM Left: INT.
    ExtDOM Right: Symbol.
    ExtPred left: (Left).
    ExtPred right: (Right).
    [both(X) :- left(X), right(X).]
    """
    with pytest.raises(EngineError) as caught:
        compile_source(source)
    assert caught.value.category is ErrorCategory.SEMANTIC_CHECK


def test_invalid_compile_option() -> None:
    with pytest.raises(ValueError):
        CompileOptions(entailment_elim="invalid")


def test_concurrent_solves_have_no_shared_temporary_files() -> None:
    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(_solve_choice_subprocess, range(4)))
    assert statuses == ["satisfiable"] * 4
