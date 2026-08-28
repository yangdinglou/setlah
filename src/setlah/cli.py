from __future__ import annotations

import argparse
import sys
from pathlib import Path

from setlah import __version__
from setlah.engine import CompileOptions, EngineError, SolveOptions, compile_source, solve_source
from setlah.protocol import protocol_main


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "protocol":
        if len(argv) != 1:
            print("usage: setlah protocol", file=sys.stderr)
            return 2
        return protocol_main()

    ap = argparse.ArgumentParser(description="SetLaH to Clingo transpiler and solver")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument("input", help="Input .sl file")
    ap.add_argument(
        "facts",
        nargs="*",
        metavar="FACTS.lp",
        help="Additional .lp fact/instance files loaded alongside the compiled program",
    )
    ap.add_argument("--verbose", action="store_true", help="Verbose rewriting logs")
    ap.add_argument(
        "--cost-conversion", action="store_true", help="Run cost conversion saturation before extraction"
    )
    ap.add_argument(
        "--entailment-elim",
        choices=["asp", "egg", "both", "none"],
        default="asp",
        help="Where to apply entailment-based literal elimination (default: asp)",
    )
    ap.add_argument("--print-asp", action="store_true", help="Print transpiled ASP and exit")
    ap.add_argument(
        "--grounding", action="store_true", help="Apply all safe post-processing ground/aggregate rewrites"
    )
    ap.add_argument(
        "--clingo-arg", action="append", default=[], help="Extra argument passed to clingo (repeatable)"
    )
    args = ap.parse_args(argv)

    source = _read(args.input)
    facts = [_read(path) for path in args.facts]
    compile_options = CompileOptions(
        grounding=args.grounding,
        cost_conversion=args.cost_conversion,
        entailment_elim=args.entailment_elim,
        verbose=args.verbose,
    )
    try:
        if args.print_asp:
            result = compile_source(source, facts, compile_options)
            if args.verbose:
                for diagnostic in result.diagnostics:
                    print(diagnostic, file=sys.stderr)
            print(result.asp, end="")
            return 0

        result = solve_source(
            source,
            facts,
            SolveOptions(
                compile=compile_options,
                max_models=1,
                clingo_arguments=tuple(args.clingo_arg),
            ),
        )
        if args.verbose:
            for diagnostic in result.diagnostics:
                print(diagnostic, file=sys.stderr)
        for model in result.models:
            print(" ".join(symbol.render() for symbol in model.symbols))
        return 0 if result.satisfiable else 10
    except EngineError as exc:
        print(f"{exc.category.value} error: {exc.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
