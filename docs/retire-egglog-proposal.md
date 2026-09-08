# Proposal: retire the egglog front half

Status: proposal, 2026-09-08, branch `direct-lowering`. Nothing here has been
performed; the egglog path is still the default and untouched.

## What the data says

`docs/track-b-results.md` has the measurements. In short: with
`--lowering direct` every runner of the regression suite reproduces the
same verdict counts as the egglog path, the three concurrency models
compile in under a second, the PORTUS sample compiles whole in seconds
per command, and per-query compile time on DuoAI and mypyvy drops from
about 5 to 6 s to about 1 s (most of the remainder is Python start-up,
Lark's grammar build and Clingo). The direct lowering also compiles every
shape the egglog path left raw or emitted wrongly (B2's ite-valued frame
equality and or-of-and shapes, B11, B12, the recursion-depth datapoint),
and the differential between the two front halves found a wrong-code
defect in the shared back half (B10) that neither would have shown alone.

The defect record (`docs/known-issues.md`) is the other half of the
argument. Of B1 to B12, every defect in the front half (B1, B2, B5, B7,
B8, B11, B12) is in the plumbing around egglog, not in the meaning of its
rules: the printed-term round trip, the budgeted and throttled schedule,
the extraction cost ties, the recursion cap. The rules themselves are
textbook normalisation, which is what the direct lowering does by
construction, in 700 lines against 3,500.

## What retiring means, concretely

1. Make `direct` the default of `--lowering`; keep `egglog` selectable for
   one release so the study can re-run any comparison.
2. Move the corpus runners' expected counts to the direct path (they are
   equal today, so this is a relabelling).
3. Delete, in a second step and only after that release: `rewrite/rw.py`,
   `egg_rules.py`, `egg_schema.py`, the egglog half of `converter.py`
   (its Let desugaring already lives in `lowering/desugar.py`),
   `transpile/egg_parsing.py`, `transpile/aux.py`, `transpile/normalize.py`,
   the string half of `transpile/pipeline.py` (`transpile_block_expr_to_asp`,
   `PrintedBlock`) and the tests that build egglog terms directly
   (`test_egg_*.py`, `test_converter.py`, `test_let_expr.py` for the
   `Constraint(Vec[LetExpr]...)` path). About 3,500 lines. `egglog` leaves
   `pyproject.toml`'s dependencies; the install shrinks and the import
   drops 0.4 s.
4. What the direct lowering does not do that egglog did: general `Let`
   expressions other than `Let ... in \subset` (the egglog path passed them
   to the transpiler as `LetExpr` rules; no corpus model uses them), and
   `Formula.Belonging` / `Formula.Subset` without a `Let` (raw in both).
   Add those to the direct lowering before step 3 if the language keeps
   them; `test_let_expr.py` is the specification.

## What to decide first

- Whether equality saturation is a claimed contribution of the paper. If
  it is, the comparison in `docs/track-b-results.md` is the data for the
  claim either way, and the egglog path should stay as the artifact of
  that claim rather than be deleted. If it is an implementation choice,
  step 1 can happen now.
- The empty-domain semantics. The egglog quantifier elimination kept
  cubes for empty sorts (`not dom_S(_)`); the direct lowering assumes
  non-empty sorts. No corpus instance has an empty sort, and the
  differential agrees on every model, but the paper's semantics should
  say which it is.

## What stays regardless

The back half (`constraint.py`, `merge.py`, `transpile/rewrite.py`,
`safety.py`, `rendering.py`, the IR in `ir.py`), the parser and the
checker. B4, B6 and B9 live there or outside the compiler and are
unchanged by this proposal.
