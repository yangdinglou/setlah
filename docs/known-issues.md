# Known Issues

Compiler defects found by compiling third-party finite-domain problems with
SetLaH: verification queries from DuoAI (OSDI 2022) and mypyvy (CAV 2024),
and Alloy commands translated by PORTUS. Each entry has a minimal `.sl`
program under `tests/inputs/regressions/` that reproduces it on its own.

Reproduce with `setlah tests/inputs/regressions/<file>.sl [facts.lp] --print-asp`.

| id | symptom | exit | severity | status |
|---|---|---|---|---|
| [B1](#b1) | crash: `Expected Literal(atom, sign), got Literal.AuxCall(...)` | 1 | blocker | **fixed** |
| [B2](#b2) | `:- % raw-constraint ...` in the output | 0 | wrong output | partly fixed |
| [B3](#b3) | unsafe auxiliary rule; Clingo rejects the program | 0 | wrong output | **fixed** |
| [B4](#b4) | a body atom loses its arguments | 0 | wrong output | open |
| [B5](#b5) | large models cannot be compiled at all | 1 | limitation | **fixed** |
| [B6](#b6) | safety check rejects sound recursive and equality-bound rules | 1 | limitation | open |
| [B7](#b7) | auxiliary predicate names wrap at five; two unrelated auxiliaries share a name | 0 | **wrong output, silent** | **fixed** |
| [B8](#b8) | an existential with nine or more bound variables fails with `Unsupported VarList: ... subst_varlist` | 1 | crash | **fixed** |
| [B9](#b9) | a PORTUS command compiles whole and cleanly and answers UNSAT where z3 answers SAT | 0 | **wrong output, silent** | open |
| [B10](#b10) | one symmetric uniqueness pair in a block turns every `not X = Y` of the block into `X < Y` | 0 | **wrong output, silent** | **fixed** |
| [B11](#b11) | an auxiliary rule with the body `?`: the program does not parse | 0 | wrong output | open (egglog path); direct lowering unaffected |
| [B12](#b12) | universals that occur in no literal end up as unbound `#count` element variables | 0 | wrong output | open (egglog path); direct lowering unaffected |

Severity: *wrong output* means the compiler exits 0 and the emitted ASP does
not faithfully encode the model, so a caller that trusts the exit code gets a
wrong answer or an unrunnable program. Those are the dangerous ones.

---

## B1. Auxiliary-predicate call survives into rendering {#b1}

**Symptom.** Exit 1 with

```
compile error: Expected Literal(atom, sign), got Call(func=Attribute(
  value=Name(id='Literal'), attr='AuxCall'), args=[Call(func=Subscript(...
```

**Reproducers.**

| file | shape | before | after |
|---|---|---|---|
| `aux_c0_one_witness_ok.sl` | one guarded witness, `exists` over one atom | compiles | compiles |
| `aux_c1_two_witness_crash.sl` (11 lines) | two guarded witnesses, `exists` over two relations | crash | compiles |
| `aux_c2_negated_disjunction_crash.sl` (23 lines) | `not (a or not b)` under two witness guards, no existential | crash | compiles |

**Mechanism.** egglog prints an extracted expression with let-style bindings
before the body, either comma-separated on one line or one per line, and the
first binding follows the tuple's opening parenthesis:

```
(_Formula_1 = Formula.Lit(GeneralLit.from_literal(Literal(Atom.Pred("k_res1", ...), True)))
_VarList_1 = cons_var(Term.Var("K_N1"), cons_var(Term.Var("K_RES1"), nil_var()))
cons_constraint(...)
```

`Rewriter._normalize_cons_list_str` inlines those bindings. It split the
prefix on top-level commas, and there are none here, so the whole prefix
became the value of `_Formula_1`; its line-based fallback parser anchored
names to the start of a line, so it matched neither the first binding (after
`(`) nor any indented one. Substituting that value spliced a binding
*definition* into the middle of the expression:

```
Formula.And(Formula.Lit(...k_res1...))
_VarList_1 = cons_var(...), Formula.Lit(...response_sent, _VarList_1...))
```

From there: the corrupted text no longer parses as Python, so
`_parse_aux_call` returns `None` and no auxiliary rule is generated;
`eval` of the modified string raises `SyntaxError`, which is caught, and the
rewriter falls back to the original extraction — which still contains
`Literal.AuxCall(...)`. The transpiler's own fallback
(`transpile/aux.py::_preprocess_aux_calls`) does not lower it either: it
matches the prefix `GeneralLit.AuxCall(` and expects the three-argument form
`(body_lits, qvars, free_vars)`, while the current schema
(`rewrite/egg_schema.py`) emits `Literal.AuxCall(body_cubes, qvars)`. The
call reaches `transpile/rendering.py::_literal_to_body_lit`, which raises.

**Fix.** `_normalize_cons_list_str` now extracts bindings with a
parenthesis-depth-aware scan (`_parse_binding_prefix`) that accepts both
layouts, an optional leading `(`, and any indentation; a name is a binding
only where it appears at depth 0 followed by `=`. `transpile/aux.py` also
accepts the current two-argument `Literal.AuxCall` form, so a call that
survives the rewriter is still lowered to auxiliary rules instead of
crashing the renderer.

**Impact.** This one defect accounted for every failure of the automatic
migration path on the DuoAI invariant-checking workload, in both of its
shapes -- the crash above and the silent fallback of B2. Compiling the 142
distinct queries of `client_server_db_ae` and comparing each answer with Z3
(unbounded and bounded):

| | before | after |
|---|---|---|
| answers agreeing with Z3 | 30 | **142** |
| wrong answers | 0 | 0 |
| compiler failures | 112 (96 raw, 16 crashes) | **0** |

Mean compile time 5.0 s (max 8.2 s), mean solve time 2 ms. The same
measurement over mypyvy's 792 `updr` queries: 169 answers and 623 failures
before, **792 answers and no failures** after, each agreeing with Z3 (mean
compile 6.5 s, max 41.9 s). That corpus needed B3 as well.

---

## B2. Untranslated constraint emitted as a comment, exit 0 {#b2}

**Symptom.** Exit 0, and the ASP contains

```
:- % raw-constraint Formula.Forall(Term.Var('V_D1'), Formula.Or(...
```

A constraint head followed only by a comment. If it is the last statement
the program is a syntax error at end of file (Clingo: `unexpected EOF,
parsing failed`); if a statement follows, that statement is absorbed as the
constraint's body, which silently changes its meaning. The compiler reports
success either way.

**Reproducers.** `raw_f0_ite_frame_equality.sl` (17 lines) — the frame axiom
exactly as Ivy writes it, `post(V) = ite(V = K, new, pre(V))` under the
witness guards of the action's parameters; exit 0 and a raw-constraint
comment on the fixed compiler. `raw_f1_frame_axiom.sl` — the same axiom,
`forall V. (V = k -> post(V) <-> new) and (V != k -> post(V) <-> pre(V))`.
`raw_f2_forall_exists_forall.sl` — an inferred invariant with a
`forall-exists-forall` prefix. Both used to fall back under every
`--entailment-elim`, `--grounding` and `--cost-conversion` setting.

**Status.** The two reproducers now compile with no raw output, and none
is emitted on the 142-query DuoAI corpus *as pre-normalised by the study's
translator* (frame equalities split disjunction-free, positive existentials
Skolemized into helper rules, universals distributed). Those rewrites were
added to dodge B1; with them switched off (`--plain`), the same 142 queries
as Ivy writes them give **12 compiled and 130 raw fallbacks** on the fixed
compiler. So the fallback is reachable on ordinary input: on the DuoAI sample
bisected assertion by assertion it is one shape, the frame axiom
`post = ite(c, new, pre)` under its universals (`raw_f0_*`, and
`test_b2_ite_frame_equality_is_lowered`, a strict xfail that flips when the
lowering handles it); on mypyvy's 792 queries the plain translation falls
raw on 568. The earlier reading that B1 explained all of it was wrong. The fallback path (`transpile/egg_parsing.py`
gives up, `transpile/constraint.py` prints the formula as a comment) is a
real incompleteness of the lowering, and it exits 0.

**The harness shapes, traced 2026-09-07.** The limits harness
(setlah-apps `ports/setlah-limits/NOTES.md`) found the fallback on five-line
models: one universal implication with a flat conjunctive antecedent over 8
or 11 variables (7, 9, 10, 12, 13 lowered), and nested universal
implications from depth 7. Reproducers `raw_v08_flat_antecedent.sl`,
`raw_v11_flat_antecedent.sl`, `raw_n07_nested_universals.sl`. Extracting the
term after each rewrite phase gave three causes, none of them the cost
tie-break the harness notes guessed at (the zero-cost integrity form always
wins when it exists; it did not exist):

1. `grouped_forall` had producers (`egg_rules.py`, `grouping_quantifiers`)
   and no consumer. `equal_set` flips one quantifier level per iteration
   (`forall x. not f == not exists x. f`, `lec10_fo_A`), and under its
   15-iteration budget and back-off scheduler the chain over 8 levels did
   not always complete (for 7 variables three levels flipped, enough to
   form an `AuxCall` and let the recursive pass finish; for 8, none). The
   grouping in `extraction` did complete, leaving `grouped_forall(vs,
   Not(grouped_and_lit(...)))` with nothing to lower it.
2. The auxiliary rule (`aux_set`) ran once, right after `extraction` had
   spent its 20 iterations under one back-off scheduler, whose bans double
   in length. The grouping chains (one literal, one quantifier level per
   iteration) finish late or not at all under those bans, so for some
   literal counts `aux_set` ran before its input existed. Removing the
   `grouped_forall` producers, as first suggested, fixed 8 variables and
   left 11 and depth 7 raw: it only changed the match counts. Raising the
   budgets, as the harness notes found, does not converge: without the
   scheduler the 8-variable model reaches the integrity form in four
   minutes and the 11-variable one not in ten.
3. `_rewrite_single_constraint` lowers one quantifier level per recursive
   pass and was capped at `max_depth=5` (docstring said 3); with the
   transpiler's one residual auxiliary, nesting stopped at depth 6.

**Fix** (commit `0be936a`, branch `direct-lowering`). An `extraction` rule
`grouped_forall(vs, Not f) -> Not(grouped_exists(vs, f))`, from which the
integrity-constraint, auxiliary and count lowerings all start; the 20
extraction iterations run as four runs of five so the scheduler's bans
reset between them; the aux round repeats up to four times until the term
is an integrity constraint or holds an `AuxCall` (an unchanged extracted
term is not a stopping criterion: the e-graph progresses while the
cheapest representative stays the same); and the recursion cap is a safety
stop at 64. With that every flat (3 to 13 variables), nested (depth 1 to
8) and width model of the harness lowers in 0.4 to 1.8 s, and so do
`raw_f1` and `raw_f2`. Differential on 55 local models: 40 byte-identical,
15 changed only in guard order, blank lines or an equivalent auxiliary
shape, plus the four previously raw ones; answer sets equal on the examples
with instances.

**Still open.** `raw_f0_ite_frame_equality.sl` (Ivy's `post(V) = ite(V = K,
new, pre(V))` under the witness guards) still falls back; the strict xfail
`test_b2_ite_frame_equality_is_lowered` stays. That is the shape behind the
130 of 142 DuoAI and 568 of 792 mypyvy plain-translation fallbacks, and it
is what the direct lowering (Track B of `docs/refactor-brief.md`) is for:
the underlying fragility is a normalisation that needs a chain of n
sequential rewrites inside a budgeted, throttled saturation, which no
schedule makes monotone. The fallback also still exits 0.

**Suggested fix for the rest.** Make the fallback a hard error, so
incompleteness is visible; a caller can then decide. Emitting a comment
where a constraint belongs is never safe, and `exit 0` on it is worse.

---

**Shape datapoint (2026-09-07, TPTP translator).** A universally quantified
disjunction whose members are conjunctions of equalities is lowered only in
the 2-by-2 case; every larger product falls back (exit 0, raw constraint):

| file | shape | result |
|---|---|---|
| `or_of_and_2x2_ok.sl` | `(\or (\and e e) (\and e e))` under `\forall` over 4 variables | compiles, 8 rules |
| `or_of_and_3x2_fallback.sl` | three disjuncts of two equalities | raw fallback |
| (same generator) | 4x2, 2x4, 3x3 | raw fallback |

The TPTP translator works around it by distributing small products (at most
32 clauses) into CNF before emission; larger ones (ALG014+1 has 4x4) stay
untranslatable and count as compile errors in that benchmark.


---

## B3. Unsafe auxiliary rule from a vacuous empty-domain cube, exit 0 {#b3}

**Symptom.** Exit 0; Clingo rejects the output with an unsafe-variable error.

**Reproducer.** `unsafe_u1_empty_domain_cube.sl` (13 lines of block, facts
`unsafe_u1.lp`), delta-debugged from a 61-line query. The shape is an
existential over an implication whose antecedent mentions only the outer
variables:

```
forall D1, N1, RES1. exists REQ1.
    (db_response_sent(D1, RES1) and t(D1, N1)) -> (match(REQ1, RES1) and request_sent(N1, REQ1))
```

**Mechanism.** An auxiliary predicate's arguments are the free variables of
the whole disjunction it replaces, so every one of its rules — one per DNF
cube — carries all of them in the head, including the cubes that do not
mention them. Here the cube for the empty-domain case `not dom_Request(_)`
drops the antecedent, which is the only positive occurrence of `D1`, and
`D1` is then in the head and nowhere positive in the body. Safety guards
were inferred from rule *bodies* only (`transpile/safety.py`), at both call
sites (`transpile/api.py` for the rewriter's auxiliary rules,
`transpile/pipeline.py` for the transpiler's), so a head-only variable was
never guarded.

**Fix.** `_infer_safety_guards` takes the rule head as well, and a head
variable not bound positively in the body is guarded like any other unsafe
variable. Its domain comes from the auxiliary predicate's own inferred
signature, that is from the sibling rule where it *is* bound;
`_extract_aux_pred_types` now merges the signatures across an auxiliary
predicate's rules instead of letting the last rule win, so a cube that
types an argument `UNKNOWN` no longer erases what another rule knows.

**Impact.** On mypyvy's 792 `updr` queries this was the next blocker after
B1: with B1 fixed alone, 41 of the first 62 queries produced a program
Clingo refused to ground; with both fixed, all 792 compile, ground and
agree with Z3.

**Datapoint (2026-09-07, TPTP FNT run, NLP037+1).** A different unsafe
shape from the vacuous-cube one: a source formula with alternating
quantifiers under negation, `forall U. sk(U) -> exists V, W. (table(U,V) and
forall X. (not member(U,X,W) or exists Y. (... forall Z. (... exists X1.
...))))`, compiles (exit 0) to an auxiliary chain in which two heads carry
variables that occur only in negated body literals:

```
__aux_4(U,V,X) :- dom_U(Y), not __aux_3(U,Y,V,X), p_s_three(U,Y), p_s_group(U,Y), not __aux_1(U,Y).
__aux_5(U,W,V) :- dom_U(X), p_s_member(U,X,W), not __aux_4(U,V,X).
```

Clingo rejects the program (`V`, `X` unsafe). Reproducer
`unsafe_aux_negated_existential_tptp.sl` (41 predicates, one constraint);
5 of the 64 NLP problems in the FNT sample fail this way (`GERR`).


---

## B4. A body atom loses its arguments, exit 0 {#b4}

**Symptom.** Exit 0; the emitted ASP contains a rule referring to a relation
with no arguments where the source has a binary atom:

```
__aux_4 :- __aux_1, dom_Sort_scc_event_1(F_112), rmw_0.
```

`rmw_0` is declared as the binary choice `{rmw_0(X0, Y)}`, so the literal
`rmw_0(V_X0_24, F_112)` lost both arguments and the auxiliary chain can never
fire (Clingo: *atom does not occur in any rule head*). The constraint that
should have been enforced is silently vacuous.

**Reproducer.** `wrongcode_d1_dropped_args.sl` with facts `wrongcode_d1.lp` —
one statement of a translated Alloy command, kept whole because formula-level
delta debugging could not remove any sub-formula without losing the symptom.
The shape is a universally quantified disjunction whose second half is a
conjunction of guarded universals over function values.

---

## B5. Large models cannot be compiled {#b5}

**Symptom.** One of two errors, depending on the interpreter:

```
compile error: maximum recursion depth exceeded            # Python 3.12
compile error: Failed to parse extracted egg expression as Python AST:
               too many nested parentheses                  # Python 3.11
```

**Mechanism.** The compiler round-trips a block-sized expression through
egglog's printer and Python's `ast.parse`. On Python 3.12 the printer's
recursion hits the interpreter's C-level recursion limit, which
`sys.setrecursionlimit` does not raise (measured: the traceback stops at
1002 frames under a limit of 100000 in a 1 GB-stack thread). On Python 3.11
that limit can be raised, and then the parser's own nesting cap (about 200
parentheses) is reached instead. Both are the same design fact: a model of
more than roughly 250 statements after the compiler's own conjunction
splitting cannot be compiled whole.

**Mechanism, precisely** (traced 2026-09-07). The block travelled from the
rewriter to the transpiler as one printed `Block(...)` whose constraint list
is a right-nested `cons_constraint` chain, one nesting level per statement;
`transpile/pipeline.py` parsed that text with `ast.parse`, and CPython's
tokenizer refuses more than 200 nested parentheses. The same chain also
failed on the rewriter's side, earlier still: egglog's Python bindings
recurse when registering it (`RecursionError` near 300 cells) and print it
in quadratic space (1.3 MB at 200 statements, which is where most of the
20 s compile of a 190-statement model went). On `main` the rewriter caught
that error and returned the unrewritten source block, so it surfaced later
as a `SyntaxError` on SetLaH-looking text.

**Fix** (commit `b4c7661`, branch `direct-lowering`). No block-sized cons
list anywhere. The rewriter splits each constraint in its own e-graph (the
split rules only look at one cons cell), walks the extracted chain with
`get_callable_args` instead of printing and re-parsing it, and returns a
`PrintedBlock` (`transpile/ir.py`): one printed term per rule and per
constraint. `transpile_printed_block_to_asp` normalizes, parses and lowers
each statement on its own; `_normalize_printed_item` handles egglog's
let-bindings in both layouts. The old whole-block string entry point stays
for callers that hold a `Block` string. `rewrite_block` re-raises instead
of returning the source block. Checked by byte-identical ASP on 52 of 55
local models (the other three differ only in egglog's set-iteration order,
which also differs between two runs of the same compiler), and by the scale
harness:

| statements | before | after |
|---|---|---|
| 192 (constraints only) | `)` syntax error at 21 s | 19.7 s |
| 302 / 502 (constraints only) | not reached | 29.9 s / 47.8 s |
| 455 / 602 / 902 (mixed) | `)` syntax error at 302 | 19.2 s / 25.7 s / 38.2 s |

Compile time stays linear at about 0.1 s per constraint; the remaining
per-statement cost is egglog saturation, not the round trip.

**Workaround (no longer needed).** Compile declarations once and constraints
in slices, then concatenate the ASP; sound because a program is the union of
its rules and constraints.

---

**Single-statement datapoint (2026-09-07, TPTP translator).**
`recursion_ground_guards_or_of_and.sl` (one constraint over a 5-constant,
2-function signature: two nested universal guard blocks of 6 and 2 binders
around a 4-by-4 disjunction of conjunctions of equalities) fails with
`compile error: maximum recursion depth exceeded` on its own, so the
recursion limit is reachable by one statement's shape, not only by
statement count.


---

## B6. Safety check rejects sound rules {#b6}

Two cases, both exit 1, both of which a caller can work around by adding a
domain guard, but which reject rules that are safe:

- **Recursive closure rule.** `tc(X0, XM) :- base(X0, X1), tc(X1, XM).` is
  rejected with `Variable 'XM' in head of rule for 'tc_284' is not bound in
  body`: the recursive atom is not taken as binding `XM`.
- **Equality-bound head variable.** `f(X, V) :- g(X, F), (= V (+ F 1)).` is
  rejected with `Variable 'V' in head ... is not bound in body`: an equality
  to an expression over bound variables is not taken as binding `V`.
- **Definition order.** The check is order-sensitive: with `p` a choice,

      r(X) :- q(X).
      q(X) :- p(X).

  is rejected with `Variable 'X' in head of rule for 'r' is not bound in
  body`, while the same two rules in the other order compile. A predicate
  binds a variable only in rules that come after its own definition, so
  the message names the wrong cause (and the same message appears for a
  predicate that is never defined at all). Found 2026-09-05 through sliced
  compilation of a PORTUS command; a two-pass check, or an "undefined
  predicate" diagnostic, would remove both problems.

## B7. Auxiliary predicate names wrap at five, exit 0 {#b7}

**Mechanism.** A constraint that needs more than five auxiliary predicates
reuses `__aux_0` for the sixth. ASP reads two rules with the same head as one
disjunctive definition, so the two unrelated auxiliaries are unioned, and
because the outer auxiliary depends on the inner chain this also closes a
cycle: `__aux_0` -> `__aux_4` -> `__aux_3` -> `__aux_2` -> `__aux_1` ->
`__aux_0`.

**Trigger.** Exactly at the sixth auxiliary. Nested universal implications of
depth 1 to 5 emit 1 to 5 distinct auxiliaries and are correct; depth 6 emits
five names for six auxiliaries.

**Impact.** Silent wrong output on a model that compiles cleanly, which makes
it more dangerous than [B2](#b2): B2 at least leaves a visible
`raw-constraint` comment, while B7 produces a plausible program that answers
the wrong question.

Corpus exposure, checked 2026-09-07: the three memory-model ports have one
auxiliary each, so none. A sample of 12 DuoAI and mypyvy translations shows
repeated `__aux_N` heads in 7, but those are the *intended* multi-cube
auxiliaries: one mint, one disjunction, one rule per DNF cube, emitted
adjacently with the same free variables. A true B7 collision is
distinguishable in the output: the second definition arrives from the
transpiler's fallback path, after the blank line that separates the
rewriter's rules from the transpiler's, with a different variable level. It
needs a constraint that exhausts the rewriter's `max_depth` (five levels)
and leaves a residual `AuxCall` for the transpiler. No Portus output is on
disk to check; those models nest to depth 15 and are where it would show.

**Mechanism, precisely.** `rewrite/rw.py:_rewrite_single_constraint` lowers
one `Literal.AuxCall` level per recursion with the module global
`rw._aux_counter`, default `max_depth=5` (its docstring still says 3). At
depth 0 the residual call stays in the printed constraint;
`transpile/aux.py:_preprocess_aux_calls`, whose docstring calls itself a
fallback for B1, then lowers it with the *other* module global
`aux._aux_counter`, which has never seen the rewriter's numbers and starts at
`__aux_0`. Neither counter is reset or shared.

**Reproducer.** `tests/inputs/regressions/aux_collision_depth6.sl` with
`aux_collision_depth6.lp`. The compiled program derives `__aux_0(7)`, which
the innermost definition forbids: `__aux_0(X)` means "some successor of X is
not p", node 7's only successor is 0, and `p(0)` holds.

```
compiled __aux_0 = __aux_0(1) __aux_0(2) __aux_0(3) __aux_0(4) __aux_0(7)
intended __aux_0 = __aux_0(1) __aux_0(2) __aux_0(3) __aux_0(4)
```

**Fix** (commit `fd5ca93`, branch `direct-lowering`). One counter per
compilation unit. The rewriter numbers its auxiliaries from an instance
counter reset in `Rewriter.rewrite_program` and exports the next free index
as `program._aux_next`; `transpile_program_to_asp` builds an `AuxNamer`
from it and threads it down to `_preprocess_aux_calls`, so the transpiler's
auxiliaries continue the numbering instead of restarting at `__aux_0`. Both
module globals are gone, which also makes compiling the same model twice in
one process give the same text. Tests: `test_b7_*` in
`tests/test_regressions_known_issues.py`; the semantic one compiles the
reproducer in a fresh interpreter and checks the 128 intended answer sets,
none of which picks node 7 (the unfixed compiler leaves 8).

---

## B8. Existential with nine or more bound variables fails with `Unsupported VarList` {#b8}

Found 2026-09-07 by the TPTP benchmark in setlah-apps, whose translator
flattens function terms and constants into fresh bound variables, so a ground
equation over a few constants and two function applications yields an
existential with ten binders.

**Symptom.** Exit 1 with

```
compile error: Unsupported VarList: Call(func=Name(id='subst_varlist', ctx=Load()), args=[Call(func=...
```

**Reproducers.**

| file | shape | result |
|---|---|---|
| `exists_binders8_ok.sl` | `(\exists F0..F7. (\and k0(F0) ... k7(F7) p(F0, F7)))`, each `k_i` a singleton choice | compiles |
| `exists_binders9_varlist_crash.sl` | the same with nine binders | crash |

The threshold is exactly nine bound variables (1 to 8 compile, 9 and 10
crash). The universal-guard form of the same formula,
`(\forall F0..Fn. (\impl (\and k0(F0) ...) p(F0, Fn)))`, does not crash but
shows the [B2](#b2) non-monotonicity again: 2, 4, 6, 8 and 12 binders compile,
9 and 10 fall back to the raw constraint (exit 0).

**Mechanism (traced 2026-09-07).** Not the rewriting budget: the
substitution rules had run, and the evaluated variable list sat in the same
e-class as the `subst_varlist(...)` call that `exists_to_anonymous`
introduces. `subst_varlist`, `subst_term` and `subst_formula` carried the
default extraction cost, so from nine binders on the unevaluated call was
the cheaper representative and the extractor printed it; the transpiler
cannot read a substitution call as a variable list.

**Fix** (commit `f756e4d`, branch `direct-lowering`). The three substitution
functions cost 10000, so their result always wins extraction when it
exists. Nine and ten binders compile; eight is unchanged; the B1, B2 and B3
reproducers are unchanged. Test `test_b8_wide_existential_is_lowered`.

**Impact.** Any model with an existential over nine or more variables. Not
hit by the study's hand-written ports (widest existential there has four
binders); hit by every function-heavy TPTP problem until the translator
switched to the universal-guard form and started hoisting ground binders.

## B9. A PORTUS command compiles whole and cleanly and answers UNSAT where z3 answers SAT {#b9}

Found 2026-09-07 by the first whole-model run of the PORTUS sample after
B5 (setlah-apps `ports/portus/auto-allcmds-trackA-partial.txt`, 35 commands
of the first 12 models). Three commands of `litmustestgen/c11_perturbed`
(cmd3, cmd4, cmd5) translate, compile with no raw fallback (about 1,540 ASP
lines, 72 to 80 s) and Clingo answers UNSAT; z3 answers SAT on the captured
query. `alloy/question` cmd1 and cmd2 do the same with one and four raw
fallbacks stripped, which is impossible for a relaxation and so also points
at wrong code. The same UNSAT comes from commit `b4c7661` (B7 and B5 only,
whose output is byte-identical to `main` on everything `main` can compile),
so the B2 schedule change did not cause it; these commands never compiled
whole before, so it is a new verdict, not a changed one.

**Reproducer.** `wrongverdict_p1_c11_perturbed_cmd3.{sl,lp}`: the
translation as the study's translator (v8) wrote it, 2,095 lines, not
minimised (each compile is about 70 s). An arity scan of the compiled
program finds no predicate used with two arities, so it is not the [B4](#b4)
signature as recorded. Whether the fault is the compiler's or the
translator's is not yet established; a differential against the direct
lowering (Track B) is the cheapest next step, since a second independent
lowering that agrees with z3 would localise it.

---

## B10. Symmetry breaking applied block-wide, exit 0 {#b10}

Found 2026-09-07 by the differential between the two lowerings on
`raw_f0_ite_frame_equality.sl`: the direct lowering's output carried
`V < K` where the source says `V != K`.

**Mechanism.** `transpile/merge.py:_apply_symmetry_breaking` rewrites
`not X = Y` to `X < Y`, which is sound only for a constraint symmetric in
`X` and `Y` (every violation with `X > Y` has a mirror image). The
condition it checked was block-wide: as soon as *any* count-convertible
core in the block had two constraints (an existence/uniqueness pair such as
a singleton witness `k`), every `not X = Y` in every integrity constraint
of the block was rewritten. On the egglog path most inequalities of
non-symmetric constraints lived in auxiliary rules, which the pass does
not touch, so it rarely showed; the direct lowering puts them in the
integrity constraint itself.

**Reproducers.** `wrongcode_b10_symmetry_breaking.sl` with
`wrongcode_b10.lp`: a singleton `k` plus
`forall X, Y. p(X) and q(Y) and X != Y -> r(X, Y)`. Both lowerings emitted
`:- p(X), q(Y), X < Y, not r(X, Y).` and with `p(2), q(1)` half the answer
sets lacked `r(2, 1)`. The author found the same defect the same day from
the TPTP translator as an equality consequent, `guards -> (= C A)` lowered
to `:- guards, C < A.`: `wrongcode_eq_consequent_lt.{sl,lp}`,
`wrongcode_eq_consequent_lt_min.sl` (13 lines) and
`wrongcode_eq_consequent_lt_ok_no_collapse.sl` (the same without the
singleton, which compiled correctly because no symmetric core was present).

**Fix** (branch `direct-lowering`). The check is now local: an inequality
is rewritten only if swapping its two variables in the other literals of
that constraint gives the same multiset of literals. The intended
uniqueness constraints (`pred(.., X, ..), pred(.., Y, ..), not X = Y`)
still qualify; unrelated ones keep `not X = Y`.

### TPTP-side reproducers and bisect (setlah-apps, 2026-09-07)


Found 2026-09-07 by the TPTP benchmark: five Theorem problems came back
`Satisfiable` from whole-model compiles with no raw fallback, and
`ports/tptp/check_model.py` (setlah-apps) showed the clingo models violate
34 of ALG020+1's 132 constraints.

Found independently the same day by the TPTP benchmark, before this entry
existed; kept here as additional reproducers.

**Symptom.** Exit 0; the constraint

```
(\forall A, B, C. (\impl (\and k(A) f(A, B) g(B, C)) (= C A))).
```

is emitted as

```
:- k(A), f(A, B), g(B, C), C < A.
```

which forbids only half of the violating assignments (`C > A` passes).
Writing `(= A C)` gives `A < C` instead. The correct lowering is
`:- k(A), f(A, B), g(B, C), not C = A.` (or `C != A`).

**Reproducer.** `wrongcode_eq_consequent_lt.sl` with
`wrongcode_eq_consequent_lt.lp` (`dom_U(1..3).`): `k` a singleton choice,
`f`, `g` total functional choices (the compiler collapses their totality and
functionality into `1{...}1`, correctly), plus the constraint above. The
compiled program has models with `g(f(k)) != k`.

**Context dependence.** The same constraint shape taken alone from
ALG020+1 (`k_s_e20(F419), f_s_j(F419, F420), f_s_h(F420, F421) -> F421 =
F419`) compiles correctly to `not F421 = F419`, while inside the 146-statement
model the emitted program accepts models violating it; so the wrong
rewrite depends on what else is in the model or on the rewriting budget.

**Trigger (bisected).** The wrong lowering appears exactly when the model
also contains an existence-plus-uniqueness pair for some predicate, the
pair the compiler collapses into `1{p(X) : dom_U(X)}1`:

| statements present besides the chain constraint | lowering |
|---|---|
| `k` existence + `k` uniqueness (`wrongcode_eq_consequent_lt_min.sl`) | `C < A` (wrong) |
| `f` totality + `f` functionality | `C < A` (wrong) |
| `f`, `g` totality only (`wrongcode_eq_consequent_ok_no_collapse.sl`) | `not C = A` |
| `f`, `g` functionality only | `not C = A` |
| `k` uniqueness only, with `k` a plain choice | `not C = A` |

So the collapsing rewrite (existence + uniqueness to a cardinality rule)
leaks into an unrelated equality consequent in the same model.

**Mechanism (not traced).** Something rewrites `not (= X Y)` into `X < Y`,
which is only sound as a symmetry-breaking step for a symmetric constraint;
here it is applied to an asymmetric one.

**Impact.** Any equality in a consequent that the collapsing patterns
(uniqueness of a singleton, functionality of a graph) do not absorb. The
study's TPTP verdicts are gated on an independent model check until this
is fixed; the concurrency and EPR ports need re-auditing for the shape.

---
## B11. Auxiliary rule with the body `?`, exit 0 {#b11}

Found 2026-09-07 by the same differential on the limits model `flat13`
(`wrongcode_v13_aux_body_question_mark.sl`): the egglog path emits

```
__aux_1(V0, V1, V2, V3, V4, V5, V6, V7, V8, V11) :- ?.
```

The rewriter renders auxiliary rule bodies with its own string printer
(`rewrite/rw.py`, around lines 897 to 942), which returns `"?"` for any
literal shape it does not know instead of failing; a cube it could not
print becomes a rule Clingo rejects with a syntax error, and the compiler
exits 0. The limits harness reported this model as "ok" because it only
looks for the raw-constraint comment. The direct lowering compiles the
model correctly (checked by answer sets against generated instances).

## B12. Vacuous universals become unbound aggregate variables, exit 0 {#b12}

Found 2026-09-07 by the same differential on the limits model `w_v6_c2`
(`unsafe_w6c2_vacuous_universals.sl`): a universal over six variables of
which four occur in no literal. The egglog path emits

```
:- dom_D(X0), dom_D(X1), #count{X2,X3,X4,X5 : q0(X0, X1), ...} != 0.
```

and Clingo refuses to ground it (`X2` to `X5` unsafe); exit 0. The direct
lowering drops the vacuous binders (sorts are assumed non-empty) and
compiles the model correctly.
