# Reproducibility: which compiler produced which measurements

The applications study (separate repository `setlah-apps`) never ran the
compiler from a live checkout: each measurement was taken on a frozen copy of
one commit (its directories `upstream/setlah-direct-<sha>`, `setlah-frozen`,
`setlah-split`). Every one of those copies is byte-identical to `git archive`
of the commit named below, so a reproduction only needs the commit.

## The commit to use

| Purpose | Ref | Commit |
|---|---|---|
| Every compiled cell of the PLDI 2027 submission (order sorts, acyclicity lowerings, SAT and MonoSAT backends, the final sweep) | tag `paper-pldi27` | `ef262db` |
| The Pusharoo bounded-translation and CoCoMoT bound-sweep rows (`--split-width 3`) | tag `study-split-width` (branch `grounding-split`) | `fd2b624` |

The tip of `order-sorts` (and of `direct-lowering`, the same commit) differs
from `ef262db` only in documentation and packaging metadata: the code and
tests are the paper's. To run exactly the paper's compiler next to a working
checkout:

```bash
git worktree add ../setlah-paper paper-pldi27
python -m pip install -e ../setlah-paper            # or: export PYTHONPATH=../setlah-paper/src
```

The study's runners select the compiler through the environment, not through
the installed package: `SETLAH_SNAP=<checkout>/src` and `PYTHONPATH=<checkout>/src`.
Make sure no other `setlah` is installed in the same environment, or that
`PYTHONPATH` is set for every run: an editable install of an older checkout
silently wins otherwise.

## Earlier snapshots

The study's notes also cite tables taken during development. Each snapshot is
the commit of the same short name on branch `order-sorts` or `direct-lowering`
(history is linear):

| Snapshot | Commit subject | Used for |
|---|---|---|
| `48a53f1` | Track B results: corpus re-run after B16 unchanged | the PORTUS sample of 12, the attached-`#edge` tables of 2026-09-18 |
| `0054fb5` | Add `(\acyclic r)`, lowered to `#edge` | first compiler-output acyclicity runs |
| `4b614b2` | inline defining rules into `#edge` | the inlining measurements |
| `73bc66e` | dl: guard by the cube's binding literals | TSN source-model first table |
| `67a708c` | inline only projection-free rules | |
| `23dba42` | dl: guard by fact literals only | TSN and JDBCMySQL-1 measurements |
| `c92c701` | renderer drops unused dom projections | |
| `32b5b8a` | dl: guards are deterministic literals or domain atoms | the compiler-output tables of 2026-09-23 |
| `dc0607f` | dl: shared reified Booleans, exclusion lemmas | the DPQA one-file table |
| `f41e353` | `--acyclic-inlining auto/all/none` | the VCh-rf inlined run |
| `6798d1d` | selection: dl falls back to enum under auto | the Pusharoo order-sort table |
| `ef262db` | acyclicity lowerings, `__may_` guards, sat and monosat backends | everything in the paper |

Two older copies: the study's `setlah-direct` is `4df62c7` (direct-lowering tip
of 2026-09-08) and `setlah-frozen` is `e6a6b66` (lean4-binding tip of 2026-09-05,
the egglog-era compiler used for the study's first three weeks).

## Optional solvers and versions

The published measurements used Python 3.12, `clingo==5.8.0`,
`clingo-dl==1.5.0.post1`, `python-sat==1.9.dev15` (CaDiCaL 1.5.3 through PySAT)
and MonoSAT built from `sambayless/monosat` at `fa810d4`; see the README for
the install commands. The test suite (148 passed and 2 expected failures with
all optional solvers; the tests that need an absent solver are skipped) takes
about 100 s.
