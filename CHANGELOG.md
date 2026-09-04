# Changelog

All notable changes to SetLaH will be documented in this file.

## [Unreleased]

### Fixed

- Lower auxiliary-predicate calls that the rewriter's recursive pass leaves in
  place, instead of failing with `Expected Literal(atom, sign), got
  Literal.AuxCall(...)`. The cause was in `Rewriter._normalize_cons_list_str`:
  egglog's let-style bindings were read either by splitting the prefix on
  top-level commas (its multi-line layout has none) or with a pattern anchored
  to the start of a line (which misses the first binding, printed after the
  tuple's `(`, and every indented one), so one binding's value swallowed the
  text of the next and substituting it spliced a binding definition into the
  middle of the expression; the corrupted expression then no longer parsed, the
  auxiliary call was never lowered, and the transpiler raised on it. Bindings
  are now extracted by a parenthesis-depth-aware scan
  (`Rewriter._parse_binding_prefix`) that accepts both layouts, and
  `transpile/aux.py` lowers a two-argument `Literal.AuxCall` if one still
  reaches it. On the DuoAI `client_server_db_ae` corpus (142 distinct
  invariant-checking queries) this takes automatic compilation from 30
  answers and 112 failures to 142 answers and no failures, each agreeing with
  Z3; on mypyvy's 792 `updr` queries, from 169 answers and 623 failures to
  792 answers and none. See `docs/known-issues.md` (B1).
- Guard head variables of generated auxiliary rules that the rule's own body
  does not bind, so Clingo accepts the program. An auxiliary predicate takes
  the free variables of the whole disjunction it replaces, so the rule for a
  disjunct that does not mention one of them had an unsafe head variable and
  Clingo refused to ground the program, while the compiler exited 0. Safety
  guards were inferred from rule bodies alone; `_infer_safety_guards` now also
  takes the head, and `_extract_aux_pred_types` merges an auxiliary
  predicate's signature across its rules so the variable's domain is known
  from the sibling rule that does bind it. See `docs/known-issues.md` (B3).

### Added

- `docs/known-issues.md`: compiler defects found by compiling third-party
  finite-domain problems (DuoAI and mypyvy verification queries, Alloy commands
  translated by PORTUS), each with a minimal reproducer under
  `tests/inputs/regressions/`.
- `tests/test_regressions_known_issues.py`: regression tests for those
  reproducers and for the binding-prefix parser.

## [0.1.0rc1] - Unreleased

Initial public prerelease of the SetLaH compiler and command-line interface.

- Package the implementation as `setlah` with a `setlah` console command.
- Add tested compilation and solving examples.
- Add Clingo AST execution through `ProgramBuilder`.
- Add safety guards inferred through arithmetic comparisons.
- Preserve variables in negated predicates when detecting uniqueness patterns.
- Constrain runtime dependencies to the tested egglog and Clingo versions.
- Declare cloudpickle explicitly because egglog 12 imports it at runtime.
- Add runnable fact instances and an end-to-end check for every Maple-set model.
