# Track B results (2026-09-08, branch `direct-lowering`)

The direct lowering (`src/setlah/lowering/`, commit `5fbe0b6`) against the
egglog front half, both on the same back half, on the same checkout, through
the study's runners with `SETLAH_LOWERING=direct`. Output directories in
setlah-apps are suffixed `-direct`; the egglog re-runs after the B10 back-half
fix are suffixed `-trackB-egglog`. The machine was shared between runs, so
times are indicative. Track A's numbers are in `docs/track-a-results.md`.

## Acceptance: the regression table with `--lowering direct`

| domain | expected | direct lowering | compile per query, direct vs egglog |
|---|---|---|---|
| DuoAI, n=3, 142 queries | 142/142 | **142/142** (137 UNSAT, 5 SAT), 0 failures | mean 1.3 s (max 3.3 s) vs 4.8 s (max 6.7 s) |
| mypyvy, 792 queries | 792/792 | **792/792** (536 UNSAT, 256 SAT), 0 failures | mean 1.1 s (max 3.7 s) vs 6.3 s (max 14.6 s) |
| x86-TSO | 487/487 | **487/487** | model 1.0 s vs 2.7 s |
| RVWMO (1,000-list) | 948 + 2 known + 4 | **948 agree, the same 2, 4 untranslated** | |
| Armv8 (1,000-list) | 640 / 0 / 342 | **640 / 0 / 342** | |
| VCh-rf shared list (400-event cap) | all agreeing | **12/12** | |
| PORTUS sample, whole model | 12 whole compiles | see below | |

The three concurrency models (`ports/dartagnan/{tso,riscv,aarch64}.sl`)
compile in 0.77, 1.06 and 0.92 s end to end on a loaded machine (3.9 to
4.6 s with egglog); an idle single run of `tso.sl` takes 0.27 s after the CLI
stopped importing egglog for the direct path.

No verdict differs between the two front halves on any runner.

### PORTUS sample under the direct lowering

(filled in when the run completes; see `ports/portus/auto-sample12-direct.txt`)

## Local differential

`tests/test_direct_lowering.py`: on 21 models where both front halves compile
(the regression reproducers and the examples with instances), sampled
SAT/UNSAT equivalence with the choice predicates pinned at random (40
samples per instance) agrees on every sample; on 5 models the egglog path
cannot compile (raw fallback, B11, B12, recursion depth) the direct lowering
compiles and grounds. `scratchpad/diff_lowering.py` did the same with full
answer-set enumeration on the limits-harness models (flat, nested, width,
mixed): every enumerable model agrees exactly.

## What the differential found in the shared back half

- **B10**, wrong output, fixed: block-wide symmetry breaking (see
  `docs/known-issues.md`). It affected the egglog path too; the corpus
  counts on the egglog path were re-run after the fix (table below).
- A quadratic deep copy in the equality-substitution pass (30 s on one
  model), fixed.

### egglog path after the B10 fix

| domain | result |
|---|---|
| DuoAI, n=3 | (running) |
| mypyvy | (running) |

## What the direct lowering does that egglog did not

| shape | egglog path | direct |
|---|---|---|
| ite-valued frame equality (`raw_f0`, the 130/142 DuoAI and 568/792 mypyvy plain-translation fallbacks) | raw fallback | compiles, semantics checked in `test_direct_lowering_enforces_ite_frame_equality` |
| or-of-and 3x2 (`or_of_and_3x2_fallback`) | raw fallback | compiles |
| flat antecedent over 13 variables (`wrongcode_v13_*`, B11) | aux rule body `?`, exit 0 | compiles |
| vacuous universals (`unsafe_w6c2_*`, B12) | unbound aggregate variables, exit 0 | compiles |
| the author's recursion datapoint (`recursion_ground_guards_or_of_and`) | recursion depth exceeded | compiles in 2.4 s (the program itself is ungroundable at any size: 610-literal constraints) |
| the author's B3 datapoint (`unsafe_aux_negated_existential_tptp`, TPTP NLP037+1) | unsafe auxiliary heads, Clingo refuses to ground, exit 0 | compiles and grounds (auxiliary variables get their domain guards in the lowering) |
| B9 (`wrongverdict_p1_*`) | UNSAT vs z3 SAT | UNSAT as well: not in the replaced half |

## Cost

`src/setlah/lowering/`: 5 files, about 1,000 lines including docstrings
(`wc -l`: 1,027). Replaced on the egglog side: about 3,500 lines. See
`docs/retire-egglog-proposal.md`.
