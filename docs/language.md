# SetLaH Language Guide

SetLaH programs contain domain declarations, external input predicates, and
blocks of rules or first-order constraints. The compiler lowers these constructs
to ASP and can either print the result or solve it with Clingo.

## Declarations

```text
ExtDOM Index: INT.
DefDOM Size: INT. Set: 1..9.
ExtPred edge: (Index, Index).
Const n: INT = 4.
```

- `ExtDOM` declares a domain supplied by an input fact file as `dom_Type/1`.
- `DefDOM` defines a domain in the source program.
- `ExtPred` declares a predicate supplied by an input fact file.
- `Const` declares a constant.
- `OrdDOM X: 0..15.` declares an order sort: a bounded integer sort whose
  values occur only in comparisons and constant offsets; `Fun f: (Q, S) -> X.`
  declares a total function into it, written in models as the predicate
  `f(Q, S, X)`. Order sorts are lowered in plain ASP by enumeration (`enum`, the basic
  lowering) or as a preorder relation (`rel`, chosen automatically when
  every comparison is between two values without offsets), and, with the
  extension `--ext dl`, to difference logic under clingo-dl
  (`--order-lowering` selects per sort: `X=rel,C=dl`); see
  `docs/order-sorts.md`.

## Rules

A question mark makes a predicate a choice. A rule without it is deterministic.

```text
selected(X)? :- available(X).
reachable(Y) :- reachable(X), edge(X, Y).
```

Rules and constraints are grouped in square-bracketed blocks:

```text
[
    selected(X)? :- available(X).
    (\exists X. selected(X)).
]
```

## Formulae

```text
\forall X. formula.
\exists X. formula.
(\impl antecedent consequent).
(\and f1 f2 ...).
(\or f1 f2 ...).
(\neg formula).
(= X Y).
(!= X Y).
```

Arithmetic terms can appear in comparisons:

```text
(!= (- R1 R2) (- C1 C2)).
(= (* 3 X) Y).
```

## Acyclicity

```text
(\acyclic edge).
```

The transitive closure of the binary relation is irreflexive; lowered to
clingo's `#edge` propagator. A relation of arity 2k has k-tuples as nodes
(the first k arguments the source), for layered encodings.

The construct has three lowerings, `--acyclic-lowering edge|closure|positions`
(per relation `r=closure`): clingo's `#edge` propagator (default), the
transitive closure as rules with an irreflexivity constraint, or a total
function into an order sort with `r(a, b) -> pos(a) < pos(b)` (difference
logic with `--ext dl`). Independently of the lowering, `--backend
sat|monosat` decides the compiled program by a SAT solver (the ground
program completed; tight programs only) or by MonoSAT, whose graph theory
takes the `#edge` directives; `docs/order-sorts.md`, Section 12.

## Aggregates

Projection variables appear in parentheses after a set predicate:

```text
\forall R, C. #count {Set_sudoku}(V) = 1.
\forall R, V. #count {Set_sudoku}(C) = 1.
```

For example, the first formula requires exactly one `V` for every `(R, C)`.

## Partitions And Sets

```text
(\partition Domain {{PredA PredB PredC}}).

Let {A}(X, Y) = { (X, Y) | condition(X, Y) }
in (\subset A {B}).
```

A partition covers its domain with mutually exclusive predicates. Set
comprehensions bind a named set for use by later set constraints.

## Complete Examples

See [the examples guide](../examples/README.md) for executable models and their
input fact files. Use `setlah SOURCE.sl --print-asp` when developing a model to
inspect its generated ASP.
