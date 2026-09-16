# TODO

Engineering items for the compiler, as opposed to the product plan in
`ROADMAP.md` (on the binding branches). Each item cites the evidence it comes
from; the defects are described in `docs/known-issues.md`. Measurements are
from compiling third-party finite-domain problems (DuoAI and mypyvy
verification queries, Alloy commands translated by PORTUS) with the
2026-09-04 fixes applied.

## Correctness

- **B9, wrong verdict on PORTUS commands that compile cleanly.** Three
  `c11_perturbed` commands and two `alloy/question` commands answer UNSAT
  where z3 answers SAT, on this branch and on `b4c7661` alike. Reproducer
  `tests/inputs/regressions/wrongverdict_p1_c11_perturbed_cmd3.{sl,lp}`
  (not minimised). Highest-severity open item together with B4; the
  direct lowering is the cheapest way to localise it.
- **B10 (TPTP-side): an equality consequent `guards -> (= C A)` lowers to `:- guards, C < A.` next to a collapsed existence+uniqueness pair.** Same mechanism as `wrongcode_b10_symmetry_breaking.sl`; TPTP reproducers `tests/inputs/regressions/wrongcode_eq_consequent_lt{,_min,_ok_no_collapse}.sl`; see `docs/known-issues.md#b10`.
- **B3 datapoint (TPTP): unsafe auxiliary heads from alternating quantifiers under negation** (`unsafe_aux_negated_existential_tptp.sl`, NLP037+1; 5 of 64 NLP problems in the FNT sample). See `docs/known-issues.md#b3`.
- **B8, crash: an existential with nine or more bound variables.** Fixed
  in `f756e4d` (the unevaluated `subst_varlist` call was the cheaper
  extraction representative; the substitution functions now cost 10000).
  Reproducers `tests/inputs/regressions/exists_binders{8_ok,9_varlist_crash}.sl`.
- **B2, or-of-and shape.** A universal over three or more disjuncts of
  conjunctions of equalities still falls back
  (`or_of_and_3x2_fallback.sl`, strict xfail): the extracted term keeps the
  body as a disjunction of conjunctions, and the equality budget does not
  finish the distributivity into DNF. The direct lowering should not
  distribute at all: a conjunction under negation inside a cube becomes an
  auxiliary predicate.
- **B7, wrong output: auxiliary names wrap at five.** Fixed in `fd5ca93`
  (one counter per compilation unit, `AuxNamer` threaded from the rewriter
  into the transpiler). Reproducer
  `tests/inputs/regressions/aux_collision_depth6.{sl,lp}`. Still to check:
  whether any Portus result depended on it (those models nest to 15).

- **Make every fallback a hard error.** Six `except Exception` blocks in
  `rewrite/rw.py` and `transpile/aux.py` end in `break`, `continue`, `pass`
  or `return`; `transpile/constraint.py` prints a constraint it could not
  lower as the comment `:- % raw-constraint ...` and exits 0 (B2); on `main`,
  `Rewriter.rewrite_block` returns the unrewritten block when a rewrite
  raises (`direct-lowering` re-raises since `b4c7661`). B1 stayed hidden
  for a whole workload because each layer swallowed the previous one's
  failure. B2 is reachable on ordinary input: Ivy's frame axioms as
  written fall raw on 130 of 142 DuoAI queries (2026-09-05). The
  limits-harness shapes of B2 (flat antecedents over 8 and 11 variables,
  nesting from depth 7) are fixed in `0be936a`; the ite-valued frame
  equality still falls raw and exits 0. A `--lenient` flag can keep the
  old behaviour for anyone who wants it.
- **B4, wrong code: a body atom loses its arguments.** Exit 0, silently
  vacuous constraint. Reproducer `tests/inputs/regressions/wrongcode_d1_*`;
  not yet minimised below one 123-line statement. Highest-severity open item.
- **B6, safety check too conservative.** A recursive atom is not taken as
  binding a head variable (`tc(X0, XM) :- base(X0, X1), tc(X1, XM).` is
  rejected), an equality to an expression over bound variables does not
  bind its left side, and the check is order-sensitive: `r(X) :- q(X).`
  before `q(X) :- p(X).` is rejected, the reverse order accepted, with a
  message ("not bound in body") that also stands in for "undefined
  predicate". All are safe rules; callers work around them with a domain
  guard or by reordering. A two-pass check fixes the order case.
- **Unify the two auxiliary-predicate paths.** `rewrite/rw.py` and
  `transpile/aux.py` each carry their own `_parse_aux_call`,
  `_generate_aux_rule`, `_extract_balanced_call`, `_split_top_level`,
  `_parse_set_call`, `_extract_var_name`. The two module-level
  `_aux_counter` globals, which caused B7, were replaced by one counter per
  compilation unit in `fd5ca93`; the duplicated parsing helpers remain.

## Architecture

- **Retire the printed-term round trip.** The rewriter serialises egglog's
  extracted expression to text and reads it back with `eval`, `ast.parse`
  and regular expressions over the printed term (`rw.py` and `transpile/`).
  It caused B1 and it costs about 1.1 s of a 7.4 s compile. The block-level
  half is gone since `b4c7661` (B5): the rewriter walks cons lists with
  `get_callable_args` and hands the transpiler one printed term per
  statement, so no size cap depends on the statement count any more. The
  per-constraint half remains: `_rewrite_single_constraint` still prints
  each extracted constraint, rewrites `AuxCall`s textually and `eval`s the
  result. egglog's Python API can return structured expressions; the
  transpiler should consume those, or the compiler's own IR, never text.
- **Output is not deterministic across runs.** The same model compiled twice
  by the same compiler can differ in the order of an auxiliary predicate's
  cube rules and in the element order of printed `Set[Term]`s (seen
  2026-09-07 on `raw_f1_frame_axiom.sl` and the limits model `flat08.sl`,
  three runs, two or three distinct outputs). Semantically equal so far, but
  it defeats byte-level differential testing and could mask a real change.
  Likely egglog set iteration order; pin it or sort before printing.
- **The rewrite schedule is a budget, not a fixpoint.** `equal_set` runs
  15 iterations and `extraction` 20 (as 4 x 5 since `0be936a`) under
  egglog's back-off scheduler, and the normalisations they must complete
  are chains of n sequential steps (one quantifier level, one literal per
  iteration). Which chains finish depends on the ban pattern, so lowering
  is non-monotone in formula size (B2). Saturating instead blows up on the
  propositional rules (4 min for 8 variables without the scheduler). The
  direct lowering removes the problem; within egglog, a pre-normalisation
  in Python (NNF, `forall` as `not exists not`) before saturation would
  shorten every chain to a constant.
- **One saturation per block, not per constraint.** Profiling a 31-constraint
  DuoAI query: 7.4 s total, of which rewriting 5.8 s across 38 per-constraint
  egglog saturations (egglog internals 3.8 s). Reusing the e-graph, or
  saturating the whole constraint list once, is the largest lever.
- **Cache the parser.** `Parser()` rebuilds the Lark grammar per instance:
  1.2 s of the same 7.4 s. A module-level parser, or Lark's cache, is a
  trivial 15 percent.
- **Split `rewrite/rw.py`** (1,113 lines, one class that rewrites, prints,
  re-parses and post-processes) along those phases once the round trip is
  gone.

## Semantics worth settling in the paper's presentation

- **The auxiliary rule schema must be ASP-safe.** `aux(FV) :- cube` is a
  correct first-order clause, but its ASP rendering needs `dom(V)` for every
  variable of `FV` the cube does not bind (B3). If the paper states the
  schema without the guard, an implementer will reproduce the defect.
- **Empty domains.** The QE keeps a cube for the case where a sort is empty
  (`not dom_S(_)`), more general than many-sorted FOL's non-empty sorts. If
  the paper assumes non-empty sorts, those cubes are dead and can be dropped,
  giving fewer auxiliary rules. Either way is sound.

## Tests

- The 43 tests that existed before 2026-09-04 never exercised a multi-cube
  auxiliary call or a two-witness constraint; a 13-line program crashed the
  released compiler. Keep growing `tests/inputs/regressions/` from real
  workloads, and add a performance regression on compile time per statement.

## Housekeeping

- `import re` inside a function in `rw.py`; `.lake/` untracked in the
  Python-only branches; `blog*.md` drafts live in the working tree only.

## From the applications study (setlah-apps, as of 2026-09-16)

Evidence and per-domain detail live in `../setlah-apps/corpus/feature-delta.md`
(what the expert ASP arm used that compiled SetLah! could not express),
`../setlah-apps/corpus/consolidation.md` and the port notes under
`../setlah-apps/ports/*/NOTES.md`. Items below are the compiler's; the
study keeps its own stand-ins (clingo API around the compiled program).

### Compiler defects (open, reproducers in `tests/inputs/regressions/`)

- [x] **B15** wrong code: aggregate variables not reusing the defining rule's
  names gave an unsafe aggregate element, exit 0. Fixed on `direct-lowering`
  (positions the names do not match are filled positionally; anything else
  is rejected). See `docs/known-issues.md#b15`.
- [x] **B14** wrong verdict: auxiliary heads and aggregate outer variables guarded
  by `dom_<Sort>`, undefined for external sorts; hit in CoCoMoT, Mockdown and
  VCh-rf. Fixed on `direct-lowering`: the lowering emits `dom_<Sort>(X) :- p(.., X, ..)`
  for every external-predicate argument of an `ExtDOM` sort, so the ports'
  `projections.lp` stand-ins are no longer needed. See `docs/known-issues.md#b14`.
- [ ] **B13** (shadowed binders, `docs/known-issues.md#b13`): not reproduced on
  the branch; the LCL653 reproducer's 736 answer sets all satisfy its
  constraints under the brute-force oracle (`tests/fol_oracle.py`). Needs the
  original failing instance or translator output to reopen.
- [ ] B2, B4, B5, B6 above remain open; B9 (a wrong UNSAT on a PORTUS command)
  is documented in `../setlah-apps/ports/portus/`.

### Compiler performance and lowering shape

- [ ] Rewrites the study had to do in its translators and that belong in the
  lowering: distribute `(=> c (and ...))` into per-conjunct constraints;
  turn one-variable `ite` chains into lookup-table facts; statement-level
  witnesses for existentials; constants of a query as facts rather than
  inlined terms. CoCoMoT: 6,963 s compile against 314 s solve over 28 traces
  (`../setlah-apps/ports/cocomot/NOTES.md`).
- [ ] Keep functional structure: inlining `define-fun` bodies produces rules
  whose width does not ground (Pusharoo); a node-by-node derived-predicate
  lowering grounds all 291 sampled queries (`../setlah-apps/ports/pusharoo/NOTES.md`).
- [ ] Decide the `grounding-split` branch (rule decomposition, `--split-width`),
  verdict-preserving on every corpus; the CoCoMoT arm needs it.

### Language features, ranked by what they would have won

1. [ ] **Acyclicity and closure as built-ins with a compact order
   representation.** VCh-rf: `#edge` removed the cubic closure; the
   remaining wall was the closure over event pairs, and the closure computed
   outside the grounder (earliest-successor vectors) took the arm from 39 to
   56 of 56 on the shared list and from 36 to 60 of 63 on the consistent set,
   ahead of SMT-Sat (5 of 63 on the same machine).
2. [ ] **An order theory or integer positions for the part a closure leaves
   free** (VCh-rf's ccache family; clingo-dl-style propagation).
3. [ ] **Optimisation**: `#minimize`/`#maximize`, weighted `#sum`, priorities
   (CoCoMoT cost bound sweep, Mockdown objective).
4. [ ] **Multi-shot and externals** at the language level (bound sweeps,
   CEGAR/CEGIS loops; done today through the clingo API).
5. [ ] **Negation in rule bodies** (Mockdown, VCh-rf choice restriction).
6. [ ] **Bounded integer arithmetic as a domain** (CoCoMoT edit-distance cells,
   Pusharoo verification conditions).
7. [ ] **Exact rational arithmetic or an oracle hook** (Mockdown is MaxSMT
   over reals; clingcon's integers are inexact there: 211 of 1,862 below z3).
8. [ ] **Term-level recursion** over data (CoCoMoT guards).
