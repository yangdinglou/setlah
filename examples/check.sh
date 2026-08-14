#!/bin/sh
set -eu

run() {
    name=$1
    shift
    printf '%-16s' "$name"
    if "$@" >/dev/null; then
        echo " SAT"
    else
        status=$?
        echo " FAILED (exit $status)" >&2
        exit "$status"
    fi
}

run "choice" setlah examples/choose.sl examples/choose.lp
run "n-queens (4)" setlah examples/maple-set/nqueen.sl examples/instances/nqueen-4.lp --grounding --cost-conversion
run "GL square (3)" setlah examples/maple-set/GL.sl examples/instances/gl-3.lp --grounding --cost-conversion
run "clique (k=3)" setlah examples/maple-set/clique.sl examples/instances/clique-4.lp --grounding --cost-conversion
run "Sudoku" setlah examples/maple-set/sudoku.sl examples/instances/sudoku-easy.lp --grounding --cost-conversion
run "Einstein" setlah examples/maple-set/einstein.sl examples/instances/einstein.lp --grounding --cost-conversion
run "15-puzzle" setlah examples/maple-set/15.sl examples/instances/15-solved.lp --grounding --cost-conversion
