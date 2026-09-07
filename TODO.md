# TODO

Engineering items for the compiler, as opposed to the product plan in
`ROADMAP.md` (on the binding branches). Each item cites the evidence it comes
from; the defects are described in `docs/known-issues.md`. Measurements are
from compiling third-party finite-domain problems (DuoAI and mypyvy
verification queries, Alloy commands translated by PORTUS) with the
2026-09-04 fixes applied.

## Correctness

- **B7, wrong output: auxiliary names wrap at five.** A constraint needing a
  sixth auxiliary reuses `__aux_0`, ASP unions the two definitions and a
  cycle closes through the auxiliary chain. Exit 0, clean-looking program,
  wrong answers. Reproducer `tests/inputs/regressions/aux_collision_depth6.{sl,lp}`.
  Fix: one counter per compilation unit, or qualify names by constraint.
  Check whether any Portus result depends on it (those models nest to 15).

- **Make every fallback a hard error.** Six `except Exception` blocks in
  `rewrite/rw.py` and `transpile/aux.py` end in `break`, `continue`, `pass`
  or `return`; `transpile/constraint.py` prints a constraint it could not
  lower as the comment `:- % raw-constraint ...` and exits 0 (B2); on `main`,
  `Rewriter.rewrite_block` returns the unrewritten block when a rewrite
  raises. B1 stayed hidden for a whole workload because each layer swallowed
  the previous one's failure. B2 is reachable on ordinary input: Ivy's
  frame axioms as written fall raw on 130 of 142 DuoAI queries (2026-09-05). A `--lenient` flag can keep the old behaviour
  for anyone who wants it.
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
  `_parse_set_call`, `_extract_var_name`, and, worst, their own module-level
  `_aux_counter`, both starting at 0 and both minting `__aux_N`, although a
  comment calls them shared. That is a latent name collision.

## Architecture

- **Retire the printed-term round trip.** The rewriter serialises egglog's
  extracted expression to text and reads it back with `eval` (2 sites),
  `ast.parse` (6 sites) and regular expressions over the printed term (27 in
  `rw.py` and `transpile/`). It caused B1, it imposes both size caps of B5
  (the C-level recursion limit in the printer on Python 3.12, the parser's
  parenthesis limit on 3.11: roughly 250 statements after splitting), and it
  costs about 1.1 s of a 7.4 s compile. egglog's Python API can return
  structured expressions; the transpiler should consume those, or the
  compiler's own IR, never text.
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
