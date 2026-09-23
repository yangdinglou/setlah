# Changelog

## Unreleased (branch order-sorts)

- Difference-logic extension: reified comparison Booleans are guarded by the
  cube's fact literals only (greedy binding); chosen or defined literals no
  longer multiply the theory rules. `(\acyclic r)` inlines a defining rule
  into `#edge` only when it projects nothing away.
- The renderer drops the `dom_S` projections (B14) of every sort no rule
  mentions; over a 435,000-event fact table they were 11 s of grounding.

- `(\acyclic r)`: a constraint that the relation `r` has an irreflexive transitive closure, lowered to `#edge` (relations of arity 2k have k-tuples as nodes); four ports of the applications study attached this by hand; a relation defined only by rules and used nowhere else is inlined into one `#edge` per rule instead of being grounded.
- Order sorts: `OrdDOM` and `Fun` declarations with two core lowerings in plain ASP, enumeration (`enum`, the basic one) and a preorder relation (`rel`), the selection rule as the default (`auto`), and difference logic as an extension (`--ext dl`, `setlah.ext.dl`, run under clingo-dl through `--backend auto`); `--order-lowering` selects per sort (`X=rel,C=dl`); design and theorems in `docs/order-sorts.md`.

All notable changes to SetLaH will be documented in this file.

## [Unreleased]

### Added

- A second front half, `--lowering direct` (`src/setlah/lowering/`): a
  syntax-directed lowering of SetLaH to the transpiler's IR without egglog.
  Same back half, same output on every model both compile (checked by
  answer-set and sampled equivalence on the local models and by the
  corpus runners), about 0.3 s per model against 1 to 4 s, and it handles
  the shapes the egglog path could not (ite-valued frame equalities,
  disjunctions of conjunctions, deep nesting, wide existentials). It is
  the default; `--lowering egglog` (or `SETLAH_LOWERING=egglog`) selects
  the previous front half, which is deprecated and will be removed in a
  later release. See `docs/track-b-results.md`,
  `docs/retire-egglog-proposal.md` and `docs/known-issues.md`.

- Direct lowering: `dom_<Sort>(X) :- p(.., X, ..)` projection rules for every
  external-predicate argument of an `ExtDOM` sort, so guards on the sort
  domain hold when an input gives the sort's elements only through the
  predicates over it (B14). Aggregate variables that do not carry the set
  predicate's argument names fill its remaining positions in order, and an
  aggregate that cannot be matched is rejected instead of compiling to an
  unsafe element (B15). A brute-force first-order oracle
  (`tests/fol_oracle.py`) checks compiled programs against their source
  constraints in the tests.

- Choice/count merging (`transpile/merge.py`, `pipeline.py`): an
  existence/uniqueness pair is fused into `1{...}1` or `#count != 1` only
  when the guards of every constraint of the pair are literals of the
  choice rule's body; otherwise both constraints are emitted as they are.
  A guarded existence constraint used to lose its guard (B16, both
  lowerings).

- The parser runs Lark's LALR(1) with the contextual lexer instead of
  Earley with the dynamic lexer, and is built once per process. The grammar
  reserves a bare predicate atom statement for facts (which is how it was
  always read) and lexes the `=` of `Let` as the comparison token; every
  local, corpus, PORTUS and memory-model file parses to the same AST as
  before (253 files checked), 25 times faster overall and linear in the
  input: 12,000 statements parse in seconds where Earley took 94 s.

### Deprecated

- The egglog front half (`--lowering egglog`, `src/setlah/rewrite/`,
  `transpile/egg_parsing.py`, `transpile/aux.py`, `transpile/normalize.py`
  and the string half of `transpile/pipeline.py`). The CLI prints a warning
  when it is selected.

### Fixed

- Auxiliary predicate names no longer wrap: one counter per compilation
  unit, shared by the rewriter and the transpiler (B7).
- Models are no longer limited to about 200 statements: the rewriter hands
  the transpiler one printed term per statement instead of one block
  expression, and never registers a block-sized cons list (B5).
- The raw-constraint fallback no longer fires on flat antecedents over 8
  or 11 variables or on nested universals from depth 7: `grouped_forall`
  has a consumer rule, the extraction schedule resets its back-off between
  runs, the aux round repeats until the term is lowered, and the recursion
  cap is 64 (B2, harness shapes).
- An existential over nine or more variables no longer crashes with
  `Unsupported VarList: subst_varlist(...)` (B8).
- Symmetry breaking (`not X = Y` to `X < Y`) applies only to constraints
  that are symmetric in the two variables, not to every inequality in a
  block that holds one symmetric pair (B10, wrong output).

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
