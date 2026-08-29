# SetLaH CLI Reference

## Usage

```text
setlah INPUT.sl [FACTS.lp ...] [options]
```

`INPUT.sl` is a SetLaH model. Each optional `FACTS.lp` is an ordinary Clingo
program that supplies external domains, predicates, and constants. Multiple fact
files are loaded together.

## Compile Or Solve

Print generated ASP without invoking Clingo:

```bash
setlah examples/choose.sl --print-asp
```

Compile and solve with input facts:

```bash
setlah examples/choose.sl examples/choose.lp
```

Enumerate every answer set by forwarding arguments to Clingo:

```bash
setlah examples/choose.sl examples/choose.lp \
  --clingo-arg=-n --clingo-arg=0
```

## Options

| Option | Meaning |
|---|---|
| `--version` | Print the installed SetLaH version. |
| `--print-asp` | Print compiled ASP and exit without solving. |
| `--grounding` | Apply all post-processing rewrites, including rewrites that require grounding. |
| `--cost-conversion` | Prefer auxiliary predicates over nested aggregates during e-graph extraction. |
| `--entailment-elim {asp,egg,both,none}` | Select where entailment-based literal elimination runs; the default is `asp`. |
| `--verbose` | Print compiler phases and timing. |
| `--clingo-arg ARG` | Forward one argument to Clingo; repeat for multiple arguments. |

## Input Facts

An external integer domain named `Index` is represented by `dom_Index/1`:

```asp
dom_Index(1..4).
```

For a declaration such as `ExtPred edge: (Index, Index).`, an input file may
provide:

```asp
edge(1,2).
edge(2,3).
```

Fact files can use any valid Clingo syntax. They may be replaced with another
instance as long as it provides the domains, predicates, and constants declared
by the model.

## Binding Protocol

`setlah protocol` is a machine interface: it reads one JSON request from stdin
and writes one JSON response to stdout. Applications should use a binding such
as the Lean library instead of invoking it manually. The wire format is
documented in [protocol.md](protocol.md).
