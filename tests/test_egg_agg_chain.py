"""
Test to trace the aggregate synthesis chain in egg.

We want to verify each step of:
∃H. (A ∧ B) 
  → grouped_exists({H}, grouped_and_lit({A, B}))
  → grouped_exists({H}, grouped_dnf([grouped_and_lit({A, B})]))
  → #count{H : A, B} != 0
"""

from egglog import EGraph, Vec, Set

from setlah.rewrite.egg_schema import (
    Atom, Formula, Literal, Term, GeneralLit, AggBody,
    cons_var, nil_var
)
from setlah.rewrite.egg_rules import equal_set, extraction, term_set


def _run(egraph: EGraph, ruleset, *, iters: int = 10) -> None:
    for _ in range(iters):
        egraph.run(ruleset.saturate())


def test_exists_to_grouped_exists():
    """
    Check: ∃H. (color(H, green) ∧ color(H+1, white)) 
           == grouped_exists({H}, ...)
    """
    h = Term.Var("H")
    green = Term.Symbol("green")
    white = Term.Symbol("white")
    h_plus_1 = Term.BinaryExpr("+", h, Term.Int(1))
    
    # Atoms
    color_h_green_atom = Atom.Pred("color", [h, green])
    color_hplus1_white_atom = Atom.Pred("color", [h_plus_1, white])
    
    # Literals
    lit_a = Literal(color_h_green_atom, True)
    lit_b = Literal(color_hplus1_white_atom, True)
    
    # Formula form: ∃H. (color(H, green) ∧ color(H+1, white))
    formula_a = Formula.Lit(GeneralLit.from_literal(lit_a))
    formula_b = Formula.Lit(GeneralLit.from_literal(lit_b))
    exists_and = Formula.Exists(h, Formula.And(formula_a, formula_b))
    
    # Grouped form: grouped_exists({H}, grouped_and_lit({A, B}))
    grouped_and_ab = Formula.grouped_and_lit(Set[Literal](lit_a, lit_b))
    grouped_exists_form = Formula.grouped_exists(Set[Term](h), grouped_and_ab)
    
    egraph = EGraph()
    egraph.register(exists_and)
    egraph.register(grouped_exists_form)
    
    _run(egraph, term_set, iters=20)
    _run(egraph, equal_set, iters=20)
    _run(egraph, extraction, iters=20)
    
    print("Checking: ∃H.(A ∧ B) == grouped_exists({H}, grouped_and_lit({A, B}))")
    try:
        egraph.check(exists_and == grouped_exists_form)
        print("  ✓ They ARE equal in the egraph")
        return True
    except:
        print("  ✗ They are NOT equal in the egraph")
        return False


def test_grouped_and_lit_to_grouped_dnf():
    """
    Check: grouped_and_lit({A, B}) == grouped_dnf([grouped_and_lit({A, B})])
    """
    h = Term.Var("H")
    green = Term.Symbol("green")
    white = Term.Symbol("white")
    h_plus_1 = Term.BinaryExpr("+", h, Term.Int(1))
    
    lit_a = Literal(Atom.Pred("color", [h, green]), True)
    lit_b = Literal(Atom.Pred("color", [h_plus_1, white]), True)
    
    # grouped_and_lit({A, B})
    grouped_and_ab = Formula.grouped_and_lit(Set[Literal](lit_a, lit_b))
    
    # grouped_dnf([grouped_and_lit({A, B})])
    grouped_dnf_form = Formula.grouped_dnf(Vec[Formula](grouped_and_ab))
    
    egraph = EGraph()
    egraph.register(grouped_and_ab)
    egraph.register(grouped_dnf_form)
    
    _run(egraph, extraction, iters=20)
    
    print("Checking: grouped_and_lit({A, B}) == grouped_dnf([grouped_and_lit({A, B})])")
    try:
        egraph.check(grouped_and_ab == grouped_dnf_form)
        print("  ✓ They ARE equal in the egraph")
        return True
    except:
        print("  ✗ They are NOT equal in the egraph")
        return False


def test_grouped_exists_dnf_to_count():
    """
    Check: grouped_exists({H}, grouped_dnf([cube])) == #count{H : cube} != 0
    """
    h = Term.Var("H")
    green = Term.Symbol("green")
    white = Term.Symbol("white")
    h_plus_1 = Term.BinaryExpr("+", h, Term.Int(1))
    
    lit_a = Literal(Atom.Pred("color", [h, green]), True)
    lit_b = Literal(Atom.Pred("color", [h_plus_1, white]), True)
    
    # The cube: grouped_and_lit({A, B})
    cube = Formula.grouped_and_lit(Set[Literal](lit_a, lit_b))
    
    # grouped_exists({H}, grouped_dnf([cube]))
    grouped_exists_dnf = Formula.grouped_exists(
        Set[Term](h),
        Formula.grouped_dnf(Vec[Formula](cube))
    )
    
    # Expected: #count{H : A, B} != 0
    count_agg = Formula.Lit(GeneralLit.general_agg(
        "count",
        AggBody.set_comprehension(Set[Term](h), Vec[Formula](cube)),
        "!=",
        Term.Int(0)
    ))
    
    egraph = EGraph()
    egraph.register(grouped_exists_dnf)
    egraph.register(count_agg)
    
    _run(egraph, extraction, iters=20)
    
    print("Checking: grouped_exists({H}, grouped_dnf([cube])) == #count{H : cube} != 0")
    try:
        egraph.check(grouped_exists_dnf == count_agg)
        print("  ✓ They ARE equal in the egraph")
        return True
    except:
        print("  ✗ They are NOT equal in the egraph")
        return False


def test_full_chain():
    """
    Check the full chain:
    ∃H. (A ∧ B) == #count{H : A, B} != 0
    """
    h = Term.Var("H")
    green = Term.Symbol("green")
    white = Term.Symbol("white")
    h_plus_1 = Term.BinaryExpr("+", h, Term.Int(1))
    
    lit_a = Literal(Atom.Pred("color", [h, green]), True)
    lit_b = Literal(Atom.Pred("color", [h_plus_1, white]), True)
    
    # Original: ∃H. (A ∧ B)
    formula_a = Formula.Lit(GeneralLit.from_literal(lit_a))
    formula_b = Formula.Lit(GeneralLit.from_literal(lit_b))
    exists_and = Formula.Exists(h, Formula.And(formula_a, formula_b))
    
    # The cube for aggregate
    cube = Formula.grouped_and_lit(Set[Literal](lit_a, lit_b))
    
    # Target: #count{H : A, B} != 0
    count_agg = Formula.Lit(GeneralLit.general_agg(
        "count",
        AggBody.set_comprehension(Set[Term](h), Vec[Formula](cube)),
        "!=",
        Term.Int(0)
    ))
    
    egraph = EGraph()
    egraph.register(exists_and)
    egraph.register(count_agg)
    
    _run(egraph, term_set, iters=30)
    _run(egraph, equal_set, iters=30)
    _run(egraph, extraction, iters=30)
    
    print("Checking: ∃H.(A ∧ B) == #count{H : A, B} != 0")
    try:
        egraph.check(exists_and == count_agg)
        print("  ✓ They ARE equal in the egraph - FULL CHAIN WORKS!")
        return True
    except:
        print("  ✗ They are NOT equal in the egraph - chain is broken somewhere")
        return False


def test_count_agg_to_integrity_constraint():
    """
    Check: Constraint([], #count{H : A, B} != 0) 
           can be converted to some integrity constraint form
           
    For a positive existential, we want ∃H.(A ∧ B) to hold.
    Violation is when ¬∃H.(A ∧ B) = #count{...} == 0
    
    So the constraint should become:
    :- #count{H : A, B} == 0.
    """
    from setlah.rewrite.egg_schema import Constraint, LetExpr
    from egglog import Vec
    
    h = Term.Var("H")
    green = Term.Symbol("green")
    white = Term.Symbol("white")
    h_plus_1 = Term.BinaryExpr("+", h, Term.Int(1))
    
    lit_a = Literal(Atom.Pred("color", [h, green]), True)
    lit_b = Literal(Atom.Pred("color", [h_plus_1, white]), True)
    
    cube = Formula.grouped_and_lit(Set[Literal](lit_a, lit_b))
    
    # #count{H : A, B} != 0  (the exists formula)
    count_ne_0 = Formula.Lit(GeneralLit.general_agg(
        "count",
        AggBody.set_comprehension(Set[Term](h), Vec[Formula](cube)),
        "!=",
        Term.Int(0)
    ))
    
    # #count{H : A, B} == 0  (the negated form for violation)
    count_eq_0 = Formula.Lit(GeneralLit.general_agg(
        "count",
        AggBody.set_comprehension(Set[Term](h), Vec[Formula](cube)),
        "==",
        Term.Int(0)
    ))
    
    # Constraint with the positive existential (we want this to hold)
    constraint_exists = Constraint(Vec[LetExpr](), count_ne_0)
    
    # Check if Not(count != 0) == count == 0
    not_count_ne_0 = Formula.Not(count_ne_0)
    
    egraph = EGraph()
    egraph.register(not_count_ne_0)
    egraph.register(count_eq_0)
    
    _run(egraph, extraction, iters=20)
    
    print("Checking: Not(#count{...} != 0) == #count{...} == 0")
    try:
        egraph.check(not_count_ne_0 == count_eq_0)
        print("  ✓ They ARE equal - negation of aggregate works")
        return True
    except:
        print("  ✗ They are NOT equal - aggregate negation broken")
        return False


def test_constraint_with_exists_to_integrity():
    """
    Check: Constraint([], ∃H.(A ∧ B)) 
           should eventually become an integrity constraint with aggregate
    """
    from setlah.rewrite.egg_schema import Constraint, LetExpr
    from egglog import Vec
    
    h = Term.Var("H")
    green = Term.Symbol("green")
    white = Term.Symbol("white")
    h_plus_1 = Term.BinaryExpr("+", h, Term.Int(1))
    
    lit_a = Literal(Atom.Pred("color", [h, green]), True)
    lit_b = Literal(Atom.Pred("color", [h_plus_1, white]), True)
    
    # Original: ∃H. (A ∧ B)
    formula_a = Formula.Lit(GeneralLit.from_literal(lit_a))
    formula_b = Formula.Lit(GeneralLit.from_literal(lit_b))
    exists_and = Formula.Exists(h, Formula.And(formula_a, formula_b))
    
    # As a constraint
    constraint = Constraint(Vec[LetExpr](), exists_and)
    
    # The cube for aggregate
    cube = Formula.grouped_and_lit(Set[Literal](lit_a, lit_b))
    
    # Expected constraint with aggregate: Constraint([], #count{...} != 0)
    count_ne_0 = Formula.Lit(GeneralLit.general_agg(
        "count",
        AggBody.set_comprehension(Set[Term](h), Vec[Formula](cube)),
        "!=",
        Term.Int(0)
    ))
    expected_constraint = Constraint(Vec[LetExpr](), count_ne_0)
    
    egraph = EGraph()
    egraph.register(constraint)
    egraph.register(expected_constraint)
    
    _run(egraph, term_set, iters=30)
    _run(egraph, equal_set, iters=30)
    _run(egraph, extraction, iters=30)
    
    print("Checking: Constraint([], ∃H.(A ∧ B)) == Constraint([], #count{...} != 0)")
    try:
        egraph.check(constraint == expected_constraint)
        print("  ✓ They ARE equal - constraint with exists becomes aggregate constraint")
        return True
    except:
        print("  ✗ They are NOT equal - constraint not converted to aggregate form")
        return False


def test_what_gets_extracted():
    """
    Check what actually gets EXTRACTED from the egraph.
    The formulas may be equal, but extraction picks the lowest cost.
    """
    from setlah.rewrite.egg_schema import Constraint, LetExpr
    from egglog import Vec
    
    h = Term.Var("H")
    green = Term.Symbol("green")
    white = Term.Symbol("white")
    h_plus_1 = Term.BinaryExpr("+", h, Term.Int(1))
    
    lit_a = Literal(Atom.Pred("color", [h, green]), True)
    lit_b = Literal(Atom.Pred("color", [h_plus_1, white]), True)
    
    # Original: ∃H. (A ∧ B)
    formula_a = Formula.Lit(GeneralLit.from_literal(lit_a))
    formula_b = Formula.Lit(GeneralLit.from_literal(lit_b))
    exists_and = Formula.Exists(h, Formula.And(formula_a, formula_b))
    
    # As a constraint
    constraint = Constraint(Vec[LetExpr](), exists_and)
    
    egraph = EGraph()
    egraph.register(constraint)
    
    _run(egraph, term_set, iters=30)
    _run(egraph, equal_set, iters=30)
    _run(egraph, extraction, iters=30)
    
    # Extract the constraint - what form does it take?
    extracted = egraph.extract(constraint)
    print(f"EXTRACTED CONSTRAINT:")
    print(f"  {extracted}")
    
    # Also extract just the formula
    extracted_formula = egraph.extract(exists_and)
    print(f"EXTRACTED FORMULA:")
    print(f"  {extracted_formula}")
    
    # Check if it's the aggregate form or original form
    extracted_str = str(extracted)
    if "general_agg" in extracted_str or "#count" in extracted_str:
        print("  → Extracted as AGGREGATE form ✓")
        return True
    elif "Exists" in extracted_str or "grouped_exists" in extracted_str:
        print("  → Extracted as EXISTS form (not aggregate)")
        return False
    else:
        print(f"  → Unknown form: {extracted_str[:100]}...")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Step 1: ∃H.(A ∧ B) → grouped_exists({H}, grouped_and_lit({A, B}))")
    print("=" * 70)
    step1 = test_exists_to_grouped_exists()
    
    print()
    print("=" * 70)
    print("Step 2: grouped_and_lit → grouped_dnf([grouped_and_lit])")
    print("=" * 70)
    step2 = test_grouped_and_lit_to_grouped_dnf()
    
    print()
    print("=" * 70)
    print("Step 3: grouped_exists(grouped_dnf) → count aggregate")
    print("=" * 70)
    step3 = test_grouped_exists_dnf_to_count()
    
    print()
    print("=" * 70)
    print("Full chain: ∃H.(A ∧ B) → #count{H : A, B} != 0")
    print("=" * 70)
    step4 = test_full_chain()
    
    print()
    print("=" * 70)
    print("Aggregate negation: Not(#count != 0) → #count == 0")
    print("=" * 70)
    step5 = test_count_agg_to_integrity_constraint()
    
    print()
    print("=" * 70)
    print("Constraint chain: Constraint(∃H.(A∧B)) → Constraint(#count!=0)")
    print("=" * 70)
    step6 = test_constraint_with_exists_to_integrity()
    
    print()
    print("=" * 70)
    print("What gets EXTRACTED (cost-based selection)")
    print("=" * 70)
    step7 = test_what_gets_extracted()
    
    print()
    print("=" * 70)
    print("SUMMARY:")
    print(f"  Step 1 (exists → grouped_exists): {'✓' if step1 else '✗'}")
    print(f"  Step 2 (grouped_and_lit → grouped_dnf): {'✓' if step2 else '✗'}")
    print(f"  Step 3 (grouped_exists+dnf → count): {'✓' if step3 else '✗'}")
    print(f"  Full chain: {'✓' if step4 else '✗'}")
    print(f"  Aggregate negation: {'✓' if step5 else '✗'}")
    print(f"  Constraint with exists → aggregate: {'✓' if step6 else '✗'}")
    print(f"  Extraction picks aggregate: {'✓' if step7 else '✗'}")
    print("=" * 70)
