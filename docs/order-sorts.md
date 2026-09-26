# Order sorts: a basic lowering and a difference-logic extension (design draft, 2026-09-23, revised the same day)

Draft for the language paper's technical core, written from the applications
study (`setlah-apps`, `corpus/feature-delta.md`, `corpus/language-proposal.md`).
Definitions and theorem statements are proposed here with proof sketches; the
proofs and the compiler changes belong to the compiler sessions. Every claim
that is a measurement cites the study's result directory.

## 1. Problem

A bounded integer sort whose values occur only in comparisons and constant
offsets (positions, time steps, coordinates, offsets) is the most common
non-Boolean structure in the systems the study migrated: VCh-rf positions,
OLSQ time steps, DPQA coordinates, Pusharoo values, TSN and MiniMalloc
offsets, CoCoMoT step indices. Today such a sort is `ExtDOM X: INT` (or
`DefDOM X: INT. Set: lo..hi.`) and is lowered by enumeration: a functional
predicate `x(Q, S, X)` becomes a one-hot choice and every comparison a
grounded relation over the values. The study measured that this lowering
loses by one to two orders of magnitude where three others of the same sort
do not (DPQA, `ports/dpqa/PORT.md`: one-hot 27.7 s, relation 0.5 s,
difference logic 1.1 s, Z3 1.5 s on the same model; timeouts from 14 qubits
against Z3's seconds). The proposal: keep one semantics for the sort and let
the compiler choose between two proved-equivalent lowerings from the model
text: the **basic lowering** (enumeration, the language as it is) and the
**difference-logic extension**. Two further lowerings the study measured
(a relation with transitivity, an order-encoding ladder) and the
acyclicity special case are kept in the appendix as alternatives; they do
not carry the story, and the theorems are stated for the two that do.

Owner's framing (2026-09-23): "basic lowering + dl extension" is the
paper's structure, for the strength of the theorem claims and for the
consistency of the semantics across lowerings. The other language items
from the study (acyclicity construct, default negation, weighted
objectives) need their own lowering mechanisms; Section 10 lists what is
still to be designed on the compiler side so they are not forgotten.

## 2. Syntax

Two additions, both small.

```text
OrdDOM X: 0..15.                 % an order sort with a declared range
Fun x: (Q, S) -> X.              % a total function into it (optional; see 7)
```

- An **order sort** is a bounded integer sort. Its values may occur in a
  model only as arguments of functional predicates into the sort and in
  comparisons of the forms `(op t1 t2)` and `(op (+ t1 c) t2)`, `op` one of
  `= != < <= > >=`, `t1`, `t2` terms of the sort, `c` an integer constant.
  Sums of two sort terms, products, and aggregates over the sort are not
  allowed (they return the sort to `DefDOM`, i.e. enumeration, or are
  rejected; see 6).
- A **functional predicate** into an order sort is a predicate whose last
  argument is of the sort and which is total and single-valued on its other
  arguments. It may be declared with `Fun` or recognised (7).

Existing syntax covers everything else: comparisons already accept
arithmetic terms (language guide, "Formulae"), `?` marks choices, blocks hold
rules and constraints.

## 3. Semantics

Let a model `M` declare finite sorts `S_1..S_n`, order sorts `O_1..O_m` with
ranges `[lo_j, hi_j]`, external and defined predicates, functional predicates
`f_i : S* -> O_j`, rules (positive bodies), choices and constraints.

A **structure** is a pair `(I, v)`: `I` a finite Herbrand interpretation of
the relational predicates over the finite sorts, `v` a valuation assigning to
every ground functional term `f_i(a)` an integer in `[lo_j, hi_j]`. A
comparison atom `(op t1 t2 + c)` holds in `(I, v)` iff `v(t1) op v(t2) + c`.

A **model** of `M` is a structure `(I, v)` such that `I` is a stable model of
the relational part of `M` (rules and choices, under the PCLP semantics of
the paper, Sec. 4) *relative to `v`*: comparison atoms are evaluated by `v`
and are never derived, and every constraint of `M` holds in `(I, v)`.

Two remarks that the study fixed empirically:
- Comparison atoms are constraints, not founded atoms. The alternative
  (founded theory atoms, as in flingo) gave wrong answers on Pusharoo where
  the constraint reading agreed with z3 on 274 of 274
  (`ports/pusharoo/NOTES.md`). This is consistent with the language's
  existing discipline: negation is expressed as choice plus constraint, and
  a comparison in a hypothesis is a choice plus two constraints (5.4).
- Ranges are part of the semantics. All four lowerings agree on the same
  class of models because all respect the range; the unbounded exactness
  that difference logic gave on Pusharoo is a remark about a fifth, relaxed
  reading, not part of this design.

## 4. The lowerings: the core (`L_enum`, `L_rel`), the extension (`L_dl`), and the alternatives

Each `L_k` maps `M` to an ASP program (possibly with theory atoms) such that
the answer sets of `L_k(M) ∪ F`, for a fact file `F`, correspond to the models
of `M` over `F`. Write `f(a) = x` for the functional atom `f(a, x)`.

**L_enum (enumeration, today's lowering).** The order sort is a finite sort
`dom_O(lo..hi)`; `f` is `1 { f(A, X) : dom_O(X) } 1 :- <domain of A>`;
a comparison `(op t1 t2 + c)` is a grounded literal `X1 op X2 + c` in the
rule or constraint where `t1 = f(a) = X1`, `t2 = g(b) = X2` are joined.

**L_rel (relation, core).** No values. For each order sort and each *frame* (5.2)
a chosen binary relation `le_O(e1, e2)` over the ground functional terms `e`
of the sort, with axioms: reflexivity, totality (`le(e1,e2) ∨ le(e2,e1)`),
transitivity (`:- le(a,b), le(b,c), not le(a,c)`), and the range as a bound
on the number of equivalence classes (`:- #count{ e : head(e) } > hi - lo + 1`,
`head(e)` the least element of its class). `eq`, `lt` are derived from `le`.
A comparison `t1 op t2` becomes the derived literal; a comparison with a
non-zero offset `c` is **not** admitted (5.2).

**(Appendix A) L_lad (ladder / order encoding).** For each ground term `e` and each `k` in
`[lo, hi)` an atom `le_k(e)` ("value ≤ k") with `le_k(e) → le_{k+1}(e)` and
`le_hi(e)` true; `t1 <= t2 + c` becomes `∀k: le_k(t2 + c) → le_k(t1)`, i.e.
the clauses `:- le_{k-c}(t2), not le_k(t1)`; equalities as two such.

**L_dl (difference logic).** Each ground functional term is a theory
variable; the range gives `&diff{ e } >= lo` and `<= hi`; a comparison in
a *conclusion* (constraint consequent, or a constraint as a whole) becomes
the theory atom `&diff{ t1 - t2 } <= c` (conditioned on the rule's body); a
comparison in a *hypothesis* is reified (5.4). Backend: clingo-dl.

**(Appendix A) L_edge (acyclicity).** Applicable only when the sort's sole use is one
constraint of the form `∀ a, b. R(a, b) → f(a) < f(b)` for a relation `R`
over the finite sorts (the "positions" idiom of the SMT encodings). The sort
and `f` are dropped and the constraint becomes `#edge (A, B) : R(A, B)`.

## 5. Theorems (statements with proof sketches)

The paper claims T0, T1 and T2 for the core (enumeration and the
relational lowering of the one semantics), T4 for the difference-logic
extension, and T6 for the selection; T3 (ladder) and T5 (edge, with the
inlining lemma of Section 11) remain appendix material.

Notation: `Mod(M, F)` the models of `M` over facts `F`; `AS(P)` the answer
sets of `P`; `π` the projection of an answer set to the relational
predicates of `M` (dropping auxiliaries and lowering-specific atoms).

**T0 (base, existing).** For a model without order sorts, `π` is a bijection
between `AS(L(M) ∪ F)` and `Mod(M, F)`. This is the paper's correspondence
for PCLP (Sec. 4); the lowerings below reduce to it.

**T1 (enumeration).** For any `M`, `AS(L_enum(M) ∪ F)` corresponds to
`Mod(M, F)` bijectively: an answer set's functional atoms `f(a, x)` define
`v`, and the grounded comparisons hold exactly when `v` satisfies them.
*Sketch:* an order sort with range `[lo, hi]` is a finite sort; T0 applies
to the model with the sort declared `DefDOM` and the comparisons as
built-in literals over it.

**T2 (relation).** Let `M` use its order sort `O` only in comparisons
without offsets, and let the elements compared all lie in one frame. Then
`AS(L_rel(M) ∪ F)` corresponds to `Mod(M, F)` *up to the valuation*: every
answer set's `le` is a total preorder with at most `hi - lo + 1` classes,
and the map `(I, le) ↦ (I, v_le)`, `v_le(e) = lo + rank of e's class`, is a
bijection between answer sets and models modulo order-isomorphism of `v`.
*Sketch:* (representation lemma) a total preorder with at most `k` classes
is realised by exactly the valuations into `[lo, lo + k - 1]` that are
order-isomorphic to its rank map; comparisons without offsets depend only on
the preorder, so `(I, v) ⊨ M` iff `(I, le_v) ⊨ L_rel(M)`. The class bound
is the range. (The lemma fails with offsets: `f(a) - f(b) > 2` is not a
property of the preorder. DPQA's AOD columns carry such a constraint and
stayed enumerated in the study's relational form, `dpqa_relorder.lp`.)

**T3 (ladder).** `AS(L_lad(M) ∪ F)` corresponds bijectively to `Mod(M, F)`.
*Sketch:* the ladder atoms of a term `e` with the monotonicity rule encode
exactly one value in the range (`v(e) = min{k : le_k(e)}`); `t1 <= t2 + c`
iff for all `k`, `t2 <= k - c` implies `t1 <= k`; the clauses are that
implication's contrapositive per `k`; equalities and strict forms reduce
to it.

**T4 (difference logic).** `AS(L_dl(M) ∪ F)`, restricted to answer sets
whose theory atoms have a consistent valuation `v` (which clingo-dl
enforces), corresponds to `Mod(M, F)`: the pair (answer set, `v`) maps to
`(π, v)`. *Sketch:* two lemmas. (a) *Reification:* for a comparison `t1 op t2 + c`
occurring in a hypothesis, the three-way choice
`1 { lt(t1,t2); gt(t1,t2); eq(t1,t2) } 1` with the theory atoms
`&diff{t1 - t2} <= c-1 :- lt`, `&diff{t2 - t1} <= -c-1 :- gt`, and both
non-strict differences for `eq`, has, for every valuation `v`, exactly one
consistent branch, the one that agrees with `v`; hence hypotheses evaluate
as under `v`. (b) *Constraints:* a comparison in a conclusion is a theory
atom whose truth under `v` is its truth in `M`. Then the relational part is
the same program as in T0 with comparison atoms fixed by `v`, and T0 gives
the correspondence for each consistent `v`. Founded theory atoms would
break (a): a branch could be "unsupported" although `v` satisfies it.

**T5 (acyclicity).** If `O` occurs in `M` only in the single constraint
`∀ a, b. R(a, b) → f(a) < f(b)` with `f` total on its domain and `R` over
finite sorts, then `AS(L_edge(M) ∪ F)` corresponds to `Mod(M, F)` up to the
valuation. *Sketch:* a total function into a bounded order with
`R(a, b) → f(a) < f(b)` exists iff `R` (as derived in the answer set) is
acyclic and its longest path has fewer than `hi - lo + 1` edges; for the
ranges the study met (positions over all events) the second condition is
vacuous, and the design adds it as a side condition of applicability (range
at least the number of ground terms of `f`'s domain). `#edge` enforces
acyclicity of the chosen `R` exactly.

**T6 (selection).** If the applicability condition of `L_k` (6) holds for
every order sort of `M`, then `L_k(M)` is a correct lowering by T1 to T5.
The conditions are syntactic and decided on the model text.

## 6. The selection rule

The core selects `L_rel` for an order sort whose uses are plain
comparisons between its terms, and `L_enum` otherwise (values as arguments
of relations over the sort, sums of two values, products, aggregates).
With the extension enabled, a sort that `L_rel` refuses because a
comparison carries an offset, a constant or a distance is retried as
`L_dl`, and a sort `L_dl` refuses because a comparison is not a difference
constraint (a sum of two values after an offset elsewhere) falls to
`L_enum`; each retry is strictly weaker, so the chain is rel, dl, enum (`auto` in `lowering/lower.py`;
`--order-lowering X=dl` forces the theory for one sort). The rule decides
on the model text alone, so it prefers the theory-free lowering wherever
it applies and uses the theory only where the relation cannot express the
comparison; it does not see the frame size, which is a property of the
fact file, and the DPQA one-file table (`ports/dpqa/run-ordsorts`) is the
measurement of what that costs where `L_dl` would have been faster.

The full table lists every lowering the study measured, in order of
preference when all conditions were decidable, with the evidence for each;
`L_edge` is not chosen for an order sort but reached through `(\acyclic r)`,
and `L_lad` is kept as an option:

| lowering | condition on the uses of `O` in `M` | evidence |
|---|---|---|
| `L_edge` | one constraint `R(a,b) → f(a) < f(b)`, nothing else; range ≥ domain size; reached through `(\acyclic r)`, whose own lowerings are Section 12.1 | VCh-rf positions: closure in the language 54 s, `#edge` 1.8 s on the largest Cobra polygraph; SI layered acyclicity `ports/isolation/NOTES.md` |
| `L_dl` | comparisons and constant offsets only (any frame, any bound) | DPQA at or ahead of Z3 on five of six graphs from the one-file model (`ports/dpqa/run-ordsorts`, shared Booleans); Pusharoo 274 of 300 exact; TSN ahead of Z3 to 128 streams (`ports/tsn/run-dl`) |
| `L_rel` | comparisons without offsets, elements in one frame, and the frame small (elements ≤ about 100, since transitivity is cubic) | DPQA `run-relorder`: in Z3's band to 18 qubits, 100× one-hot |
| `L_enum` | values are arguments of relations over the sort, or the sort is small and the model is not search-bound | OLSQ time steps (level with the expert, 60 s → 0.4 s against Z3); every domain of the first three weeks |
| (`L_lad`) | never selected by default; kept as an option | DPQA: smaller program, slower search on one thread |

"Frame": the set of ground terms among which the model compares values;
DPQA's sites are one frame across all stages (a site persists), which is
what makes `L_rel` cubic in qubits × stages. A sort with a sum of two of its
terms, or with an aggregate over its values, fails every condition: the
compiler reports it and lowers by enumeration if the range is finite. This
is the boundary the study names as "sums" (MiniMalloc's chains, VCh-rf's
capacity counters, CoCoMoT's edit distance).

Threads are orthogonal: the study's rule (`corpus/parallelism.md`) is to
report 1 and 8 and to try heuristics only where the 8-thread gain exceeds
about three times and the time is in solving.

## 7. Compiler mechanics (implemented 2026-09-23 on branch `order-sorts`)

**Structure (owner's decision, 2026-09-23): the pure-ASP lowerings are the
core and are merged; difference logic is an extension** (`setlah.ext.dl`),
since it is a different system (clingo-dl), with its own admissibility
check (the comparison must normalise to `x - y <= c`) and its own runner,
enabled with `--ext dl` (or `SETLAH_EXT=dl`) and never imported otherwise.

- Core (`lowering/order.py`): `enum`, the basic lowering (`dom_S(lo..hi)`,
  each `Fun` as an exactly-one choice, comparisons grounded: T1); `rel`,
  the preorder lowering (T2); and the selection rule `auto` (T6): try the
  relation, retry a sort as `dl` when a comparison needs an offset, a
  constant or a distance and the extension is enabled, else as `enum`;
  a sort whose values occur outside comparisons, in a sum of two values,
  or under multiplication goes to `enum`.
- Extension (`ext/dl.py`): the reified comparison Booleans with their
  `&diff` rules, the ranges as theory bounds, and `run_source` for
  clingo-dl (T4); the CLI's `--backend auto` uses it when `&diff` atoms
  occur. A Boolean's guard is the cube's deterministic literals (external
  predicates, `dom_` atoms, and predicates that non-choice rules derive
  from them, a fixpoint computed in `lower.py`), taken greedily until the
  Boolean's variables are bound; a variable none of them binds gets a
  domain atom. A chosen literal is never a guard: as a binding it
  multiplies the theory rules by its models (TSN's queue choice: 64 copies
  of every isolation rule, s64 from 27 s to 4 s once excluded), and as a
  condition it ties the Boolean's existence to the choice, which cost the
  DPQA model 20x (0.96 s against 19.4 s on the 10-qubit graph at 4 stages
  when `a(Q, S)` guarded the column comparisons).

### First version, as implemented before the split

Implemented: `OrdDOM X: lo..hi.` and `Fun f: (S1, ..., Sn) -> X.` in the
grammar, AST, transformer and checker (`checker.order_sorts`,
`checker.functions`; `f` is registered as an external predicate of arity
n+1 so models type-check unchanged); `lowering/order.py`, a pass over the
direct lowering's DNF cubes and rule bodies that binds each value variable
to its theory term `f(args)`, drops the functional atom, rewrites every
comparison whose net coefficients are one `+1` and one `-1` (differences of
two values against a constant expression included) into a reified Boolean
`__dl_k(vars)` with `{ __dl_k } :- guards`, `&diff{t1 - t2} <= c :- __dl_k`
and the strict converse under `not __dl_k`, splits `!=` into two cubes,
guards argument variables the remaining literals leave unbound, and emits
the ranges; `transpile.api` appends the theory section verbatim and
provides `run_clingodl_source`; the CLI's `--backend auto|clingo|clingo-dl`
runs clingo-dl when `&diff` atoms are present and prints the valuation.
Rejected with a message: negated functional atoms, a value used as an
ordinary predicate argument or in an aggregate, sums of two values,
products, a `Fun` defined by a rule. Tests: `tests/test_order_sorts.py`
(strict order on a chain and a cycle; the DPQA placement model of the
study at 3 and 4 stages). Measured (graphs 10 to 20 at 4 stages, one thread, seconds; the study's
hand-written clingo-dl program and the tool's Z3 for comparison):

| graph | compiled model | hand-written clingo-dl | DPQA's Z3 |
|---|---|---|---|
| 10 | 0.96 | 1.07 | 1.4 |
| 12 | 2.4 | 1.4 | 19.6 |
| 14 | 4.7 | 3.7 | 5.4 |
| 16 | 13.3 | 3.6 | 6.0 |
| 18 | 27.3 | 3.5 | 10.2 |
| 20 | 41.2 | 68.9 | 56.0 |

Same verdicts on every stage count. The compiled program reifies one
Boolean per comparison site (48 sites, 104 theory rules for this model)
where the hand-written one shares a three-way choice per compared pair
and axis, which is why it is slower at 16 and 18 qubits; sharing reified
atoms across sites with the same pair of terms is the first optimisation
to make (Section 8).

Also implemented (same day): the **relational lowering** `L_rel` as a
second lowering of the same model, selected per sort with
`--order-lowering rel` or `X=rel,C=dl` (default `dl`, environment
`SETLAH_ORDER_LOWERING`): one total preorder `__le_S` per order sort over
the function terms of the sort (`__el_S(f(A..))`, reflexivity, totality,
transitivity, and the range as a bound on the number of preorder classes
through `__head_S`), comparisons without offsets rewritten to `__le_S`
literals (`<` as `le` and `not le` of the converse, `==` as both, `!=` as
two cubes); comparisons with offsets, with constants, or between sorts are
rejected for a relational sort with a message naming the difference-logic
lowering. The two lowerings mix within one program (the DPQA test lowers
the sites relationally, one preorder per axis, and the AOD columns, which
carry the crowding distance, in difference logic): graphs 10 to 20 at 4 stages in
1.8, 157, 2.7, 11.1, 21.9 s and unknown at 600 s (all-dl: 0.96, 2.4, 4.7,
13.3, 27.3, 41.2; hand-written relational: 0.6, 28.7, 11.9, 57.2, 72.9 s
and a timeout at 20), same verdicts wherever decided: the mixed form is
in the hand-written relational form's band and faster on the larger
graphs, with the portfolio variance of the 12-qubit instance. So the owner's question is answered in the
compiler: the fast propositional form and the theory form are two
lowerings of one source, and the selection is a flag. The default is the
selection rule itself (`--order-lowering auto`): every order sort is
tried relationally first and retried in difference logic only when one of
its comparisons carries an offset, a constant or a distance (owner's
principle, 2026-09-23: the theory is not applied where it is not needed);
the DPQA test checks that the default yields `X=rel, Y=rel, C=dl`.

Reified Booleans are guarded by the cube's own binding literals rather
than by domain products (2026-09-23, after the TSN source model grounded
`dom_N`³ for the constant-side variables): `{ __dl_k(S, L2, L1, TT, PR, SY) }
:- hop(S, L1, L2), ttrans(S, TT), lproc(L2, PR), lsync(L2, SY).`

Not yet: inference of `Fun` from the exactly-one pattern, sharing reified
atoms across sites (dl) and splitting a sort's preorder by comparison
classes (rel), and the Lean binding.

### Original plan

1. **Recognise functional predicates.** The existence-plus-uniqueness
   pattern that the compiler already fuses into `1 { f(A, X) : dom(X) } 1 :- ...`
   (with the B16 guard rule) identifies `f` as total and single-valued on
   its domain; `Fun` makes it explicit. Only functional predicates into order
   sorts are lowered specially; an order sort that appears as a relation's
   argument otherwise forces `L_enum`.
2. **Classify the uses of each order sort** (6): walk comparisons; record
   offsets, frames, sums, aggregate occurrences, and the acyclicity idiom.
3. **Lower per sort.** `L_edge` drops the sort and emits `#edge`; `L_dl`
   replaces `f(A, X)` by the theory variable `f(A)`, emits range atoms,
   turns comparisons in conclusions into `&diff` atoms conditioned on the
   rule body, and reifies comparisons in hypotheses (T4a) with one three-way
   choice per compared pair; `L_rel` emits the preorder choice and axioms
   per frame and rewrites comparisons to `le/eq/lt` literals; `L_enum` is
   the current path.
4. **Backend.** `L_dl` programs run under clingo-dl (`python -m clingodl`
   or the C API); the CLI gains `--backend clingo-dl` and selects it when a
   `&diff` atom is emitted. The study's manual attachments
   (`ports/dpqa/dpqa_dl.lp`, `corpus/tools/smt2dl.py` output,
   `ports/isolation` `#edge` lines) are the expected output of steps 3 and 4
   and become regression tests: same verdicts, same order of time.
5. **Overrides.** `--order-lowering SORT=enum|rel|ladder|dl|edge` for
   measurement; the paper's tables come from running all applicable
   lowerings on the same models.

## 8. Open decisions

- `Fun` explicit or inferred only. Inference is what the study relied on
  (the fusion), explicit is what a reader of the model wants. **Decision
  (owner, 2026-09-23): explicit `Fun` declarations only for now; inference
  from the exactly-one pattern is a later convenience, not part of the
  paper's semantics.**
- Whether `L_dl` may drop the range when the model never mentions the
  bounds (Pusharoo's unbounded exactness). **Decision (owner, 2026-09-23):
  ranges are semantics; every lowering respects the declared range, and
  the four lowerings are equivalent on the same class of models.** An
  unbounded variant, if ever wanted, is a distinct sort (`OrdDOM X: INT.`)
  admitting only `L_dl`, outside the paper.
- Whether to keep `L_lad` in the compiler at all (never selected). Proposal:
  keep behind the override for the paper's table, not in the rule.
- Reification cost of `L_dl` is quadratic in compared pairs per frame; the
  study never met a model where that was the wall (DPQA 24 atoms, TSN pairs
  from the query), but the rule should say so.

## 9. What the study will supply

One table per theorem from existing runs: T1/T2/T4 on DPQA (`ports/dpqa/PORT.md`,
five forms), T4 on Pusharoo (`ports/pusharoo/results/clingodl_differential.tsv`)
and TSN (`ports/tsn/run-dl`), T5 on Cobra and VCh-rf (`ports/isolation`,
`ports/vch-rf`), and the negative side of T2 (DPQA's AOD columns) and of
the selection rule (MiniMalloc, `ports/minimalloc/NOTES.md`).


## 10. Still to be designed on the compiler side (lowering mechanisms for the other study items)

The order sort is one of five language items the study produced
(`setlah` `TODO.md`, "Language items from the applications study"). The
lowering mechanism of each of the others is not yet designed; listing them
here so the extension work does not leave them behind:

- **Acyclicity as a construct: implemented 2026-09-23.** `(\acyclic R)` for a
  derived, chosen or external relation `R`; lowering `#edge (X, Y) : R(X, Y).`,
  and for arity 2k `#edge ((X0,..), (Y0,..)) : R(...)` with k-tuples as nodes
  (the SI layered form). A relation defined only by deterministic, projection-free rules (every body
  variable in the head) and used nowhere else is not materialised: one `#edge`
  per defining rule with the rule body as condition; a projecting rule keeps
  the relation, since the propagator would otherwise see one edge per binding
  of the projected variables (Cobra: 3.5 s against 1.9 s) (the layered SI form then is exactly the three
  `#edge` statements the study attached by hand, measured 2.4 times faster
  than grounding the 4-ary relation first). Tests `tests/test_acyclic.py`. Semantics: `R`'s transitive closure is
  irreflexive; equivalent to the existence of a strict order extending `R`
  (T5's argument), which is the connection to order sorts. Four domains
  attached it by hand.
- **Default negation in rule bodies.** Proposed: stratified `\neg p(...)` in
  rule bodies only when `p` is not defined through the rule's own head
  (a stratification check in the safety checker, which already has an
  order-sensitivity defect, B6, to fix on the way). Lowering: clingo `not`.
  Evidence: the deadlock port's `fthread` pre-pass fact, OLSQ's frame rule.
- **Weighted objectives.** Proposed: `(\minimize (sum_{X} w(X) : p(X)))` or
  a block-level `Minimize p weighted by w.`; lowering to `#minimize { W,X :
  p(X), w(X,W) }` with priorities as a second component. Evidence: CoCoMoT,
  Mockdown, DiMage.
- **Cost tables (functions of finite arguments to integers).** Already
  expressible as external predicates; document the idiom rather than add
  syntax; sums over them remain outside (Section 6).
- **Reified-atom sharing across sites (implemented 2026-09-23).** One Boolean
  per comparison up to the names of its variables, not per site: sites whose
  comparison canonicalises to the same `(x, y, c)` share the Boolean, each
  adding its own guard rules once, and a comparison with a numeric bound
  whose complement is already shared uses the complement. With it the
  compiler emits, for DPQA, the 14 Booleans of the hand-written program
  instead of 48. Between shared Booleans over the same pair of terms the
  compiler also emits the exclusion `:- b1, b2` when their bounds cannot
  both hold (`x - y <= c1`, `y - x <= c2`, `c1 + c2 < 0`), the propositional
  half of the hand-written program's exactly-one over less, greater and
  equal, sound wherever both atoms exist; the implication between two bounds
  of the same orientation is not emitted, since as a constraint it would be
  unsound where the weaker atom has no guard. Measured on the 12-qubit graph
  at 4 stages: 71.8 s per site, 23 s shared, 9.8 s shared with the lemma
  (`--propagate=full` gives 2.0 s to the shared program without the lemma:
  the lemma is what the theory's full propagation would find).
  The full DPQA table on this snapshot (`ports/dpqa/run-ordsorts` of the
  applications study): the theory lowering 0.5, 10.0, 2.2, 8.8, 9.8 and
  19.6 s on graphs 10 to 20 against Z3's 1.4, 19.6, 5.4, 6.0, 10.2 and
  56.0 s and the hand-written program's 68.9 s on the largest; before
  sharing it was 1.3, 71.8, 2.9, 4.9, 47.4 s and a timeout.
- **One-way reification for constraint-only comparisons.** A comparison
  that occurs only under constraints (never in a rule body that derives
  something, never enumerated) needs only the direction "Boolean false
  implies the comparison"; the converse rule, which makes the Boolean
  faithful, can be dropped without changing satisfiability (each model of
  `M` still has a stable model, and every stable model still satisfies the
  constraint). TSNKit's dumped queries use this form for their disjunctions
  and are 1.4x faster at one thread on 128 streams than the faithful form
  (318 s against 436 s), while the faithful form is ahead to 64 streams and
  at eight threads (48 s against 201 s). Not applied: T4 is stated for the
  faithful form, and the one-way form loses the one-to-one correspondence of
  answer sets and models (a Boolean may be true while its comparison holds).
  Candidate for a polarity-aware option with its own lemma.
- **Nullary functions (`Fun t: () -> T`).** A query's integer variables are
  constants of the sort; the grammar requires at least one argument sort, so
  the Pusharoo port declares a unit sort `One` with one element and writes
  `Fun t: (One) -> T`, `t(X, V)` with `one(X)` as the guard. Allowing the
  empty argument list is a grammar and lowering change of a few lines
  (enumeration: `1 { t(V) : dom_T(V) } 1.`; theory: the variable `t`).
- **Theory propagator interface (LRA).** Out of the paper's core; record as
  future work with Mockdown's oracle loop as the evidence.

The difference-logic extension is the first of these to be implemented
because its theorem is the paper's and its evidence is the strongest; the
acyclicity construct is the second because it is a one-line lowering with
four domains of evidence.

## 11. Proofs, against the implementation (draft, 2026-09-23)

Conventions. `M` is a model with finite sorts, order sorts `O` with ranges
`[lo_O, hi_O]`, and functions `f : S_1 × … × S_n → O` declared by `Fun`.
`F` is a set of facts over the external predicates and the finite sorts'
domains `dom_S`. `Rel(M)` is `M` without its order sorts: the relational
rules, choices and constraints, with every comparison over order-sort
values treated as an atom of a distinguished predicate `cmp_i` (one per
syntactic occurrence, over the occurrence's free variables). The direct
lowering `L_0` of `Rel(M)` is the paper's PCLP lowering, and T0 gives, for
any interpretation `c` of the `cmp_i` atoms as facts, a bijection `π`
between `AS(L_0(Rel(M)) ∪ F ∪ c)` and the models of `Rel(M)` over `F` in
which the `cmp_i` atoms are read from `c`.

A structure `(I, v)` is a model of `M` over `F` iff `I` is a model of
`Rel(M)` over `F` with each `cmp_i` read as the truth value of its
comparison under `v`, and `v` maps every ground `f(a)` into `[lo_O, hi_O]`
(Section 3). Write `c_v` for the interpretation of the `cmp_i` atoms
induced by `v`.

### T1 (enumeration)

`L_enum(M)` adds to `L_0(Rel(M))` the facts `dom_O(lo_O..hi_O)` and, per
function, `1 { f(A, V) : dom_O(V) } 1 :- dom_{S_1}(A_1), …, dom_{S_n}(A_n)`,
and lowers each comparison as the corresponding built-in literal over the
value variables bound by the function atoms in the same cube.

*Proof.* Let `X` be an answer set of `L_enum(M) ∪ F`. The choice rules force
exactly one atom `f(a, x)` per ground `a` with `x ∈ [lo_O, hi_O]`; define
`v_X(f(a)) = x`. In every cube the function atoms are positive literals
whose value variables are thereby bound to `v_X`, and the built-in literal
evaluates to the truth of the comparison under `v_X`; so the cube is
satisfied in `X` iff it is satisfied in `L_0(Rel(M)) ∪ F ∪ c_{v_X}` with the
same relational atoms. Hence the restriction `π'(X)` of `X` to the
relational atoms is an answer set of `L_0(Rel(M)) ∪ F ∪ c_{v_X}` (the
function atoms are choice atoms constrained only by the exactly-one rule,
so they do not affect foundedness of the rest), and by T0 `(π(π'(X)), v_X)`
is a model of `M`. Conversely a model `(I, v)` yields the answer set
`L_0`-image of `I` plus the atoms `f(a, v(f(a)))`, which satisfies the
exactly-one rules and every cube. The two maps are inverse. ∎

### T2 (relation)

Let `O` be an order sort of `M` such that every comparison over `O` is
between two function terms of `O` with no offset (`t_1 op t_2`,
`op ∈ {=, ≠, <, ≤, >, ≥}`). `L_rel(M)` (for `O`; other sorts as they are)
adds the element facts `el_O(f(a))` for every ground function term, the
choice `{ le_O(e_1, e_2) }` over pairs of distinct elements, reflexivity
`le_O(e, e)`, totality `:- el(e_1), el(e_2), e_1 < e_2, not le(e_1, e_2),
not le(e_2, e_1)`, transitivity `:- le(e_1,e_2), le(e_2,e_3), not le(e_1,e_3)`,
the class bound `:- #count{ e : head(e) } > hi_O − lo_O + 1` with
`head(e) :- el(e), #count{ e' : le(e, e'), le(e', e), e' < e } = 0`, and
lowers `t_1 ≤ t_2` to `le(t_1, t_2)`, `t_1 < t_2` to `le(t_1, t_2), not
le(t_2, t_1)`, `t_1 = t_2` to both `le` atoms, and `≠` to the two
alternatives `not le(t_1, t_2)` and `not le(t_2, t_1)` (each in its own
cube; `≥`, `>` by symmetry).

*Lemma (representation).* For a finite set `E` and `k ≥ 1`, the total
preorders on `E` with at most `k` equivalence classes are in bijection with
the sets `{ v : E → [lo, lo+k−1] }` modulo order-isomorphism (i.e. two
valuations are identified when they induce the same `≤` on `E`), the
bijection sending `v` to `e_1 ≼ e_2 ⟺ v(e_1) ≤ v(e_2)` and a preorder to
its rank map `v(e) = lo + (number of classes strictly below e's class)`.
*Proof.* A total preorder's classes are linearly ordered; the rank map is a
valuation with the same induced `≼`, and any valuation inducing `≼` is
order-isomorphic to it. The number of classes is the number of distinct
values, hence at most `k` iff a valuation into `k` values exists. ∎

*Proof of T2.* Let `X` be an answer set of `L_rel(M) ∪ F`. The totality and
transitivity constraints and reflexivity make `le_X` a total preorder on
the ground elements; `head` marks the least element of each class (the
`#count` is zero exactly for the element with no smaller-indexed member of
its class), so the class bound holds iff the preorder has at most
`hi_O − lo_O + 1` classes. By the lemma there is a valuation `v_X` into
`[lo_O, hi_O]` inducing `le_X`; each lowered comparison holds in `X` iff the
comparison holds under `v_X` (for `≤`, `<`, `=`, `≠` by the definitions, since
they mention only the induced order). So the relational part of `X` is an
answer set of `L_0(Rel(M)) ∪ F ∪ c_{v_X}` and `(π, v_X)` is a model of `M`.
Conversely a model `(I, v)` gives the answer set with `le` the preorder
induced by `v` (choice atoms constrained only by the axioms), which
satisfies the class bound because `v` takes at most `hi_O − lo_O + 1` values.
The correspondence is a bijection up to order-isomorphism of `v`, which is
the statement. Offsets break the lemma's premise: `t_1 + c ≤ t_2` is not
determined by the induced preorder (the applicability condition). ∎

### T4 (difference logic, as implemented)

Let `O` be an order sort of `M` all of whose comparisons normalise to
`x − y ≤ c` (`x`, `y` function terms of `O` or absent, `c` a constant
expression over non-order variables), including differences of two values
against a constant. `L_dl(M)` adds, per ground function term, the theory
atoms `&diff{ f(a) } ≤ hi_O` and `≥ lo_O`, and lowers each comparison
occurrence `i` with free variables `z` (the function terms' arguments and
the constant's variables) to a Boolean `b_i(z)` with the rules
`{ b_i(z) } :- guards(z)`, `&diff{ x − y } ≤ c :- b_i(z)`, and
`&diff{ y − x } ≤ −c−1 :- not b_i(z), guards(z)`; `=` becomes two such
Booleans in one cube, `≠` two alternatives, and the cube's literal is
`b_i(z)` or `not b_i(z)`.

*Lemma (reification).* For every valuation `v` of the theory terms and every
ground `z`, exactly one of `b_i(z)` true, `b_i(z)` false is consistent with
the theory atoms it triggers, namely the one equal to the truth of
`v(x) − v(y) ≤ c` under `v`. *Proof.* If `v(x) − v(y) ≤ c` then the atom
triggered by `b_i` true holds and the one triggered by `b_i` false,
`v(y) − v(x) ≤ −c−1`, i.e. `v(x) − v(y) ≥ c+1`, fails; symmetrically
otherwise. ∎

*Proof of T4.* clingo-dl's answer sets are the answer sets `X` of the
program in which the set of triggered theory atoms has a consistent
valuation `v_X` (the propagator rejects the others). By the reification
lemma the truth of every `b_i(z)` in `X` equals the truth of the
corresponding comparison under `v_X`, and by the range atoms `v_X` maps
into `[lo_O, hi_O]`. So the relational part of `X` is an answer set of
`L_0(Rel(M)) ∪ F ∪ c_{v_X}` and `(π, v_X)` is a model of `M`. Conversely,
for a model `(I, v)`, set every `b_i(z)` to the truth of its comparison
under `v`; the triggered theory atoms are then exactly the true ones,
consistent with `v`, and the program's answer set is the `L_0`-image of `I`
plus those Booleans. The map (answer set, `v_X`) ↦ `(π, v_X)` is a bijection
onto the models, with `v_X` determined only up to the theory's freedom on
terms no comparison mentions (a remark, not a gap: such terms are
unconstrained in `M` as well). The `Fun` atoms disappear from the cubes
because their only role, binding the value variable, is taken by the term
substitution; their argument variables are bound by the cube's other
positive literals or by the domain guards the pass adds. ∎

Founded theory atoms (flingo) would break the reification lemma: `b_i`
false with `&diff{ y − x } ≤ −c−1` unsupported could be accepted although
`v` violates it. The constraint reading is the one the study validated
(Pusharoo, 274 of 274 against z3).

### T6 (selection, as implemented)

`auto` lowers a sort by `L_rel` if no comparison over it raises the
applicability failure of T2 (an offset, a constant, a distance), otherwise
by `L_dl` when the extension is enabled and every comparison normalises to
a difference constraint, otherwise by `L_enum`; a sort whose values occur
outside comparisons, in a sum of two values, or under a product, goes to
`L_enum`. Each branch's condition is the hypothesis of T2, T4 or T1
respectively, decided syntactically during the lowering (the failures are
raised by the pass and the sort is re-lowered), and the theorems compose
because each sort's lowering is independent of the others' (a comparison
never mixes sorts, by the checker). ∎

### What T5 adds (appendix)

`(\acyclic r)` lowered to `#edge` is correct by the definition of clingo's
propagator (an answer set is accepted iff the chosen edges are acyclic);
the connection to order sorts is that a strict total order `f` with
`r(a, b) → f(a) < f(b)` exists iff `r` is acyclic and its longest path is
shorter than the range, so the "integer positions" encoding of the SMT
baselines is `L_enum` or `L_dl` of a sort whose only use is that constraint,
and `#edge` is the lowering that drops the sort.

*Inlining lemma.* Let `r` be defined only by rules `r(t_i) :- B_i` (no
choice, no negation, `r` in no other head) and occur nowhere else in the
program. In every stable model `M`, `r^M = ∪_i { t_i σ : B_i σ ⊆ M }`, since
`r`'s atoms are supported only by these rules and constrain nothing else.
Hence `#edge (t_i) : B_i.` for each `i` denotes the same edge set as
`#edge (X, Y) : r(X, Y).` and the two programs have the same stable models.
The compiler takes the inlined form only when every variable of `B_i`
occurs in `t_i`: then each edge is presented to the propagator once, as in
the materialised form; a projecting rule presents it once per binding of
the projected variables, which is correct and can go either way: slower on
Cobra (`edge(A, B) :- pick(C, K), alt(C, K, A, B)`, 3.5 s against 1.9 s)
and mixed on VCh-rf (`hbc(X1, Y1) :- hb(X, Y), rep(X, X1), rep(Y, Y1),
X1 != Y1`: 13 s against 167 s on `hugo_main_5000`, but two to three times
slower on the other large instances, 47 s against 20 s on the next
slowest, measured with `--acyclic-inlining hbc=all` on an idle machine).
The compiler takes the form that is never worse by much, and
`--acyclic-inlining auto|all|none` (per relation: `hbc=all`; env
`SETLAH_ACYCLIC_INLINING`) overrides it; a cost model over the multiplicity
of the projected variables would make the choice automatic. The three layered rules of the
snapshot-isolation model are projection-free and their inlined form matches
the hand-attached program.

## 12. Lowerings in the plural: per feature and per solver (2026-09-26)

Owner's framing: the order sort is not the only construct that admits
several lowerings. A SetLah! program has many compilations, and the
compiler should be able to try them all: a program without recursion can
go to SAT, one without choice to Datalog, and acyclicity has, besides
`#edge`, the transitive closure as rules and the integer positions of the
SMT baselines, or MonoSAT's graph theory. Two axes, then: **feature-level
lowerings** (how a construct becomes rules) and **solver-level lowerings**
(which system decides the rules). Every baseline the study beat or lost to
is one cell of this matrix, produced by hand; the compiler now produces
the cells from one model text.

### 12.1 Acyclicity: three feature-level lowerings

`(\acyclic r)`, `--acyclic-lowering edge|closure|positions` (per relation
`r=closure`; env `SETLAH_ACYCLIC_LOWERING`):

| lowering | emitted | correctness |
|---|---|---|
| `edge` (default) | `#edge (X, Y) : r(X, Y).` (k-tuple nodes for arity 2k; projection-free defining rules inlined) | clingo's propagator accepts an answer set iff the chosen edges are acyclic (T5) |
| `closure` | `__tc_r(X, Y) :- r(X, Y). __tc_r(X, Z) :- __tc_r(X, Y), r(Y, Z). :- __tc_r(X, X).` | `__tc_r` is the transitive closure of `r` in every stable model (least fixpoint of positive rules), and `r` is acyclic iff its closure is irreflexive |
| `positions` | `OrdDOM Pos_r: 0..N. Fun pos_r: (S..) -> Pos_r.` and the constraint `r(a, b) -> pos_r(a) < pos_r(b)`, then the order-sort lowering of `Pos_r` (`dl` when the extension is enabled, else `enum`; `--acyclic-range N`, default 2^24) | a strict order with `r(a, b) -> f(a) < f(b)` exists iff `r` is acyclic and its longest path is shorter than `N` (T5's argument); the sort is then lowered by T4 or T1 |

The `positions` rewrite runs on the AST after the first semantic check and
re-checks; the node sorts are the relation's argument sorts (an unknown
sort, as the layer constants of the snapshot-isolation relation, leaves the
range atoms ungrounded, which is the relaxed unbounded reading, still
correct for acyclicity). The guard problem it raised: the reified Boolean
of `pos_r(a) < pos_r(b)` may not be guarded by `r(a, b)` when `r` is
derived from a choice (Section 7), and guarding it by the domains gives one
Boolean per pair of nodes (1.5 M on a 1,243-transaction polygraph). The
compiler therefore computes, for every predicate defined by rules whose
truth depends on a choice, a deterministic over-approximation `__may_p`:
one rule per defining rule, deterministic body literals kept, a
non-deterministic defined literal replaced by its own `__may_`, comparisons
dropped, unbound head variables guarded by their domains. `p ⊆ __may_p` in
every answer set, so `__may_p` is a sound guard, and on Cobra it is
`__may_edge(A, B) :- __may_pick(C, K), alt(C, K, A, B)`: one Boolean per
candidate edge, the SMT baseline's encoding exactly.

### 12.2 Solver-level lowerings: SAT and MonoSAT as extensions

`--backend sat|monosat` (`setlah.ext.ground`, `setlah.ext.sat`,
`setlah.ext.mono`). The compiled ASP program is grounded by clingo's
grounder and captured through the observer interface (normal and choice
rules, weight rules from aggregates, `#edge` conditions, output symbols);
Clark's completion turns it into clauses; cardinalities become sequential
counters (pysat) in both directions (`h <-> #true >= k`); the clauses go to
a SAT solver (cadical through pysat) or to MonoSAT, where every `#edge`
becomes an edge of one graph whose literal is equivalent to the edge's
condition, under the `acyclic` predicate. A program that is not tight
(a positive cycle through the ground rules), has an objective, a theory
atom or a disjunctive rule is refused with the reason; plain SAT also
refuses `#edge` (no compact propositional acyclicity; the positions or
closure lowering is the way to it, and the closure is not tight).

**T7 (completion).** For a tight ground program `P` (no cycle in the
positive dependency graph, choice bodies counted as positive dependencies),
the models of `Comp(P)` restricted to the atoms of `P` are exactly its
stable models (Fages 1994; Erdem and Lifschitz 2003 for the extension to
choice and weight rules, which the encoding treats as: a choice rule's head
atom is supported by its body without being forced, a weight rule's head is
equivalent to the cardinality of its body). The auxiliary variables for
conjunctive bodies and cardinalities are definitional, so the restriction
is a bijection. *Proof of the encoding's fidelity.* For each atom `a`,
`Comp(P)` has `a <-> ∨_i B_i` over its rule bodies; the encoder emits
`b_i <-> ∧ B_i` (or the single literal), `b_i -> a` for the normal rules,
and the support clause `¬a ∨ ∨ b_i ∨ ∨ c_j` where `c_j` are the choice
bodies (`c_j -> a` is not emitted, which is the choice); an atom with a
fact rule is a unit clause, one with no rule is false; a constraint is the
clause of its negated body; a weight rule's head `h` gets `h <-> Σ ≥ lb`
through `atleast` conditioned on `h` and `atmost(lb − 1)` conditioned on
`¬h`. Each clause set is the definition of the corresponding formula of
`Comp(P)`. ∎

**T8 (edges).** `AS(P ∪ E)`, `E` a set of `#edge (u, v) : B` directives,
equals the stable models `X` of `P` in which `{(u, v) : B ⊆ X}` is acyclic
(clingo's definition of the propagator). MonoSAT with `e_uv <-> ∧ B` for
each directive and `acyclic(G)` asserted accepts exactly the assignments in
which the true edges form an acyclic graph, which is the same set. ∎

Composition: with T7 for the Boolean part and T8 for the edges, the
MonoSAT backend decides exactly the stable models of the compiled program
with `#edge`; the SAT backend those of a program without `#edge`.

### 12.3 What is measured (applications study, 2026-09-26)

The four acyclicity domains under `edge`, `closure`, `positions` (with the
dl extension) and MonoSAT; the recursion-free benchmarks (EPR queries of
DuoAI and mypyvy, TPTP's decided problems, OLSQ, DPQA's enumerated and
relational lowerings, Pusharoo's enumerated queries) under clingo and the
SAT backend from the same compiled program. Results in the study's notes
(`ports/*/NOTES.md`, "Lowerings in the plural") and its dossier. First
rows: Cobra's 65 polygraphs, `closure` 65 of 65 identical with 54.5 s on
the largest (the hand-measured figure reproduced) against 1.81 s for
`edge`.

### 12.4 Not done, and why

- **Datalog as a target.** A choice-free stratified program has one
  model, which a Datalog engine computes; the study's one use is the
  saturation pre-pass of VCh-rf, where the closure computed outside the
  grounder took the arm from 39 of 56 to 56 of 56 (as facts from the
  artifact's own saturation). Emitting the choice-free fragment to a
  Datalog engine is a day's work with that one datapoint behind it.
- **Positions under plain SAT.** The order encoding (`L_lad`, appendix) is
  the lowering that makes positions propositional in O(N) per node and
  per edge; it is not implemented (the enumeration is one-hot and
  quadratic), so the SAT backend's acyclicity route is MonoSAT.
- **Non-tight programs to SAT** need loop formulas (ASSAT) or a CEGAR
  loop; out of scope, the ASP backend is the general one.
