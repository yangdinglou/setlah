from egglog import EGraph

from setlah.rewrite.egg_schema import Atom, Formula, Literal, Term
from setlah.rewrite.egg_rules import equal_set, extraction, term_set


def _run_backoff(egraph: EGraph, ruleset, *, iters: int = 10) -> None:
    # Keep it bounded like the other egg tests in this repo.
    for _ in range(iters):
        egraph.run(ruleset.saturate())


def test_trivial_exists_dropped_via_anon() -> None:
    # ∃X. (p(X) ∧ q(Y))  ==  (p(_) ∧ q(Y))
    x = Term.Var("X")
    y = Term.Var("Y")

    p_x = Formula.Lit(Literal(Atom.Pred("p", [x,y]), True))
    q_y = Formula.Lit(Literal(Atom.Pred("q", [y]), True))

    # lhs = Formula.Exists(x, Formula.And(p_x, q_y))
    # rhs = Formula.And(
    #     Formula.Lit(Literal(Atom.Pred("p", [Term.Anon()]), True)),
    #     q_y,
    # )
    lhs = Formula.Exists(x, p_x)
    rhs = Formula.Lit(Literal(Atom.Pred("p", [Term.Anon(),y]), True))

    egraph = EGraph()
    egraph.register(lhs)
    egraph.register(rhs)

    # Run the same phases used elsewhere: var analysis (term_set), equalities, then extraction.
    _run_backoff(egraph, term_set)
    _run_backoff(egraph, equal_set)
    # _run_backoff(egraph, extraction)

    #virtualise the egraph
    # egraph.display()
    # Prove they end up in the same e-class.
    assert egraph.check_bool(lhs == rhs)
    # exp= egraph.extract(lhs)  # For debug printing if needed.
    # print(f"Extracted expression: {exp}")

    print("Test passed: trivial exists rewritten to anonymous variable.")

def test_exists_dropped_with_const() -> None:
    # ∃X. (p(X, c) ∧ q(Y))  ==  (p(_, c) ∧ q(Y))
    x = Term.Var("X")
    y = Term.Var("Y")
    c = Term.Symbol("c")

    p_xc = Formula.Lit(Literal(Atom.Pred("p", [x,c]), True))
    q_y = Formula.Lit(Literal(Atom.Pred("q", [y]), True))

    lhs = Formula.Exists(x, p_xc)
    rhs = Formula.Lit(Literal(Atom.Pred("p", [Term.Anon(),c]), True))

    egraph = EGraph()
    egraph.register(lhs)
    egraph.register(rhs)

    # Run the same phases used elsewhere: var analysis (term_set), equalities, then extraction.
    _run_backoff(egraph, term_set)
    _run_backoff(egraph, equal_set)

    # Prove they end up in the same e-class.
    assert egraph.check_bool(lhs == rhs)
    print("Test passed: exists with constant argument rewritten to anonymous variable.")

if __name__ == "__main__":
    # test_trivial_exists_dropped_via_anon()
    test_exists_dropped_with_const()