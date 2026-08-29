# SetLaH In Python

The Python package provides an in-process workflow for constructing an
instance, compiling it to ASP, solving it with Clingo, and inspecting structured
models. It does not start a `setlah` subprocess or create temporary files.

## Installation

SetLaH requires Python 3.11 or later. From a repository checkout:

```bash
python -m pip install .
```

After a release is published to PyPI, applications can install it with:

```bash
python -m pip install setlah
```

Confirm both the package and command-line entry point:

```bash
python -c "import setlah; print(setlah.__version__)"
setlah --version
```

## Define A Program

`Program` accepts SetLaH source and checks its syntax immediately:

```python
from setlah import Program

choice = Program(r"""
ExtDOM Item: INT.
ExtPred available: (Item).
[
    selected(X)? :- available(X).
    (\exists X. selected(X)).
]
""")
```

For a model maintained in a separate file:

```python
choice = Program.from_file("examples/choose.sl")
```

Semantic checking and compiler rewrites run when the program is compiled or
solved. Python and Lean therefore use the same Python compiler implementation.

## Build An Instance

An `Instance` combines a program with its concrete domains, predicates, and
constants. Instances are immutable: every `add_...` method returns a new value.

```python
instance = (
    choice.instance()
    .add_raw_facts("dom_Item(1..3).")
    .add_fact("available", 1)
    .add_fact("available", 2)
    .add_fact("available", 3)
)
```

Integer arguments can be passed directly. Other ASP term types are explicit so
that Python strings are never ambiguously treated as quoted strings or symbolic
constants:

```python
from setlah import function, string, symbol

instance = (
    instance
    .add_fact("colour", 1, symbol("red"))
    .add_fact("label", 1, string("first item"))
    .add_fact("metadata", function("pair", 1, symbol("red")))
    .add_fact("disabled", 3, positive=False)
    .add_const("limit", 3)
)
```

Use `add_raw_facts` for ranges, rules, or other arbitrary Clingo input. Use
`atom(...)` with `add_atom(...)` when facts are prepared separately.

## Solve And Inspect Models

Solving returns a structured status and zero or more structured models:

```python
from setlah import SolveStatus

result = instance.solve()

match result.status:
    case SolveStatus.SATISFIABLE:
        model = result.models[0]
        for selected in model.atoms_named("selected"):
            item = selected.arguments[0].number
            print(f"selected item {item}")
    case SolveStatus.UNSATISFIABLE:
        print("the instance has no solution")
    case SolveStatus.UNKNOWN:
        print("the solver stopped without deciding the instance")
```

Terms have a `kind` and structured fields: integer terms use `number`, quoted
strings use `string`, and functions or atoms use `name`, `arguments`, and
`positive`. `render()` converts a term back to ASP syntax when text is useful.

One model is returned by default. Request a bounded number or all models
explicitly:

```python
from setlah import SolveOptions

two = instance.solve(SolveOptions(max_models=2))
all_models = instance.solve(SolveOptions(max_models=0))
```

## Compile Without Solving

Compilation produces ASP and any compiler diagnostics:

```python
from setlah import CompileOptions

compiled = instance.compile(CompileOptions(
    grounding=True,
    cost_conversion=True,
))
print(compiled.asp)
```

`entailment_elim` accepts `"asp"`, `"egg"`, `"both"`, or `"none"`. Solver
calls accept the same settings through `SolveOptions.compile`:

```python
options = SolveOptions(
    compile=CompileOptions(grounding=True, cost_conversion=True),
    max_models=1,
    clingo_arguments=("--stats=1",),
)
result = instance.solve(options)
```

## Error Handling

Compiler and solver failures raise `EngineError` with a stable category:

```python
from setlah import EngineError

try:
    result = instance.solve()
except EngineError as error:
    print(error.category.value, error.message)
```

Categories distinguish parsing, semantic checking, compilation, grounding, and
solving. Invalid Python helper arguments raise `TypeError` or `ValueError`
before the engine runs.

## Larger Example

The N-Queens model can be loaded and solved without temporary files:

```python
from setlah import CompileOptions, Program, SolveOptions

queens = (
    Program.from_file("examples/maple-set/nqueen.sl")
    .instance()
    .add_raw_facts("dom_Index(1..4). n_map(1..4,1..4).")
)
result = queens.solve(SolveOptions(
    compile=CompileOptions(grounding=True, cost_conversion=True),
))
print([atom.render() for atom in result.models[0].atoms_named("queen")])
```

The lower-level `compile_source` and `solve_source` functions remain available
for frameworks that already manage source and fact strings directly.
