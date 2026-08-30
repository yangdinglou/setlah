# SetLaH

SetLaH is a constraint-modelling language that compiles first-order logic,
choice rules, and set constraints to
[Clingo](https://potassco.org/clingo/) Answer Set Programs.

The language and its design are presented in the OOPSLA 2026 paper
[Semi-Declarative Language for Combinatorial Search](https://yangdinglou.com/files/setlah-oopsla26.pdf).

This repository is a prerelease. The language and Python API may change before
version 1.0; command-line changes are recorded in [CHANGELOG.md](CHANGELOG.md).

## Installation

SetLaH requires Python 3.11 or later.

```bash
git clone https://github.com/yangdinglou/setlah.git
cd setlah
python -m pip install .
```

Confirm the installation:

```bash
setlah --version
```

## Running Example

The included `examples/choose.sl` model chooses a non-empty subset of the
available items:

```text
ExtDOM Item: INT.
ExtPred available: (Item).

[
    selected(X)? :- available(X).
    (\exists X. selected(X)).
]
```

Its input file, `examples/choose.lp`, supplies the concrete domain and facts:

```asp
dom_Item(1..3).
available(1..3).
```

Run the model and input together:

```bash
setlah examples/choose.sl examples/choose.lp
```

The answer set contains at least one `selected/1` atom. Clingo may choose a
different valid non-empty subset between runs.

To inspect the generated ASP without solving it:

```bash
setlah examples/choose.sl --print-asp
```

## Larger Example

Run the included four-queens instance:

```bash
setlah examples/maple-set/nqueen.sl examples/instances/nqueen-4.lp \
  --grounding --cost-conversion
```

Every executable model under `examples/maple-set/` has a corresponding input
under `examples/instances/`. Check all included examples with:

```bash
./examples/check.sh
```

## Lean 4

The Lean library provides checked SetLaH quotations, program-building
combinators, typed facts, and structured solver results. It uses the installed
Python `setlah` command as its compiler and solver engine.

```lean
import SetLah

open SetLah

def choice : Program := setlah% r#"
ExtDOM Item: INT.
ExtPred available: (Item).
[
  selected(X)? :- available(X).
  (\exists X. selected(X)).
]
"#

def main : IO Unit := do
  let instance := (Instance.ofProgram choice)
    |>.addFact "dom_Item" [.number 1]
    |>.addFact "available" [.number 1]
  let result ← solve! instance
  IO.println s!"{repr result.status}: {result.models.length} model(s)"
```

Build the library and verify the Python engine, protocol, and Clingo:

```bash
lake build SetLah
lake exe setlahDoctor
lake exe setlahExamples
```

See the [Lean guide](docs/lean.md) for Lake dependency setup, combinators,
options, model inspection, and error handling.

## Documentation

- [Language guide](docs/language.md): declarations, rules, formulae, sets, and
  aggregates.
- [CLI reference](docs/cli.md): compilation, solving, fact files, and options.
- [Examples](examples/README.md): runnable models, commands, and input schemas.
- [Lean 4 guide](docs/lean.md): embedding, compilation, solving, and models.
- [JSON protocol](docs/protocol.md): versioned interface for language bindings.
- [Architecture](docs/architecture.md): compiler pipeline and source layout.
- [Contributing](CONTRIBUTING.md): development setup and contribution checks.
- [Roadmap](ROADMAP.md): work planned beyond this prerelease.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

## Known Limitations

- The Python API is provisional and may change before version 1.0.
- Lean integration requires Lean 4.32.0 and an installed `setlah` executable.
- The Lean client starts one isolated engine process per request. Streaming,
  cancellation, and incremental grounding are not yet supported.
- Models under `examples/maple/` use an experimental shorthand. Use the
  equivalent `examples/maple-set/` models for direct execution.
- This prerelease is tested with egglog 12.x and Clingo 5.8.0.

## License

SetLaH is licensed under the [Apache License 2.0](LICENSE).
