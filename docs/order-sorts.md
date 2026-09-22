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

## 4. The two lowerings (and, in the appendix, the alternatives)

Each `L_k` maps `M` to an ASP program (possibly with theory atoms) such that
the answer sets of `L_k(M) ∪ F`, for a fact file `F`, correspond to the models
of `M` over `F`. Write `f(a) = x` for the functional atom `f(a, x)`.

**L_enum (enumeration, today's lowering).** The order sort is a finite sort
`dom_O(lo..hi)`; `f` is `1 { f(A, X) : dom_O(X) } 1 :- <domain of A>`;
a comparison `(op t1 t2 + c)` is a grounded literal `X1 op X2 + c` in the
rule or constraint where `t1 = f(a) = X1`, `t2 = g(b) = X2` are joined.

**(Appendix A) L_rel (relation).** No values. For each order sort and each *frame* (5.2)
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

The paper claims T0, T1 and T4 (basic lowering, difference-logic extension)
and T6 for the selection; T2 is now implemented as well (`L_rel`, the
same model lowered relationally) and can stand in the paper as the second
lowering if the story prefers a pure-ASP alternative to the theory; T3 and
T5 remain appendix material.

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

## 6. The selection rule (paper version: two lowerings)

The compiler uses `L_dl` for an order sort whose uses are comparisons and
constant offsets only, and `L_enum` otherwise (values as arguments of
relations over the sort, sums, aggregates). The full table below records
the alternatives and the evidence for each; only the first two rows and the
`L_enum` row are in the paper's rule.

For each order sort `O` of `M`, in this order, choose the first lowering whose
condition holds:

| lowering | condition on the uses of `O` in `M` | evidence |
|---|---|---|
| `L_edge` | one constraint `R(a,b) → f(a) < f(b)`, nothing else; range ≥ domain size | VCh-rf positions: closure in the language 54 s, `#edge` 1.8 s on the largest Cobra polygraph; SI layered acyclicity `ports/isolation/NOTES.md` |
| `L_dl` | comparisons and constant offsets only (any frame, any bound) | DPQA level with Z3 on all six graphs (`ports/dpqa/run-dl`); Pusharoo 274 of 300 exact; TSN ahead of Z3 to 128 streams (`ports/tsn/run-dl`) |
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

## 7. Compiler mechanics (implemented 2026-09-23 on branch `order-sorts`, first version)

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
lowerings of one source, and the selection is a flag.

Not yet: the enumeration fallback (a sort failing the conditions is an
error today, not a `DefDOM` lowering), the `L_edge` special case, inference
of `Fun` from the exactly-one pattern, sharing reified atoms across sites
(dl) and splitting a sort's preorder by comparison classes (rel), and the
Lean binding.

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

- **Acyclicity as a construct.** Proposed syntax `(\acyclic R)` for a derived
  or chosen binary predicate `R` (or an `Acyclic R.` declaration); lowering
  `#edge (X, Y) : R(X, Y).` with tuple node terms allowed (the SI layered
  form needs `((X,0),(Y,1))`). Semantics: `R`'s transitive closure is
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
- **Theory propagator interface (LRA).** Out of the paper's core; record as
  future work with Mockdown's oracle loop as the evidence.

The difference-logic extension is the first of these to be implemented
because its theorem is the paper's and its evidence is the strongest; the
acyclicity construct is the second because it is a one-line lowering with
four domains of evidence.
