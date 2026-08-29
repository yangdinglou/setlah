from __future__ import annotations

from pathlib import Path

import pytest

from setlah import (
    CompileOptions,
    EngineError,
    ErrorCategory,
    Program,
    SolveOptions,
    SolveStatus,
    atom,
    function,
    string,
    symbol,
)


CHOICE = r"""
ExtDOM Item: INT.
ExtPred available: (Item).
[
    selected(X)? :- available(X).
    (\exists X. selected(X)).
]
"""


def test_program_validates_source_eagerly(capsys) -> None:
    Program(CHOICE)
    with pytest.raises(EngineError) as caught:
        Program("not SetLaH")
    assert caught.value.category is ErrorCategory.PARSE
    assert capsys.readouterr().out == ""


def test_program_loads_from_file() -> None:
    program = Program.from_file(Path("examples/choose.sl"))
    assert "available" in program.source


def test_instance_is_immutable_and_solves_typed_facts() -> None:
    empty = Program(CHOICE).instance().add_raw_facts("dom_Item(1..3).")
    populated = (
        empty.add_fact("available", 1)
        .add_fact("available", 2)
        .add_fact("metadata", string("example"), function("pair", 1, symbol("red")))
        .add_fact("disabled", 3, positive=False)
    )

    assert empty.fact_sources == ("dom_Item(1..3).",)
    result = populated.solve()
    assert result.status is SolveStatus.SATISFIABLE
    assert len(result.models) == 1
    model = result.models[0]
    assert model.atoms_named("selected")
    metadata = model.atoms_named("metadata")[0]
    assert metadata.arguments[0].string == "example"
    assert metadata.arguments[1].name == "pair"
    assert model.atoms_named("disabled")[0].positive is False


def test_atom_and_constant_helpers_compile() -> None:
    instance = (
        Program(CHOICE)
        .instance()
        .add_raw_facts("dom_Item(1).")
        .add_atom(atom("available", 1))
        .add_const("limit", 1)
    )
    compiled = instance.compile(CompileOptions(grounding=True))
    assert "available(1)." in compiled.asp
    assert "#const limit=1." in compiled.asp


def test_program_convenience_compile_and_unsat_solve() -> None:
    assert "selected" in Program(CHOICE).compile().asp
    result = Program(CHOICE).solve(SolveOptions(max_models=1))
    assert result.status is SolveStatus.UNSATISFIABLE


def test_raw_fact_errors_remain_structured() -> None:
    instance = Program(CHOICE).instance().add_raw_facts("broken(")
    with pytest.raises(EngineError) as caught:
        instance.solve()
    assert caught.value.category is ErrorCategory.GROUNDING


@pytest.mark.parametrize(
    "operation",
    [
        lambda: symbol("Upper"),
        lambda: function("f", "ambiguous"),
        lambda: atom("available", True),
        lambda: Program(CHOICE).instance().add_const("Limit", 1),
    ],
)
def test_typed_helpers_reject_ambiguous_or_invalid_values(operation) -> None:
    with pytest.raises((TypeError, ValueError)):
        operation()
