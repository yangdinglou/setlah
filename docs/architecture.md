# SetLaH Architecture

## Compiler Pipeline

```text
.sl source
    | parsing (Lark)
    v
SetLaH AST
    | front half: rewriting (egglog, default) or direct lowering (--lowering direct)
    v
IR: rules and constraints (IRRule / IRConstraint), auxiliary rules
    | transpilation and post-processing (shared by both front halves)
    v
Clingo ASP
    | solving (optional)
    v
answer sets
```

The egglog front half lowers first-order and set constructs by equality
saturation, introduces auxiliary predicates and splits conjunctions into
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
|-- lowering/     direct syntax-directed lowering to the transpiler IR
`-- transpile/    ASP IR, lowering, safety, rendering, and Clingo execution
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
