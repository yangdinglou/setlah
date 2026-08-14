import unittest

try:
    from egglog import EGraph, run, back_off
except ImportError:  # pragma: no cover
    EGraph = None  # type: ignore[assignment]
    run = None  # type: ignore[assignment]
    back_off = None  # type: ignore[assignment]

from setlah.rewrite.egg_schema import Atom, Constraint, Formula, GeneralLit, Literal, Term
from setlah.rewrite.egg_rules import equal_set, extraction, term_set


class TestEggForallImplIntegrity(unittest.TestCase):
    def test_forall_impl_is_equiv_to_integrity_constraint(self):
        if EGraph is None:
            raise unittest.SkipTest("egglog not installed; run tests in the `setla` environment")
        # forall R,C,V. ( initial(R,C,V) -> sudoku(R,C,V) )
        R = Term.Var("R")
        C = Term.Var("C")
        V = Term.Var("V")
        args = [R, C, V]

        initial = Formula.Lit(GeneralLit.from_literal(Literal(Atom.Pred("initial", args), True)))
        sudoku_pos = Formula.Lit(GeneralLit.from_literal(Literal(Atom.Pred("sudoku", args), True)))

        lhs = Constraint(
            lets=[],
            body=Formula.Forall(R, Formula.Forall(C, Formula.Forall(V, Formula.Implies(initial, sudoku_pos)))),
        )

        rhs = Constraint.integrity_constraints(
            vars={R, C, V},
            formulas={
                GeneralLit.from_literal(Literal(Atom.Pred("initial", args), True)),
                GeneralLit.from_literal(Literal(Atom.Pred("sudoku", args), False)),
            },
        )

        egraph = EGraph()
        egraph.register(lhs)
        egraph.register(rhs)

        # Avoid unbounded saturation: match the bounded schedule used by Rewriter.
        sched = (
            run(term_set).saturate()
            + run(equal_set, scheduler=back_off()) * 25
            + run(extraction, scheduler=back_off()) * 20
        )
        egraph.run(sched)

        ok = egraph.check_bool(lhs == rhs)
        if not ok:
            extracted_lhs = egraph.extract(lhs)
            extracted_rhs = egraph.extract(rhs)
            raise AssertionError(
                "Expected egraph equivalence but check_bool was false.\n"
                f"LHS extracted: {extracted_lhs}\n"
                f"RHS extracted: {extracted_rhs}\n"
            )


if __name__ == "__main__":
    unittest.main()
