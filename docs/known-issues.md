# Known Issues

Compiler defects found by compiling third-party finite-domain problems with
SetLaH: verification queries from DuoAI (OSDI 2022) and mypyvy (CAV 2024),
and Alloy commands translated by PORTUS. Each entry has a minimal `.sl`
program under `tests/inputs/regressions/` that reproduces it on its own.

Reproduce with `setlah tests/inputs/regressions/<file>.sl [facts.lp] --print-asp`.

| id | symptom | exit | severity | status |
|---|---|---|---|---|
| [B1](#b1) | crash: `Expected Literal(atom, sign), got Literal.AuxCall(...)` | 1 | blocker | **fixed** |
| [B2](#b2) | `:- % raw-constraint ...` in the output | 0 | wrong output | open |
| [B3](#b3) | unsafe auxiliary rule; Clingo rejects the program | 0 | wrong output | **fixed** |
| [B4](#b4) | a body atom loses its arguments | 0 | wrong output | open |
| [B5](#b5) | large models cannot be compiled at all | 1 | limitation | open |
| [B6](#b6) | safety check rejects sound recursive and equality-bound rules | 1 | limitation | open |

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

**Suggested fix.** Make the fallback a hard error, so incompleteness is
visible; a caller can then decide. Emitting a comment where a constraint
belongs is never safe, and `exit 0` on it is worse.

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

**Workaround.** Compile declarations once and constraints in slices, then
concatenate the ASP; sound because a program is the union of its rules and
constraints.

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
