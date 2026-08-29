# Lean Binding Agent Guide

This guide applies to the Lean library under `SetLah/`. The public facade is
`SetLah.lean`; implementation modules should remain independently testable.

## Toolchain And Boundary

- The package is pinned by `lean-toolchain` to Lean 4.32.0.
- Python remains authoritative for SetLaH semantics. Lean validates authoring
  syntax early, renders SetLaH source, and calls `setlah protocol`.
- Do not add a second ASP renderer, repository-relative `main.py` invocation,
  hard-coded Python executable, fixed temporary file, or silent fallback.
- Discover the engine through `PATH`, with `SETLAH_EXE` as the explicit
  override. Validate engine and protocol compatibility before compile/solve.

## Module Responsibilities

- `Ast.lean`: typed SetLaH syntax and public data structures.
- `Parser.lean`: Lean-side parser for authoring and early diagnostics.
- `Checker.lean`: inexpensive structural and semantic checks available in Lean.
- `Source.lean`: deterministic SetLaH source rendering and round-tripping.
- `DSL.lean`: programmatic combinators.
- `Quotation.lean`: `setlah% r#"..."#` elaboration-time checking.
- `Backend.lean`: engine discovery, JSON protocol, structured results, and
  actionable errors.

Keep AST construction separate from backend IO. Do not make model consumers
parse printed atoms; use structured `Term`, `Atom`, and `Model` values.

## Public API Expectations

- Support both combinators and checked quotation without changing their
  semantics independently.
- Keep `Instance` fact helpers typed, with raw ASP as an explicit escape hatch.
- Expose non-throwing `compile`/`solve` results and concise throwing
  `compile!`/`solve!` wrappers.
- Preserve structured solve statuses and backend error categories.
- Default to one model; require an explicit option for multiple or all models.
- Protocol stdout is machine data. Include stderr in useful backend errors, but
  do not decode human solver output.

## Validation

Install the local Python package first, then run:

```bash
lake build SetLah setlahDoctor setlahTests setlahExamples
lake exe setlahTests
lake exe setlahDoctor
lake exe setlahExamples
```

For parser, AST, DSL, quotation, or source-renderer changes, test both authoring
styles and source round-tripping. For backend changes, cover mocked success,
missing executables, invalid JSON, structured engine errors, incompatible
versions, SAT, and UNSAT. Keep `docs/lean.md` and at least one top-level README
example aligned with the public workflow.
