# Track A results (2026-09-07, branch `direct-lowering`)

The "fix in place" track of `docs/history/refactor-brief.md`: B7, B5 and B2 fixed
in the existing egglog pipeline, plus B8 found by the author during the
same day. Commits, in order: `fd5ca93` (B7), `b4c7661` (B5), `0be936a`
(B2, harness shapes), `f756e4d` (B8). Mechanisms and reproducers are in
`docs/known-issues.md`.

All corpus runs below were made with this checkout on `direct-lowering`
through the study's own runners (setlah-apps), into fresh output
directories suffixed `-trackA` so the study's recorded results were not
overwritten. The machine was shared between runs, so times are indicative.

## Limits harness (acceptance: no raw fallback, no ceiling)

| sweep | before (`ports/setlah-limits/NOTES.md`) | after |
|---|---|---|
| flat antecedent, 3 to 13 variables | raw at 8 and 11 | all lower, 0.6 to 1.8 s |
| nested universals, depth 1 to 10 | raw from 7 | all lower, 0.5 to 2.1 s |
| width, 2 to 6 variables x 2 to 16 conjuncts | (not previously swept past 4x8) | all lower, 0.7 to 1.6 s |
| scale, constraints only | `)` syntax error at 192 statements | 192 / 302 / 502 statements in 20 / 30 / 48 s |
| scale, mixed | `)` syntax error at 302 | 455 / 602 / 902 statements in 19 / 26 / 38 s |

Compile time stays linear at about 0.1 s per constraint.

## Corpus runners (acceptance: the brief's expected counts, exactly)

| domain | expected | result |
|---|---|---|
| DuoAI, n=3, 142 distinct queries | 142/142 agree | **142/142** (137 UNSAT, 5 SAT), 0 failures, compile mean 4.8 s, max 6.7 s |
| mypyvy, 792 queries, size auto | 792/792 agree | **792/792** (536 UNSAT, 256 SAT), 0 failures, compile mean 6.3 s, max 14.6 s |
| x86-TSO | 487/487 | **487 agree, 0 disagree** |
| RVWMO (1,000-list) | 948 agree, 2 known, 4 untranslated | **948 agree, 2 disagree** (`ISA-S-DEP-DATA-SUCCESS`, `LB+addr+addrpx-poxp+VAR2`, the recorded sc-failure pair), **4 untranslated** |
| Armv8 (1,000-list) | 640 agree, 0 disagree, 342 untranslated | **640 / 0 / 342** |
| VCh-rf shared list | all agreeing | **12/12** at the runner's default 400-event cap |
| PORTUS sample, whole-model path | 4 usable of 12; target 12 whole compiles | **12/12 compile whole** (8 to 151 s; 5 timed out at 2,400 s before). Verdicts below. |

No verdict changed anywhere. The DuoAI and mypyvy runs used `--oracle-inline`
(z3 per query) on `ports/duoai/inferred-distinct` and
`ports/mypyvy/lockserv-distinct`, the sets the study's own clean runs used.

### PORTUS sample, per command (from `auto-allcmds-trackA-partial.txt`)

| command | compile | raw | solve | z3 | verdict |
|---|---|---|---|---|---|
| talks/scc_mp cmd1 | 40 s | 1 | UNSAT | UNSAT | agree (relaxed UNSAT) |
| alloy/fullsub2 cmd1 | 151 s | 10 | timeout 300 s | timeout | none |
| hc-atd/converge cmd1 | 8 s | 0 | SAT | SAT | agree |
| hc-atd/hc7 cmd1 | 89 s | 6 | SAT | SAT | inconclusive (relaxed SAT) |
| hc-jwb/hc4 cmd1 | 19 s | 0 | SAT | SAT | agree |
| alloy/question cmd1 | 83 s | 1 | UNSAT | SAT | **disagree** (B9) |
| litmustestgen/c11_perturbed cmd1 | 79 s | 0 | UNSAT | UNSAT | agree |
| litmustestgen/scc_perturbed_scflip cmd1 | 89 s | 2 | SAT | SAT | inconclusive |
| litmustestgen/tso_perturbed cmd1 | 66 s | 4 | SAT | SAT | inconclusive |
| amazon/serializableSnapshot cmd1 | 81 s | 0 | timeout 300 s | SAT | none |
| amazon/textbookSnapshot cmd1 | 59 s | 0 | timeout 300 s | SAT | none (clingo timed out at 900 s before too) |
| MSV/lc-lenses cmd1 | 21 s | 0 | UNSAT | UNSAT | agree |

Usable verdicts: 5 agreeing (4 before) and 1 disagreeing (new, B9). The
sample was covered by an all-commands run that was stopped after 35
commands; the first command of each model is the sample. Outside the sample
the same run found `c11_perturbed` cmd3, cmd4, cmd5 disagreeing with a clean
compile, which is B9's reproducer, and 15 raw fallbacks across 9 commands
(1 to 10 each), the remaining B2 shapes on this workload.

## Remaining, for Track B

- B2's remaining shapes: the ite-valued frame equality (`raw_f0`), the
  or-of-and shape (`or_of_and_3x2_fallback.sl`), and the 15 fallbacks in the
  PORTUS run. All are chains that a budgeted saturation does not finish.
- B9 (and B4): wrong code on clean compiles; a second, independent lowering
  is the cheapest way to tell compiler from translator.
- The raw fallback still exits 0.

## Answers to the brief's open questions, from the evidence

- `max_depth=5` was a safety stop that inputs hit: each recursive pass lowers
  exactly one quantifier level, so it was also a hard cap on nesting depth
  (6 with the transpiler's residual). Now 64.
- The transpiler-side `_preprocess_aux_calls` is reachable in ordinary runs
  whenever the rewriter's cap is hit; with the cap at 64 it is the B1 crash
  guard only.
- `grouped_forall` was an intermediate with no consumer; its cost was not
  what made it win, the absence of the integrity form was. The consumer
  now exists.
- Parsing the whole block as one expression was the simplest thing at the
  sizes tested; nothing else depended on it.
- Whether equality saturation is a claimed contribution is for the author;
  the data says its budget and scheduler, not its rules, caused B2 and B8.
