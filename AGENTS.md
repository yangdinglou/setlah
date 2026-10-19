# SetLaH Agent Guide

This file is operational guidance for coding agents. User-facing behavior and
installation instructions belong in `README.md` and `docs/`.

## Start Here

1. Run `git branch --show-current` and `git status --short` before editing.
2. Read the nearest `AGENTS.md` for every file you plan to change. A nested
   guide overrides this file within its directory.
3. Keep changes on the branch that owns the feature. Do not move unrelated
   evaluation-artifact code into this repository.

## Branch Ownership

- `main`: released language, CLI, documentation, and generally useful fixes.
- `binding-core`: shared in-memory engine and versioned JSON protocol.
- `lean4-binding`: Lean client, quotations, DSL, examples, and Lean tests. It is
  based on `binding-core`.
- `python-binding`: ergonomic Python embedding API and Python tutorial. It is
  based on `binding-core`.

- `direct-lowering` / `order-sorts` (same commit): the direct lowering, order sorts,
  `(\acyclic r)` and the solver backends (`setlah.ext`); tag `paper-pldi27` marks the
  commit the published evaluation used.
- `grounding-split`: the rule-decomposition pass (`--split-width`), tag
  `study-split-width`.

When a change is useful to both bindings, implement it in `binding-core` first.
Do not add Python embedding API work to `lean4-binding`, or Lean sources and
Lake configuration to `python-binding`.

## Setup And Commands

SetLaH requires Python 3.11 or later.

```bash
python -m pip install -e '.[dev]'
python -m pytest
./examples/check.sh
```

Use `python -m pytest`, not a bare `pytest`, so the command uses the selected
Python environment. Run commands from the repository root.

For package-facing changes, also run:

```bash
python -m build
python -m twine check dist/*
```

If `lakefile.lean` exists, also follow `SetLah/AGENTS.md` and run the Lean checks
listed there.

## Architecture Invariants

- Python is the canonical implementation of SetLaH parsing, checking,
  rewriting, ASP generation, grounding, and solving.
- Preserve the pipeline: `parsing` -> `lowering` (direct; `rewrite` is the deprecated
  egglog front half) -> `transpile` -> a solver backend (Clingo by default).
- Do not change the code of a commit the evaluation cites (`docs/reproducibility.md`);
  fix forward on a new commit.
- Preserve existing CLI behavior unless the task explicitly changes it.
- Use structured AST, Clingo, and JSON APIs instead of parsing rendered output
  or rewriting structured data with ad hoc string operations.
- Keep protocol stdout machine-only. Diagnostics belong on stderr.
- Do not introduce repository-relative executable paths, fixed temporary files,
  or silent fallback implementations.
- One model is the default. Enumerating more or all models must be explicit.

## Editing Rules

- Prefer existing dataclasses, enums, helpers, and naming conventions.
- Keep public APIs typed and document behavior that users need to rely on.
- Add focused regression tests for every behavior change.
- Keep examples executable; example input facts belong under
  `examples/instances/`.
- Do not edit generated directories such as `build/`, `dist/`, `.lake/`,
  `*.egg-info/`, caches, or compiled artifacts.
- Do not weaken or delete tests merely to make a change pass.

## Definition Of Done

A task is complete when the implementation, focused tests, relevant full test
suite, and affected documentation agree. Report which commands ran and any
remaining limitations. Do not claim success for tests that were not executed.
