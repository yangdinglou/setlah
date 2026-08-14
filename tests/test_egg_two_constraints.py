"""
Test whether egglog can rewrite two splittable constraints into split form.
This isolates the rewriting problem from extraction/scheduling issues.
"""

from egglog import EGraph, ruleset, rewrite, var
from setlah.rewrite.egg_schema import Term, Atom, Literal, Formula, GeneralLit, Constraint, Block, Rule
from setlah.rewrite.egg_rules import *

def test_two_splittable_constraints():
    """
    Test: Can egglog rewrite:
        cons_constraint(
            Constraint(And(p(X), q(X))),
            cons_constraint(
                Constraint(And(r(X), s(X))),
                nil_constraint()
            )
        )
    
    Into an equivalent form with both constraints split?
    """
    
    egraph = EGraph()
    
    # Build atoms
    atom_p = Atom.Pred("p", [Term.Var("X")])
    atom_q = Atom.Pred("q", [Term.Var("X")])
    atom_r = Atom.Pred("r", [Term.Var("X")])
    atom_s = Atom.Pred("s", [Term.Var("X")])
    
    # Build literals
    lit_p = GeneralLit.from_literal(Literal(atom_p, True))
    lit_q = GeneralLit.from_literal(Literal(atom_q, True))
    lit_r = GeneralLit.from_literal(Literal(atom_r, True))
    lit_s = GeneralLit.from_literal(Literal(atom_s, True))
    
    # Build formula: And(p, q)
    formula_constraint1 = Formula.And(Formula.Lit(lit_p), Formula.Lit(lit_q))
    
    # Build formula: And(r, s)
    formula_constraint2 = Formula.And(Formula.Lit(lit_r), Formula.Lit(lit_s))
    
    # Build constraints
    constraint1 = Constraint([], formula_constraint1)
    constraint2 = Constraint([], formula_constraint2)
    
    # Build LHS cons_constraint list (two AND constraints)
    from setlah.rewrite.egg_schema import cons_constraint, nil_constraint
    lhs = cons_constraint(constraint1, cons_constraint(constraint2, nil_constraint()))
    
    print("LHS (two AND constraints as single items):")
    print(lhs)
    print()
    
    # Also register the raw ConsLists, to show that list-level equality does NOT hold
    # (because the split rule is written over `Block`, not over `ConsList`).
    egraph.register(lhs)

    # Wrap in a Block so block-level conjunction splitting rules can apply
    lhs_block = Block(Set[Rule](), lhs)

    # Register in egraph
    egraph.register(lhs_block)

    # Build RHS: split each AND into two separate constraints
    c11 = Constraint([], Formula.Lit(lit_p))
    c12 = Constraint([], Formula.Lit(lit_q))
    c21 = Constraint([], Formula.Lit(lit_r))
    c22 = Constraint([], Formula.Lit(lit_s))

    rhs = cons_constraint(c11, cons_constraint(c12, cons_constraint(c21, cons_constraint(c22, nil_constraint()))))
    egraph.register(rhs)
    rhs_block = Block(Set[Rule](), rhs)
    egraph.register(rhs_block)

    # Witness blocks: split only the first constraint, or only the second.
    rhs_split_first = cons_constraint(
        c11,
        cons_constraint(c12, cons_constraint(constraint2, nil_constraint())),
    )
    rhs_split_first_block = Block(Set[Rule](), rhs_split_first)
    egraph.register(rhs_split_first_block)

    rhs_split_second = cons_constraint(
        constraint1,
        cons_constraint(c21, cons_constraint(c22, nil_constraint())),
    )
    rhs_split_second_block = Block(Set[Rule](), rhs_split_second)
    egraph.register(rhs_split_second_block)

    print("RHS (each conjunction split into two constraints):")
    print(rhs)
    print()
    
    # Run all rules
    eq_rules = equal_set
    extraction_rules = extraction
    
    base_rules = (
        run(term_set).saturate()
        + run(eq_rules, scheduler=back_off()) * 25
        + run(extraction_rules, scheduler=back_off()) * 25
    )
    
    print("Running rewrite rules...")
    egraph.run(base_rules)
    print("Done.")
    print()

    # Show the key distinction explicitly:
    # - list-level equality is false (no list-level split rule)
    # - block-level equality is true (because `conjunction_split` rewrites Blocks)
    list_eq = egraph.check_bool(lhs == rhs)
    print("check_bool(lhs == rhs) [ConsList level]:", list_eq)
    
    # Witness checks: do we at least split one conjunction?
    split_first_ok = egraph.check_bool(lhs_block == rhs_split_first_block)
    split_second_ok = egraph.check_bool(lhs_block == rhs_split_second_block)
    print("check_bool(lhs_block == rhs_split_first_block):", split_first_ok)
    print("check_bool(lhs_block == rhs_split_second_block):", split_second_ok)

    # Full split check (often depends on re-ordering after the first split)
    full_before = egraph.check_bool(lhs_block == rhs_block)
    print("check_bool(lhs_block == rhs_block) [before extra term_set]:", full_before)

    # IMPORTANT: term_set contains the ConsList commutativity/idempotency rules.
    # In the base schedule we only saturate term_set *before* extraction.
    # Re-saturate term_set now so newly-created ConsList shapes can be reordered.
    egraph.run(run(term_set).saturate())
    full_after = egraph.check_bool(lhs_block == rhs_block)
    print("check_bool(lhs_block == rhs_block) [after extra term_set]:", full_after)

    # --- Extraction check ---
    # Now that we know lhs_block == rhs_block in the e-graph, check what the extractor
    # *chooses* as the best representative for each.
    best_lhs, cost_lhs = egraph.extract(lhs_block, include_cost=True)
    best_rhs, cost_rhs = egraph.extract(rhs_block, include_cost=True)
    print()
    print("Best extracted LHS block (expr, cost):")
    print(best_lhs)
    print(cost_lhs)
    print()
    print("Best extracted RHS block (expr, cost):")
    print(best_rhs)
    print(cost_rhs)

    # Does extraction pick something equivalent to the fully split RHS block?
    # (This is about the *chosen* representative, not about the e-class equality.)
    extracted_equals_split = egraph.check_bool(best_lhs == rhs_block)
    print()
    print("check_bool(extract(lhs_block).expr == rhs_block):", extracted_equals_split)

    return full_after

if __name__ == "__main__":
    test_two_splittable_constraints()
