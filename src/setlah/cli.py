import argparse
import os
import sys
import time

import contextlib
import io

from setlah import __version__
from setlah.parsing.parser import Parser
from setlah.transpile import transpile_program_to_asp, transpile_program_to_clingo, run_clingo_ast, run_clingodl_source

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SetLaH -> (egg) -> Clingo transpiler (FO only)")
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
        "--cost-conversion",
        action="store_true",
        help="Run cost conversion saturation before extraction (enables aggregate lowering rewrites)",
    )
    ap.add_argument(
        "--entailment-elim",
        choices=["asp", "egg", "both", "none"],
        default="asp",
        help="Where to apply entailment-based literal elimination (default: asp)",
    )
    ap.add_argument("--print-asp", action="store_true", help="Print transpiled ASP and exit")
    ap.add_argument(
        "--grounding",
        action="store_true",
        help="Apply all safe post-processing ground/aggregate rewrites (otherwise only when mergeable)",
    )
    ap.add_argument("--clingo-arg", action="append", default=[], help="Extra argument passed to clingo (repeatable)")
    ap.add_argument(
        "--order-lowering",
        default=None,
        help="Lowering of order sorts: auto (default: a preorder relation where every comparison is between two values without offsets, difference logic otherwise), dl, rel, or per sort as X=rel,C=dl; "
        "the default can be set with SETLAH_ORDER_LOWERING",
    )
    ap.add_argument(
        "--backend",
        choices=["auto", "clingo", "clingo-dl"],
        default="auto",
        help="Solver: clingo, or clingo-dl for programs with order sorts (auto: clingo-dl when the compiled program has &diff atoms)",
    )
    ap.add_argument(
        "--lowering",
        choices=["direct", "egglog"],
        default=os.environ.get("SETLAH_LOWERING", "direct"),
        help="Front half: the direct syntax-directed lowering (default) or the deprecated equality-saturation "
        "rewriting in egglog; the default can be set with the SETLAH_LOWERING environment variable",
    )
    args = ap.parse_args(argv)

    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()

    # Phase: Parsing
    if args.verbose:
        print("=" * 60)
        print("PARSING")
        print("=" * 60)
        t0 = time.perf_counter()
    program = Parser().parse(text)
    if args.verbose:
        print(f"Parsing time: {time.perf_counter() - t0:.3f}s")
        print()

    # Phase: Rewriting
    if args.verbose:
        print("=" * 60)
        print("REWRITING")
        print("=" * 60)
        t0 = time.perf_counter()
    # Import the selected front half only: the egglog import alone costs
    # about 0.4 s, which the direct lowering does not need.
    if args.lowering == "direct":
        from setlah.lowering import DirectLowerer as front
    else:
        print(
            "warning: --lowering egglog is deprecated and will be removed in a later release; "
            "the direct lowering is the default (docs/retire-egglog-proposal.md)",
            file=sys.stderr,
        )
        from setlah.rewrite.rw import Rewriter as front
    front_kwargs = dict(verbose=args.verbose, entailment_elim=args.entailment_elim, enable_cost_conversion=args.cost_conversion)
    if args.lowering == "direct":
        front_kwargs["order_lowering"] = args.order_lowering
    rw = front(**front_kwargs)
    if args.verbose:
        rewritten = rw.rewrite_program(program, convert_only=False)
        print(f"Total rewriting time: {time.perf_counter() - t0:.3f}s")
        print()
    else:
        # egglog can be noisy on stdout; keep CLI output clean unless --verbose.
        with contextlib.redirect_stdout(io.StringIO()):
            rewritten = rw.rewrite_program(program, convert_only=False)

    # Phase: Transpiling (post-processing)
    if args.verbose:
        print("=" * 60)
        print("TRANSPILING")
        print("=" * 60)
        t0 = time.perf_counter()
    if args.print_asp:
        asp_output = transpile_program_to_asp(rewritten, grounding=args.grounding)
        if args.verbose:
            print(f"Transpiling time: {time.perf_counter() - t0:.3f}s")
            print()
            print("=" * 60)
            print("OUTPUT")
            print("=" * 60)
        print(asp_output)
        if args.facts:
            print()
            for path in args.facts:
                with open(path, "r", encoding="utf-8") as f:
                    print(f.read())
        return 0

    asp_source = transpile_program_to_asp(rewritten, grounding=args.grounding)
    use_dl = args.backend == "clingo-dl" or (args.backend == "auto" and "&diff{" in asp_source)
    if use_dl:
        if args.verbose:
            print(f"Transpiling time: {time.perf_counter() - t0:.3f}s")
            print()

        def on_dl_model(mv):
            m, assignment = mv
            print(m)
            print(" ".join(f"{k}={v}" for k, v in assignment))

        res = run_clingodl_source(asp_source, extra_files=list(args.facts), arguments=list(args.clingo_arg), on_model=on_dl_model)
        return 0 if res.satisfiable else 10

    tr = transpile_program_to_clingo(rewritten, grounding=args.grounding)
    if args.verbose:
        print(f"Transpiling time: {time.perf_counter() - t0:.3f}s")
        print()

    def on_model(m):
        print(m)

    res = run_clingo_ast(
        tr.ast,
        extra_files=list(args.facts),
        arguments=list(args.clingo_arg),
        on_model=on_model,
    )
    return 0 if res.satisfiable else 10


if __name__ == "__main__":
    raise SystemExit(main())
