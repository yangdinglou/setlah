import contextlib
import io

from setlah.parsing.parser import Parser
from setlah.rewrite.rw import Rewriter
from setlah.transpile import transpile_program_to_asp


def test_negated_binary_predicate_is_not_rewritten_as_uniqueness():
    source = r"""
ExtDOM Node: INT.
ExtPred node: (Node).
ExtPred edge: (Node, Node).
[
    in_clique(X)? :- node(X).
    (\neg (\exists X, Y. (\and
        in_clique(X)
        in_clique(Y)
        (!= X Y)
        (\neg edge(X, Y))
    ))).
]
"""
    program = Parser().parse(source)
    with contextlib.redirect_stdout(io.StringIO()):
        rewritten = Rewriter().rewrite_program(program, convert_only=False)

    asp = transpile_program_to_asp(rewritten, grounding=True)

    assert "not edge(X, Y)" in asp
    assert "#count{X : in_clique(X)} > 1" not in asp
