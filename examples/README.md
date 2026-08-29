# Examples

Executable models are under `maple-set/`; their input facts are under
`instances/`. Run these commands from the repository root after installing
SetLaH.

## Basic Choice

```bash
setlah examples/choose.sl examples/choose.lp
```

This model chooses a non-empty subset of three available items.

## N-Queens

```bash
setlah examples/maple-set/nqueen.sl examples/instances/nqueen-4.lp \
  --grounding --cost-conversion
```

The fact file sets the board size to four.

## Graeco-Latin Square

```bash
setlah examples/maple-set/GL.sl examples/instances/gl-3.lp \
  --grounding --cost-conversion
```

## Clique

```bash
setlah examples/maple-set/clique.sl examples/instances/clique-4.lp \
  --grounding --cost-conversion
```

The supplied graph contains a clique of size three.

## Sudoku

```bash
setlah examples/maple-set/sudoku.sl examples/instances/sudoku-easy.lp \
  --grounding --cost-conversion
```

## Einstein Puzzle

```bash
setlah examples/maple-set/einstein.sl examples/instances/einstein.lp \
  --grounding --cost-conversion
```

## 15-Puzzle

```bash
setlah examples/maple-set/15.sl examples/instances/15-solved.lp \
  --grounding --cost-conversion
```

The supplied board is already solved and uses a move bound of zero.

## Check Every Executable Example

```bash
./examples/check.sh
```

## Python Embedding

Run the same basic Choice workflow through the in-process Python API:

```bash
python examples/python_choice.py
```

The example constructs typed facts, solves one model, and reads `selected/1`
atoms from the structured result. See `docs/python.md` for the complete guide.

The script prints `SAT` or `UNSAT` for each expected result and exits nonzero if
a command fails or produces the wrong status.

Input files are ordinary Clingo programs. To add an instance, provide all
`ExtDOM`, `ExtPred`, and constant inputs expected by its `.sl` model. New
executable models should also be added to `check.sh`.

The similarly named models under `maple/` use experimental compiler shorthand.
They are retained for compiler development; use `maple-set/` for direct solving.
