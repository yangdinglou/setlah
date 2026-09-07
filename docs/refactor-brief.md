# Brief: replacing the egglog front half with a direct lowering

Written 2026-09-07 from the setlah-apps study, as the handoff for a
compiler-side session. Everything cited is on disk; nothing here depends on
chat context.

## What the front half does today

`rewrite/` (rw.py 1,113 lines, egg_rules.py 523, egg_schema.py 271,
converter.py 401) lowers FOL constraints to ASP integrity constraints and
auxiliary rules by equality saturation in egglog. The rule set
(`egg_rules.py`) is textbook normalisation run as a search:

- propositional laws: double negation, commutativity, associativity, De
  Morgan, implication elimination, distributivity, idempotency, identity;
- quantifier laws (`lec10_fo_A/B/C`): negation duality, miniscoping, prenex
  moves;
- free-variable bookkeeping done *inside* the e-graph as relations
  (`var_in_list`, `formula_contains_var`, several rules commented out, three
  `TODO`s for aggregates and grouped forms);
- extraction of existential subformulas into auxiliary predicates
  (`Literal.AuxCall`) and of `#count` aggregates, chosen by cost annotations
  in `egg_schema.py` (aux preferred over nested aggregates, cost 100/500;
  grouped quantifier forms cost 200).

The egglog result is then printed as a Python expression string and read
back by `eval`, `ast.parse` and regexes (`rw.py`, `transpile/egg_parsing.py`,
`transpile/aux.py`, `transpile/pipeline.py:67`). The back half
(`transpile/constraint.py`, `safety.py`, `rendering.py`, `merge.py`,
`normalize.py`) renders the lowered IR to clingo text and is not at issue.

## Why the study wants it replaced

Every compiler defect found by running real corpora sits in the plumbing
around egglog, not in the lowering's semantics (`docs/known-issues.md`):

| defect | where | root |
|---|---|---|
| B5 ceiling at ~200 statements | `pipeline.py:67` | whole block printed as one right-nested expression; CPython refuses >200 nested parentheses |
| B2 silent raw fallback | extraction + `egg_parsing.py` | extractor picks `grouped_forall` (produced at `egg_rules.py:357-361`, consumed nowhere: TODOs at 132/343); non-monotone in variable count |
| B7 auxiliary name collision | `rw.py:343` + `aux.py` | two module-global counters, `max_depth=5` residual path lowered by the transpiler's B1 fallback |
| B1, B3 (fixed) | round trip | let-binding prefix parsed by comma-split regex; aux rule safety |
| compile time | rewriting | about 0.1 s per statement (profile 2026-09-04: 5.8 s of 7.4 s in rewriting) |

Consequences in the study: Portus expert models (222 to 840 lines) do not
compile whole (5 of 12 time out at 2,400 s), so the bounded-relational
domain has 4 usable verdicts of 12; the plain (un-normalised) translation of
Ivy queries falls raw on 130 of 142 DuoAI and 568 of 792 mypyvy queries.

## What a direct lowering is

A syntax-directed function over the formula AST, no e-graph, no string
round trip, linear time:

1. NNF with implication elimination; negation pushed to literals.
2. Miniscoping / prenex as needed; free-variable sets computed by a plain
   recursive function.
3. For each top-level universal `forall X. (phi -> psi)`: body literals of
   `phi` become the integrity constraint's positive body with domain guards
   from `safety.py`; `psi` with existentials becomes an auxiliary predicate
   `aux_k(FV) :- ...` (one rule per DNF cube); negated `psi` becomes `not
   aux_k(FV)`.
4. Aggregates: `#count {Set_p}(V) op k` rendered directly.
5. One auxiliary counter per compilation unit; names qualified by the
   constraint index.

Estimated 500 to 1,000 lines of Python. The cost-based choices egglog makes
(aux versus aggregate) are local patterns a direct lowering can decide with
a fixed rule.

## Two tracks, not one leap

**Track A, fix in place (about a day).** B7: share one counter (or qualify
names). B5: parse the cons list per constraint instead of the whole block.
B2: remove the `grouped_forall` producers or add the consumer. This protects
the existing corpus results and unblocks Portus compilation regardless of
what happens to egglog.

**Track B, direct lowering as a second backend behind a flag.** Keep egglog
selectable. Validate by differential testing on the corpus, which is now a
regression suite of more than 3,200 decided queries (below). Retire egglog
only if the direct backend matches every verdict and compiles faster.

If equality saturation is part of the paper's claimed contribution, Track B
becomes the comparison that argues it either way with data.

## The regression suite (setlah-apps)

Same verdicts on these are the acceptance criterion for Track B.

| domain | command | expected |
|---|---|---|
| DuoAI, n=3 | `ports/duoai/run_auto.py --size 3 --oracle ports/duoai/oracle-n3.txt` | 142/142 agree |
| mypyvy | `ports/mypyvy/run_auto.py` (see its NOTES) | 792/792 agree |
| x86-TSO | `ports/dartagnan/run_tso.py` | 487/487 |
| RVWMO | `ports/dartagnan/run_litmus.py --arch RISCV --model ports/dartagnan/riscv.sl --oracle corpus-snapshots/dartagnan/riscv-1000/run.log` | 948 agree, 2 known (sc failure), 4 untranslated |
| Armv8 | `... --arch AARCH64 --model ports/dartagnan/aarch64.sl --oracle corpus-snapshots/dartagnan/aarch64-1000/run.log --list corpus-snapshots/dartagnan/aarch64-1000-list.txt` | 640 agree, 0 disagree, 342 untranslated |
| Portus sample | `ports/portus/run_auto.py --sliced` | 4 usable of 12 today; the target is 12 whole compiles |
| VCh-rf | `ports/vch-rf/run_vchrf.py --list corpus-snapshots/vch-rf/shared-list.tsv` | all agreeing with FG-Sat |
| limits | `ports/setlah-limits/{scale,width,nesting}.py` | no raw fallback, no ceiling below the Portus sizes |

Reproducers for B1 to B7: `tests/inputs/regressions/`. Mechanism notes with
line references: `docs/known-issues.md`, and in setlah-apps
`ports/setlah-limits/NOTES.md`.

## Open questions for the author (asked 2026-09-07, unanswered)

- Was `max_depth=5` a bound inputs were expected to respect, or a safety
  stop never meant to be hit? (Docstring says 3.)
- Was the transpiler-side `_preprocess_aux_calls` meant to be reachable in
  ordinary runs, or only as the B1 crash guard?
- Was `grouped_forall` an intermediate for an unfinished count-aggregate
  lowering, and is its cost meant to make it win extraction?
- Was parsing the whole block as one Python expression a deliberate part of
  the round trip, or the simplest thing that worked at the sizes tested?
- Is equality saturation a claimed contribution of the paper, or an
  implementation choice?

## Scope, measured (2026-09-07)

The boundary is "everything that reads or writes the printed egglog string",
not "the whole codebase". Of the 6,474 lines under `rewrite/` and
`transpile/`:

| goes with egglog (string-bound) | lines |
|---|---|
| `rewrite/rw.py`, `egg_rules.py`, `egg_schema.py`, `converter.py` | 2,308 |
| `transpile/egg_parsing.py`, `aux.py`, `normalize.py` | 1,246 |
| the string half of `transpile/pipeline.py` | about 100 |

| keeps, consumes the IR (`IRRule`/`IRConstraint`) | lines |
|---|---|
| `constraint.py` (rendering of lowered constraints, partitions, aggregates) | 633 |
| `merge.py` (existence + uniqueness -> `1{..}1`, symmetry breaking) | 538 |
| `transpile/rewrite.py` (equality/inequality -> `#count`) | 486 |
| `rendering.py`, `safety.py` (B6 lives here), rest of `pipeline.py` | about 700 |

So about 56 % is replaced and 36 % kept; the kept passes already take the
IR, which becomes the contract between a direct lowering and the renderer.
`B4` (dropped atom arguments) is in the kept half and not yet pinned to a
module. The parser (`parsing/parser.py`) is Lark Earley with a dynamic
lexer, rebuilt per `Parser()`: separate small item, cache it and try LALR.
Tests: 22 files, 73 functions; the corpus runners are the real suite.
