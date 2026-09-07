# Initial prompt for the compiler refactoring session

Paste the block below into a fresh Claude Code session started in
`/Users/ydl/project/mine/setlah`. Fill in the "Author's answers" section first
(or delete a line to leave the question open).

---

You are working in the SetLah! compiler repository (`/Users/ydl/project/mine/setlah`).
The goal is to replace the egglog-based front half of the compiler with a
direct, syntax-directed lowering, without changing what the compiler
accepts or what the ASP renderer emits. Start by reading, in this order:

1. `docs/refactor-brief.md` — what egglog does today, why it is being
   replaced, the measured scope boundary, the two-track plan, and the
   regression suite with expected counts. Treat it as the specification.
2. `docs/known-issues.md` — defects B1 to B7 with mechanisms, line references
   and reproducers under `tests/inputs/regressions/`.
3. `TODO.md` — the correctness and architecture items already recorded.
4. `/Users/ydl/project/mine/setlah-apps/ports/setlah-limits/NOTES.md` — the
   measurements behind the brief (compile-time scaling, the ceiling near 200
   statements, the non-monotone fallback, the three mechanisms traced to code).

Do not re-derive any of that from scratch; if something there looks wrong,
say so and check it against the reproducers.

Work in two tracks, in this order, and do not start the second until the
first passes its acceptance check.

Track A, fix in place. Three targeted fixes to the existing pipeline:
B7 (one auxiliary counter per compilation unit, or names qualified by
constraint), B5 (parse the constraint cons-list one constraint at a time
instead of the whole block as one Python expression), and B2 (remove the
`grouped_forall` producers at `rewrite/egg_rules.py:357-361` or add the
consumer the two TODOs describe). Each fix gets a regression test from the
reproducers. Acceptance: the limits harnesses in
`/Users/ydl/project/mine/setlah-apps/ports/setlah-limits/` show no raw
fallback and no ceiling at the sizes they sweep, and the corpus runners in
the brief reproduce their expected verdict counts exactly.

Track B, the direct lowering as a second backend. Implement it as a new
package behind a CLI flag (for example `--lowering direct`, default staying
`egglog`) that produces the same IR the existing passes consume
(`IRRule` / `IRConstraint` in `transpile/ir.py`), so `merge.py`,
`transpile/rewrite.py`, `constraint.py`, `safety.py` and `rendering.py` are
reused unchanged. The lowering is: NNF with implication elimination;
miniscoping and prenexing as needed; free-variable sets by a plain
recursive function; each top-level universal implication becomes an
integrity constraint with domain guards, existential consequents become
auxiliary predicates with one rule per DNF cube; aggregates rendered
directly. Fixed rules decide auxiliary-versus-aggregate choices; no cost
search. Acceptance: with `--lowering direct` every runner in the brief's
regression table reproduces its expected counts, the three concurrency
models compile in well under a second, and the Portus expert models that
timed out at 2,400 s compile whole. Only after that, propose (do not
perform) retiring egglog.

Constraints:
- Work on a new branch `direct-lowering` created from `main`. Commit on that
  branch as you go with clear messages. Do not merge into `main`,
  `binding-core`, `python-binding` or `lean4-binding` unless asked.
- Never commit `blog.md` or `blog-v2.md`.
- The study repository's virtual environment imports this checkout's `src/`
  through an editable install, so whatever branch is checked out here is
  what the study's runners compile with. Say which branch is checked out
  before running any corpus runner, and restore `lean4-binding` when you are
  done for the day unless told otherwise.
- Validate by differential testing on the corpus, not by unit tests alone.
  Report every long run when it finishes, with its result.
- If a fix changes a verdict anywhere in the regression suite, stop and
  report the instance before continuing; a changed verdict is either a bug
  in the fix or a bug the old compiler had, and which one matters.
- Keep `docs/known-issues.md` and `TODO.md` current as you go: mark defects
  fixed with the commit, and record any new defect with a reproducer.

Author's answers to the brief's open questions (fill in):
- `max_depth=5` was: <bound inputs should respect | a safety stop | other>
- The transpiler-side `_preprocess_aux_calls` was meant to be: <reachable normally | only the B1 crash guard>
- `grouped_forall` was: <an unfinished count-aggregate lowering | something else>
- Parsing the whole block as one expression was: <deliberate | the simplest thing at the sizes tested>
- Equality saturation is: <a claimed contribution of the paper | an implementation choice>

Begin with Track A, B7 first. Before editing, show the exact lines you will
change and the test you will add.
