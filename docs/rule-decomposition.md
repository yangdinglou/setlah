# Rule decomposition in the direct lowering (`--split-width N`)

Branch `grounding-split` (worktree of `direct-lowering`), 2026-09-10.
Provenance of every element, and of the lowering around it, in
`docs/techniques.md`.

**What.** An integrity constraint whose cube has more than N variables
is split along a tree decomposition of its variable graph (two variables
are adjacent when they share a literal; min-fill elimination order). Each
non-root bag becomes a rule `__aux_k(separator) :- guards, literals of
the bag, child temporaries`, the root bag stays the constraint. This is
lpopt's construction (Bichler, Morak, Woltran) applied where the direct
lowering emits constraints, in `DirectLowerer._split_cube`. Grounding of
the constraint drops from about d^(variables) to about d^(treewidth+1)
per rule. Cubes that no decomposition narrows are left alone.

**Soundness.** The temporaries are fresh predicates defined by
stratified rules, so the program is a conservative extension: answer sets
projected onto the original signature are unchanged. Every bag rule is
safe by construction: a bag variable that no positive literal of the bag
binds gets its `dom_T` guard from the variable types the checker knows.

**Why.** The study's second TPTP pass and the memory-model solve times
showed the direct lowering's wide constraints failing to ground (96 EPR
and 92 FNT sweep timeouts, 61 of the EPR ones at domain size 2; the two
Portus snapshot specs; a 1.7x rise in per-test solve time on the
Dartagnan models). The egglog front half had introduced auxiliaries at
every quantifier alternation, which kept constraints narrow by accident;
this pass does it on purpose and only where it pays.

**Switch.** `--split-width N` on the CLI, or `SETLAH_SPLIT_WIDTH=N` in
the environment (so existing runners pick it up); 0 disables. Default
0 until the acceptance runs below settle the threshold.

**Acceptance so far.**
- test suite: 100 passed, 2 xfailed with the pass off; the direct-lowering
  and clingo-execution tests pass with width 3;
- Dartagnan x86-TSO, 487 tests, width 4: every verdict identical to the
  direct lowering, total solve time 1.65 s to 1.29 s;
- Dartagnan RISC-V (954 tests) and Armv8 (982), width 4: every verdict and
  note identical to the direct lowering; solve totals 3.21 s to 3.04 s and
  2.12 s to 2.24 s (noise level);
- mypyvy, Portus snapshot specs, TPTP EPR undecided set: running
  (setlah-apps `ports/tptp/run-epr-split`).

**ALG020+1 (TPTP, Theorem; the SetLah! translation with 8 constants and 4
functions), one clingo run per size, 300 s cap.**

| width | size 6 | size 8 |
|---|---|---|
| off | UNSAT, ground 5.2 s, total 7.9 s | timeout |
| 6 | UNSAT, ground 0.2 s, total 0.6 s | timeout |
| 4 | UNSAT, ground 0.1 s, total 0.4 s | UNSAT, ground 0.3 s, total 137.7 s |

Grounding is solved by the pass; at size 8 what remains is the
refutation itself (137 s of solving on a 0.3 s grounding), which is the
symmetry-breaking question, not a lowering one. Width 4 beat width 6
here; the threshold is still to be settled on the corpus.

**Portus snapshot-isolation specs (the case the pass was built for), width
4, 600 s compile and 300 s solve.** Both amazon snapshot specs and
fullsub2 still time out in clingo at 300 s (z3: SAT in 8 and 22 s, timeout
on fullsub2). Compile stays under a minute. A grounding-versus-solving
diagnosis on textbookSnapshot is running; if grounding is already small
there, the block is the search, not the width, and the pass cannot be
expected to move it.

**Auxiliary rule bodies (2026-09-11).** The pass now also splits the
cubes of auxiliary rules (`make_aux`), with the rule's head variables
kept in the root bag so the head stays bound. TSO at width 3: 487 of 487
verdicts identical, total solve 1.65 s to 1.01 s (the egglog front half's
figure was 0.93 s, so the regression the direct lowering introduced is
gone). Width 3 beats 4 and 6 on every measurement so far.

**Harness note.** The first EPR run of the pass used the live worktree
while it was being edited (constraints-only at first, then auxiliary
bodies too); both versions are sound, so its verdicts stand, but its
timings mix two versions. Later runs use a snapshot
(`setlah-apps/upstream/setlah-split`).

**Width 3 on the other two memory models (snapshot of this tree).**
RISC-V, 954 tests: every verdict and note identical, total solve 3.21 s
to 2.57 s. Armv8, 982 tests: identical, 2.12 s to 1.84 s. With TSO
(1.65 s to 1.01 s) that is the direct lowering's solve-time regression
on all three corpora removed, at width 3, with no verdict changed on
2,423 tests.

**Portus snapshot specs, diagnosis.** Grounding alone exceeds 900 s with
the pass off and on. The wide lines of that program are not constraints
(the widest constraint has 5 variables) but the study translator's
`chain_N` rules, 8 variables in the head and body, produced by
`smttc2setlah.py` when it linearises Alloy's quantifier chains. A rule
whose head carries all its variables cannot be narrowed by decomposition,
so this case is the translator's to fix (project the chain onto the
variables still needed), not the pass's. Recorded so that the acceptance
list does not overstate what the pass covers.

**TPTP EPR, the 209 problems the direct lowering left undecided or
timed out on (snapshot of this tree, width 6, 120 s sweep budget).**
No new verdict and no wrong verdict. 9 sweep timeouts became completed
sweeps to size 8 (all 36 completed sweeps are Unsatisfiable-status
problems with more constants than the cap, so no model finder decides
them); the remaining 86 timeouts moved from size 2 (61 before, 25 after)
to sizes 3 to 8. Compile time rose from a median of 6.2 s to 10.6 s on
these large models (the min-fill order on cubes of tens of variables).
Reading: the pass removes the grounding wall on this tail as far as
width goes, and what is left is refutation per size and atoms too wide
to split; the same conclusion as the expert-arm rerun with the tree
splitter (85 of 175 still time out there).

**Bug found by the DuoAI differential (2026-09-11), fixed.** Two of 142
queries went from unsatisfiable to satisfiable at width 3. Cause: when
splitting an auxiliary rule's body, the kept (head) variables were only
deferred in the elimination order, not excluded, so once every other
variable was gone a head variable was eliminated too and a temporary
projected it away (`__aux_11(D) :- dom_Node(N), not t(D, N), ...` for a
head over `(D, N)`). Kept variables are now never eliminated: they form
the root bag. Regression test `test_split_keeps_head_variables` with the
query as `tests/inputs/regressions/split_keep_head_var.{sl,lp}`. Every
acceptance run that used the auxiliary-body splitting before this fix
is being redone on a new snapshot; the constraint-only runs (TSO at
width 4, ALG020+1) did not exercise the bug.

**Memory models on the fixed pass (width 3, fresh snapshot).** TSO 487,
RISC-V 954, Armv8 982: every verdict and note identical to the direct
lowering. The totals recorded in that run (2.62 s, 5.59 s, 4.10 s) are
not comparable with the earlier ones: the machine carried a load average
of 11 on 8 cores from the concurrent EPR and mypyvy runs, and the ground
programs are the same size as before the fix (TSO: three extra rules
in the model, identical grounding time per test in isolation). The
solve-time comparison is redone on an idle machine once the batch ends.

**mypyvy differential, first attempt void (2026-09-11).** 99 of 792
verdicts differed from the 09-08 direct run, all satisfiable to
unsatisfiable. Not the pass: that run used `--size auto` (each query
fixes its own `node` size from its cardinality constants), the
differential used `--size 3`, and the first differing query is
unsatisfiable at size 3 and satisfiable at size 2 for the direct-lowering
snapshot, the branch at width 0 and the branch at width 3 alike. Redone
with `--size auto`; a width-0 control at size 3 runs alongside to
confirm the 99 are size artefacts.

**mypyvy at size 3, width 0 against width 3 on this branch: 792 queries,
0 verdict differences.** The 99 differences against the 09-08 run appear
identically at width 0, so they are the size artefact described above,
and the pass is verdict-preserving on the corpus. The size-auto
differential against the 09-08 run is still running for completeness.

**mypyvy, per-query sizes (`--size auto`), width 3, fixed pass: 792 of
792 verdicts identical to the 09-08 direct-lowering run.**

**Correctness status of the fixed pass, 2026-09-11:** test suite (103
passed, 2 xfailed), DuoAI 142/142, mypyvy 792/792, Dartagnan TSO 487,
RISC-V 954, Armv8 982 all identical; TPTP EPR undecided set rerun in
progress (no verdict changed in the first 16). Timing on the memory
models to be redone idle.

**TPTP EPR undecided set, fixed pass, width 3, snapshot (2026-09-11).**
209 problems: no new verdict, no wrong verdict; 14 sweep timeouts became
completed sweeps to size 8 (all on Unsatisfiable-status problems with
more constants than the cap); the remaining 84 timeouts moved from size
2 (26 stay there, 34 reach sizes 3 to 7) upward; compile median 6.4 s to
7.0 s (width 3 is much cheaper than width 6 was on these large models).
This closes the acceptance runs: correctness on every corpus, grounding
relief where width was the limit, no TPTP verdict gained on the hard
tail. Timing on the memory models still to be redone on an idle machine.

**Memory-model timing, paired run (2026-09-12).** Direct lowering and the
pass at width 3 run back to back under the same conditions (the machine
was not idle after all, load average about 20 at the start, but both
arms saw it): verdicts identical on all 2,423 tests; solve totals TSO
0.87 s to 0.81 s, RISC-V 2.05 s to 1.98 s, Armv8 1.32 s to 1.29 s, that is
2 to 7 % less, within noise. Note that the direct lowering's own totals
here (0.87 s on TSO) are at the egglog front half's level (0.93 s), so
the "1.7x slower per test" figure recorded for the direct lowering on
09-08 was a load artefact of that run, not a property of the lowering.
The pass's measurable benefit is therefore on grounding-bound models
(ALG020+1 and the TPTP tail), not on the memory models, where it is
neutral.
