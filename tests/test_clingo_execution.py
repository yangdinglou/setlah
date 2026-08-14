import clingo.ast

from setlah.transpile import run_clingo_ast


def test_run_clingo_ast_solves_program():
    nodes = []
    models = []
    clingo.ast.parse_string("answer.", nodes.append)

    result = run_clingo_ast(
        nodes,
        on_model=lambda model: models.append(str(model)),
    )

    assert result.satisfiable
    assert models == ["answer"]
