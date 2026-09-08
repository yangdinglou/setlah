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
| `--lowering {direct,egglog}` | Select the front half: `direct` (default) is the syntax-directed lowering in `setlah.lowering`; `egglog`, deprecated, rewrites by equality saturation and produces the same IR for the same back half. The default can be set with the `SETLAH_LOWERING` environment variable, so drivers that call `setlah` unchanged can select a backend. |

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
