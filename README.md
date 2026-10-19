# SetLaH

SetLaH is a constraint-modelling language that compiles first-order logic,
choice rules, and set constraints to
[Clingo](https://potassco.org/clingo/) Answer Set Programs.

The language and its design are presented in the OOPSLA 2026 paper
[Semi-Declarative Language for Combinatorial Search](https://yangdinglou.com/files/setlah-oopsla26.pdf).
This branch (`order-sorts`) adds two constructs, order sorts and acyclicity,
each with several lowerings and solver backends; they are described in
[docs/language.md](docs/language.md) and, with their correctness arguments,
in [docs/order-sorts.md](docs/order-sorts.md).

This repository is a prerelease. The language and Python API may change before
version 1.0; changes are recorded in [CHANGELOG.md](CHANGELOG.md).

## Installation

SetLaH requires Python 3.11 or later (Ubuntu 24.04 ships 3.12; on 22.04 use
`uv`, `pyenv` or the deadsnakes PPA). Install into a virtual environment:

```bash
git clone https://github.com/yangdinglou/setlah.git
cd setlah
python3 -m venv .venv && . .venv/bin/activate
python -m pip install -e '.[dev]'
setlah --version
```

The core needs only Clingo 5.8.0 (installed as a dependency). Three optional
solver backends need extra packages; install the ones you use:

| Feature | Needs | Install |
|---|---|---|
| `--ext dl` (order sorts in difference logic), including `--acyclic-lowering positions --ext dl` | clingo-dl | `pip install -e '.[dl]'` (pins `clingo-dl==1.5.0.post1`) |
| `--backend sat` and `--backend monosat` | PySAT | `pip install -e '.[sat]'` (pins `python-sat==1.9.dev15`) |
| `--backend monosat` | MonoSAT's Python binding | build from source, below |

MonoSAT is not on PyPI. Build it from [sambayless/monosat](https://github.com/sambayless/monosat)
(the published measurements used commit `fa810d4`):

```bash
sudo apt install build-essential cmake libgmp-dev zlib1g-dev
git clone https://github.com/sambayless/monosat.git && cd monosat && git checkout fa810d4
cmake -DPYTHON=OFF -DCMAKE_BUILD_TYPE=Release . && make -j"$(nproc)"
cd src/monosat/api/python && python -m pip install .   # copies libmonosat.so into the package
```

If a recent GCC rejects warnings in MonoSAT's sources, add
`-DCMAKE_CXX_FLAGS=-Wno-error` to the `cmake` line.

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

Run the model and input together, or inspect the generated ASP:

```bash
setlah examples/choose.sl examples/choose.lp
setlah examples/choose.sl --print-asp
```

The exit code is 0 when an answer set is found, 10 when the program is
unsatisfiable, and 1 on an error.

## Order Sorts and Acyclicity

An order sort is a bounded integer sort whose values may only be compared;
the compiler chooses its lowering (enumeration, a total preorder, or
difference logic) from the model text:

```text
OrdDOM T: 0..20000.
Fun phi: (S, L) -> T.
```

```bash
setlah MODEL.sl FACTS.lp --ext dl                                 # selection rule: rel, dl, enum
setlah MODEL.sl FACTS.lp --ext dl --order-lowering X=rel,C=dl     # override per sort
```

`(\acyclic r)` states that a relation is acyclic; its lowering is a flag:

```bash
setlah tests/inputs/acyclic/polygraph.sl --print-asp               # clingo's #edge propagator (default)
setlah MODEL.sl FACTS.lp --acyclic-lowering closure                # transitive closure as rules
setlah MODEL.sl FACTS.lp --acyclic-lowering positions --ext dl     # integer positions under clingo-dl
setlah MODEL.sl FACTS.lp --backend monosat                         # MonoSAT's graph theory for #edge
```

Always pair `--acyclic-lowering positions` with `--ext dl` (or a small
`--acyclic-range`): without the extension the positions sort is enumerated
over its default range of 2^24 values. Models using both constructs are under
`tests/inputs/order/` and `tests/inputs/acyclic/`.

## Larger Example

```bash
setlah examples/maple-set/nqueen.sl examples/instances/nqueen-4.lp --grounding
./examples/check.sh      # runs every included example
```

## Documentation

- [Language guide](docs/language.md): declarations, rules, formulae, sets,
  aggregates, order sorts and acyclicity.
- [CLI reference](docs/cli.md): options, environment variables and exit codes.
- [Order sorts and lowerings](docs/order-sorts.md): semantics, the lowerings,
  their correctness arguments and the selection rule.
- [Architecture](docs/architecture.md): compiler pipeline and source layout.
- [Known issues](docs/known-issues.md): the defect register with reproducers.
- [Reproducibility](docs/reproducibility.md): which commit produced which
  published measurements, and how to check out exactly that compiler.
- [Examples](examples/README.md) and [Contributing](CONTRIBUTING.md).

## Development

```bash
python -m pip install -e '.[dev,dl,sat]'
python -m pytest            # about 100 s; tests that need an absent optional solver are skipped
./examples/check.sh
```

## Known Limitations

- The Python API is provisional and may change before version 1.0.
- Models under `examples/maple/` use an experimental shorthand. Use the
  equivalent `examples/maple-set/` models for direct execution.
- Tested with Clingo 5.8.0. The default front half is the direct lowering;
  the deprecated egglog front half (`--lowering egglog`) is tested with
  egglog 12.x, which remains a dependency because the tests use it as a
  differential oracle.
- `--backend sat|monosat` accept only tight programs without objectives or
  theory atoms (the closure lowering of acyclicity is not tight); unsupported
  combinations stop with a Python error.

## License

SetLaH is licensed under the [Apache License 2.0](LICENSE).
