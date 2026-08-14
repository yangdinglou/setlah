import unittest


try:
    # Import the module (it imports clingo). This may only be available in the `setla` env.
    from setlah.transpile.pipeline import transpile_block_expr_to_asp
except Exception:  # pragma: no cover
    transpile_block_expr_to_asp = None  # type: ignore[assignment]


class TestTranspilerPostProcessing(unittest.TestCase):
    def test_existence_compiles_to_count_eq_0(self):
        if transpile_block_expr_to_asp is None:
            raise unittest.SkipTest("transpiler unavailable; run tests in the `setla` environment")

        # This represents the denial of: forall R,C. exists V. sudoku(R,C,V)
        # i.e. exists R,C. #count{V : sudoku(R,C,V)} = 0
        block = """
Block(
  Set[Rule](),
  cons_constraint(
    Constraint.integrity_constraints(
      Set[Term](Term.Var('R'), Term.Var('C'), Term.Var('V')),
      Set[GeneralLit](
        GeneralLit.from_literal(Literal(Atom.Pred('dom_Index', [Term.Var('R')]), True)),
        GeneralLit.from_literal(Literal(Atom.Pred('dom_Index', [Term.Var('C')]), True)),
        GeneralLit.general_agg(
          'count',
          AggBody.set_comprehension(
            Set[Term](Term.Var('V')),
            Vec[Formula](
              Formula.Lit(GeneralLit.from_literal(Literal(Atom.Pred('sudoku', [Term.Var('R'), Term.Var('C'), Term.Var('V')]), True)))
            )
          ),
          '==',
          Term.Int(0)
        )
      )
    ),
    nil_constraint()
  )
)
""".strip()

        asp = transpile_block_expr_to_asp(
            block,
            entailment_specs=None,
            pred_arg_types={"sudoku": ("Index", "Index", "Index")},
            grounding=False,
        )

        self.assertIn("#count{V : sudoku(R, C, V)} = 0", asp)

    def test_uniqueness_rewrites_to_count_gt_1_when_core_present(self):
        if transpile_block_expr_to_asp is None:
            raise unittest.SkipTest("transpiler unavailable; run tests in the `setla` environment")

        # Two constraints in one block:
        #  (A) existence violation with #count{V:sudoku(R,C,V)}=0  => provides a mergeable core
        #  (B) uniqueness violation with V1!=V2 => should be rewritten to #count{V1:sudoku(R,C,V1)} > 1
        block = """
Block(
  Set[Rule](),
  cons_constraint(
    Constraint.integrity_constraints(
      Set[Term](Term.Var('R'), Term.Var('C'), Term.Var('V')),
      Set[GeneralLit](
        GeneralLit.from_literal(Literal(Atom.Pred('dom_Index', [Term.Var('R')]), True)),
        GeneralLit.from_literal(Literal(Atom.Pred('dom_Index', [Term.Var('C')]), True)),
        GeneralLit.general_agg(
          'count',
          AggBody.set_comprehension(
            Set[Term](Term.Var('V')),
            Vec[Formula](
              Formula.Lit(GeneralLit.from_literal(Literal(Atom.Pred('sudoku', [Term.Var('R'), Term.Var('C'), Term.Var('V')]), True)))
            )
          ),
          '==',
          Term.Int(0)
        )
      )
    ),
    cons_constraint(
      Constraint.integrity_constraints(
        Set[Term](Term.Var('R'), Term.Var('C'), Term.Var('V1'), Term.Var('V2')),
        Set[GeneralLit](
          GeneralLit.from_literal(Literal(Atom.Pred('sudoku', [Term.Var('R'), Term.Var('C'), Term.Var('V1')]), True)),
          GeneralLit.from_literal(Literal(Atom.Pred('sudoku', [Term.Var('R'), Term.Var('C'), Term.Var('V2')]), True)),
          GeneralLit.from_literal(Literal(Atom.Comp('!=', Term.Var('V1'), Term.Var('V2')), True))
        )
      ),
      nil_constraint()
    )
  )
)
""".strip()

        asp = transpile_block_expr_to_asp(
            block,
            entailment_specs=None,
            pred_arg_types={"sudoku": ("Index", "Index", "Index")},
            grounding=True,
        )

        # Existence constraint should still be present.
        self.assertIn("#count{V : sudoku(R, C, V)} = 0", asp)

        # Uniqueness should be rewritten to count > 1 (and must NOT become = 0).
        self.assertIn("#count{V1 : sudoku(R, C, V1)} > 1", asp)
        self.assertNotIn("#count{V1 : sudoku(R, C, V1)} = 0", asp)


if __name__ == "__main__":
    unittest.main()
