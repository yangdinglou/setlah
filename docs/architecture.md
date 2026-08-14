# SetLaH Architecture

## Compiler Pipeline

```text
.sl source
    | parsing (Lark)
    v
SetLaH AST
    | rewriting (egglog)
    v
normalised block expression
    | transpilation and post-processing
    v
Clingo ASP
    | solving (optional)
    v
answer sets
```

Equality-saturation rewrites lower first-order and set constructs, introduce
auxiliary predicates, and split conjunctions into integrity constraints. The
transpiler then renders ASP and applies safety and simplification passes.

## Source Layout

```text
src/setlah/
|-- ast/          AST dataclasses
|-- parsing/      grammar, parser, transformer, and semantic checker
|-- rewrite/      egglog schema, rewrite rules, and AST conversion
`-- transpile/    ASP IR, lowering, safety, rendering, and Clingo execution
```

Important entry points are:

- `src/setlah/cli.py` for the command-line interface.
- `src/setlah/rewrite/rw.py` for e-graph orchestration.
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
