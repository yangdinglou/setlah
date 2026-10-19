# SetLaH CLI Reference

## Usage

```text
setlah INPUT.sl [FACTS.lp ...] [options]
python -m setlah.cli INPUT.sl [FACTS.lp ...] [options]     # equivalent, without the installed script
```

`INPUT.sl` is a SetLaH model. Each optional `FACTS.lp` is an ordinary Clingo
program that supplies external domains, predicates, and constants. Multiple fact
files are loaded together.

## Compile Or Solve

Print generated ASP without invoking a solver:

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

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | An answer set was found (or `--print-asp` succeeded). |
| 10 | The program is unsatisfiable. |
| 1 | An error: a parse or check failure, an unsupported construct, or a missing optional solver. |

Note that a shell script running under `set -e` stops on an unsatisfiable
instance; test the exit code explicitly when 10 is an expected answer.

## Options

| Option | Meaning |
|---|---|
| `--version` | Print the installed SetLaH version. |
| `--print-asp` | Print compiled ASP and exit without solving. |
| `--clingo-arg ARG` | Forward one argument to Clingo (or clingo-dl); repeat for multiple arguments, e.g. `--clingo-arg=-t8`. |
| `--grounding` | Apply all post-processing rewrites, including rewrites that require grounding. |
| `--verbose` | Print compiler phases and timing. |
| `--lowering {direct,egglog}` | Front half: `direct` (default), the syntax-directed lowering in `setlah.lowering`; `egglog`, deprecated, rewrites by equality saturation and produces the same IR. |
| `--cost-conversion` | Only with `--lowering egglog`: prefer auxiliary predicates over nested aggregates during e-graph extraction. Ignored by the direct lowering. |
| `--entailment-elim {asp,egg,both,none}` | Where entailment-based literal elimination runs; `egg` and `both` only matter with `--lowering egglog`. Default `asp`. |
| `--ext EXT` | Enable an extension; repeatable. `dl` lowers order sorts (where the selection rule or `--order-lowering` asks for it) to difference-logic atoms solved by clingo-dl. |
| `--order-lowering SPEC` | Lowering of order sorts: `auto` (default: a preorder relation when every comparison over the sort is between two values without an offset; otherwise difference logic if `--ext dl` is on; otherwise enumeration), `enum`, `rel`, `dl`, or per sort, e.g. `X=rel,C=dl`. |
| `--acyclic-lowering SPEC` | Lowering of `(\acyclic r)`: `edge` (default, clingo's `#edge` propagator), `closure` (transitive closure as rules with an irreflexivity constraint), `positions` (a function into an order sort with `r(a,b) -> pos(a) < pos(b)`; use with `--ext dl`), or per relation, e.g. `hb=closure`. |
| `--acyclic-range N` | Range `0..N` of the positions sort created by `--acyclic-lowering positions` (default 2^24). |
| `--acyclic-inlining SPEC` | Whether a relation's defining rules are inlined into `#edge` conditions: `auto` (default: only rules that project no variable away), `all`, `none`, or per relation, e.g. `hbc=all`. |
| `--backend {auto,clingo,clingo-dl,sat,monosat}` | Solver. `auto` (default) runs clingo-dl when the compiled program has `&diff` atoms and clingo otherwise; `sat` grounds the program with Clingo's grounder, forms Clark's completion and solves it with a SAT solver through PySAT (tight programs without `#edge`, objectives or theory atoms); `monosat` does the same and hands the `#edge` directives to MonoSAT's graph theory. |

## Environment Variables

Each sets the default of the corresponding option; an explicit option wins.
They also apply when the compiler is called in-process (tests, drivers), so
unset them when you do not mean to change compilation.

| Variable | Option |
|---|---|
| `SETLAH_LOWERING` | `--lowering` |
| `SETLAH_EXT` | `--ext` (comma-separated) |
| `SETLAH_ORDER_LOWERING` | `--order-lowering` |
| `SETLAH_ACYCLIC_LOWERING` | `--acyclic-lowering` |
| `SETLAH_ACYCLIC_INLINING` | `--acyclic-inlining` |
| `SETLAH_ACYCLIC_RANGE` | `--acyclic-range` |

## Optional Solvers

`--ext dl` needs the `clingodl` module (`pip install clingo-dl`) to solve,
not to print; `--backend sat` and `--backend monosat` need PySAT
(`pip install python-sat`), and `--backend monosat` also needs MonoSAT's
Python binding, built from source (see the README).

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
