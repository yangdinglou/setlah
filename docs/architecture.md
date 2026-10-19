# SetLaH Architecture

## Compiler Pipeline

```text
.sl source
    | parsing (Lark)
    v
SetLaH AST
    | front half: direct lowering (default) or rewriting (egglog, deprecated, --lowering egglog)
    v
IR: rules and constraints (IRRule / IRConstraint), auxiliary rules
    | order sorts (lowering/order.py): enum, rel, or dl (extension ext/dl.py)
    | acyclicity: #edge, closure rules, or positions (an order sort)
    | transpilation and post-processing (shared by both front halves)
    v
Clingo ASP (with &diff atoms under --ext dl)
    | solving (optional): clingo, clingo-dl (ext/dl.py),
    |   SAT via completion (ext/ground.py, ext/sat.py), MonoSAT (ext/mono.py)
    v
answer sets
```

Order sorts (`OrdDOM`, `Fun`) are lowered by a pass over the direct
lowering's cubes and rule bodies (`src/setlah/lowering/order.py`): enumeration,
a chosen total preorder, or, with the `dl` extension, reified comparison
Booleans with `&diff` atoms; `auto` selects per sort from the model text.
`(\acyclic r)` is lowered in `src/setlah/lowering/lower.py`: an `#edge`
directive (inlining projection-free defining rules), the transitive closure
as rules, or an AST rewrite to a positions order sort. The solver backends in
`src/setlah/ext/` capture the ground program through Clingo's observer
interface; `docs/order-sorts.md` gives the semantics and the correctness
argument of every lowering.

The egglog front half (deprecated) lowers first-order and set constructs by
equality saturation, introduces auxiliary predicates and splits conjunctions into
integrity constraints; it hands the transpiler one printed egglog term per
statement (`PrintedBlock`). The direct front half (`src/setlah/lowering/`)
does the same lowering syntax-directed: negation normal form, one integrity
constraint per DNF cube of a constraint's violation, auxiliary predicates
for quantified subformulas, projected count aggregates rendered directly;
it hands the transpiler IR nodes (`LoweredBlock`). The transpiler then
renders ASP and applies safety and simplification passes on either input.

## Source Layout

```text
src/setlah/
|-- ast/          AST dataclasses
|-- parsing/      grammar, parser, transformer, and semantic checker
|-- rewrite/      egglog schema, rewrite rules, and AST conversion
|-- lowering/     direct syntax-directed lowering to the transpiler IR;
|                 order.py lowers order sorts, lower.py also lowers (\acyclic r)
|-- ext/          extensions: dl.py (difference logic, clingo-dl), ground.py
|                 (ground-program capture and Clark's completion), sat.py (PySAT),
|                 mono.py (MonoSAT)
`-- transpile/    ASP IR, lowering, safety, rendering, and solver execution
```

Important entry points are:

- `src/setlah/cli.py` for the command-line interface.
- `src/setlah/rewrite/rw.py` for e-graph orchestration.
- `src/setlah/lowering/lower.py` for the direct lowering.
- `src/setlah/transpile/api.py` for public transpilation and execution helpers.
- `src/setlah/transpile/pipeline.py` for ASP post-processing phases.

## Transpiler Phases

| Phase | Operation | Module |
|---|---|---|
| 0 | Merge choice and partition constraints | `merge.py` |
| 0.5 | Substitute variable equalities | `rewrite.py` |
| 1 | Lower selected negated patterns to counts | `rewrite.py` |
| 2 | Merge compatible count constraints | `merge.py` |
| 3 | Eliminate entailed literals | `entailment.py` |
| 4 | Insert domain guards for ASP safety | `safety.py` |
| 5 | Replace singleton variables | `safety.py` |

## Dependencies

- [Lark](https://github.com/lark-parser/lark) parses SetLaH source.
- [egglog](https://github.com/egraphs-good/egglog) performs equality-saturation
  rewriting.
- [Clingo](https://potassco.org/clingo/) grounds and solves generated ASP.
- Optional: [clingo-dl](https://github.com/potassco/clingo-dl) for `--ext dl`,
  [PySAT](https://pysathq.github.io/) for `--backend sat|monosat`, and
  [MonoSAT](https://github.com/sambayless/monosat) for `--backend monosat`.
- egglog is used only by the deprecated front half and by the tests, which
  use it as a differential oracle.
