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

`compile_source` and `solve_source` expose this pipeline without intermediate
files. The command-line interface and JSON protocol both call these operations,
so all clients use the same compiler semantics.

## Language Bindings

```text
Lean application
    | SetLaH source + in-memory facts, protocol v1 JSON
    v
setlah protocol (one subprocess per request)
    | Python compiler and Clingo
    v
structured compile result or structured solver models
```

The Lean package renders its checked AST back to SetLaH source and invokes the
engine discovered through `PATH` or `SETLAH_EXE`. It does not contain a second
ASP backend. This keeps Python authoritative for compilation semantics and
makes each request isolated and safe to run concurrently.

## Source Layout

```text
src/setlah/
|-- ast/          AST dataclasses
|-- parsing/      grammar, parser, transformer, and semantic checker
|-- rewrite/      egglog schema, rewrite rules, and AST conversion
|-- transpile/    ASP IR, lowering, safety, rendering, and Clingo execution
|-- engine.py     in-memory compile and solve operations
`-- protocol.py   versioned JSON binding interface
```

The `SetLah/` directory contains the Lean AST, parser, checker, source renderer,
DSL, quotation elaborator, and protocol client.

Important entry points are:

- `src/setlah/cli.py` for the command-line interface.
- `src/setlah/engine.py` for the public in-memory API.
- `src/setlah/protocol.py` for the external binding protocol.
- `SetLah/Backend.lean` for the Lean protocol client and public result types.
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
