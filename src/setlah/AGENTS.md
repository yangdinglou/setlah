# Python Engine Agent Guide

This guide applies to `src/setlah/` and overrides the root guide where more
specific. The Python implementation is authoritative for compiler and solver
semantics.

## Module Responsibilities

- `parsing/`: grammar, AST construction, and semantic checks.
- `rewrite/`: equality-saturation schema, rules, and AST conversion.
- `transpile/`: ASP IR, lowering, safety, rendering, and Clingo execution.
- `engine.py`: public in-memory compile/solve operations and structured result
  types.
- `protocol.py`: protocol-v1 request validation and JSON encoding.
- `cli.py`: file-based user commands and protocol dispatch.
- `api.py`, when present: ergonomic in-process Python `Program` and `Instance`
  workflow.

Keep these ownership boundaries. Shared semantics belong in `engine.py` or the
compiler pipeline, not duplicated in the CLI, protocol, Lean client, or Python
convenience API.

## Engine And Protocol Contracts

- `compile_source` and `solve_source` accept source and facts in memory. Do not
  add temporary-file transport.
- Keep `CompileOptions`, `SolveOptions`, results, symbols, models, statuses, and
  error categories structured and serializable.
- Return `satisfiable`, `unsatisfiable`, or `unknown`; do not infer status from
  printed solver text.
- Encode model symbols recursively with kind, value/name, arguments, and sign.
- Protocol v1 reads one request from stdin and writes exactly one JSON response
  to stdout. Redirect compiler chatter and diagnostics away from stdout.
- Reject malformed fields and incompatible protocol versions with structured
  protocol errors. Never silently select another implementation.
- A breaking wire-format change requires a protocol version change plus updates
  to `docs/protocol.md`, protocol tests, and binding clients.
- Keep legacy file-based CLI commands working and route them through the same
  engine where practical.

## Python Embedding API

When `api.py` exists:

- Validate `Program` source eagerly, but use the engine for authoritative
  semantic checking, compilation, and solving.
- Keep `Instance` immutable; every `add_*` operation returns a new instance.
- Treat Python strings explicitly: quoted strings use `string(...)`, symbolic
  constants use `symbol(...)`, and raw ASP uses `add_raw_facts(...)`.
- Reject booleans where integer ASP terms are expected.
- Export intended public names from `setlah.__init__` and keep `py.typed` in the
  built wheel.
- Do not launch the `setlah` subprocess from the in-process Python API.

## Validation

Run focused tests while iterating, then:

```bash
python -m pytest
python examples/python_choice.py  # when this file exists
./examples/check.sh
```

For protocol changes, cover compile, SAT, UNSAT, malformed requests, version
mismatch, structured errors, structured symbols, and concurrent solves. For
packaging changes, build the wheel and verify required package data is present.
