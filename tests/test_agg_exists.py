import contextlib
import io

from setlah.parsing.parser import Parser
from setlah.rewrite.rw import Rewriter


def run_rewriter(program_text: str):
    p = Parser()
    ast = p.parse(program_text)
    rw = Rewriter()
    with contextlib.redirect_stdout(io.StringIO()):
        return rw.rewrite_program(ast, convert_only=False)


def test_exists_single_var_or_disjunction():
    # \exists X. (p(X) \or q(X))  — single variable, rewriter uses negated literals
    program = r"""
ExtDOM D: INT.
ExtPred p: (D).
ExtPred q: (D).
[
    (\exists X. (\or p(X) q(X))).
]
"""
    out = run_rewriter(program)
    s = str(out)
    # Rewriter produces integrity constraint with negated p and q literals
    assert '"p"' in s and '"q"' in s and "False" in s, s


def test_exists_two_vars_or_disjunction():
    # \exists X, Y. (cube1(X,Y) \or cube2(X,Y))  — two vars, rewriter uses count aggregate
    program = r"""
ExtDOM D: INT.
ExtPred cube1: (D,D).
ExtPred cube2: (D,D).
[
    (\exists X, Y. (\or cube1(X, Y) cube2(X, Y))).
]
"""
    out = run_rewriter(program)
    s = str(out)
    # Rewriter produces #count == 0 integrity constraint (denial form)
    assert "general_agg" in s and "count" in s and '==' in s, s


if __name__ == "__main__":
    test_exists_single_var_or_disjunction()
    test_exists_two_vars_or_disjunction()
    print("Exists->constraint tests passed.")
