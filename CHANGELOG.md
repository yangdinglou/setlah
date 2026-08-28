# Changelog

All notable changes to SetLaH will be documented in this file.

## [0.1.0rc1] - Unreleased

Initial public prerelease of the SetLaH compiler and command-line interface.

- Package the implementation as `setlah` with a `setlah` console command.
- Add tested compilation and solving examples.
- Add Clingo AST execution through `ProgramBuilder`.
- Add safety guards inferred through arithmetic comparisons.
- Preserve variables in negated predicates when detecting uniqueness patterns.
- Constrain runtime dependencies to the tested egglog and Clingo versions.
- Declare cloudpickle explicitly because egglog 12 imports it at runtime.
- Add runnable fact instances and an end-to-end check for every Maple-set model.
- Add public in-memory Python compilation and solving APIs.
- Add the versioned JSON protocol used by external language bindings.
- Add a Lean 4.32 library with checked quotations, program combinators, typed
  facts, structured models, and actionable backend errors.
- Add a Lean installation doctor and end-to-end SAT/UNSAT examples.
