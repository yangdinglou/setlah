"""Rule decomposition (--split-width): the split program must have the same answer sets over the
original signature as the unsplit one, and every generated rule must be safe."""
import subprocess, sys, os, textwrap, tempfile
import clingo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODEL = textwrap.dedent('''
    ExtDOM U: INT.

    [
        p(X, Y)? :- dom_U(X), dom_U(Y).
        q(X)? :- dom_U(X).
        (\\forall A, B, C, D, E. (\\impl (\\and dom_U(A) dom_U(B) dom_U(C) dom_U(D) dom_U(E) p(A, B) p(B, C) p(C, D) p(D, E)) (\\or q(A) q(E)))).
        (\\forall A, B, C, D. (\\impl (\\and dom_U(A) dom_U(B) dom_U(C) dom_U(D)) (\\or (= A B) (= C D) p(A, D)))).
    ]
''')
FACTS = "dom_U(1..3).\n"


def compile_(width: int) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".sl", delete=False) as f:
        f.write(MODEL); path = f.name
    out = subprocess.run([sys.executable, "-m", "setlah", path, "--print-asp", "--lowering", "direct", "--split-width", str(width)],
                         capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src")))
    assert out.returncode == 0, out.stderr
    return out.stdout


def answer_sets(asp: str) -> set:
    ctl = clingo.Control(["0", "--warn=none"]); ctl.add("base", [], asp + FACTS); ctl.ground([("base", [])])
    models = set()
    ctl.solve(on_model=lambda m: models.add(frozenset(str(a) for a in m.symbols(atoms=True) if str(a).startswith(("p(", "q(")))))
    return models


def test_split_preserves_answer_sets():
    plain, split = compile_(0), compile_(3)
    assert "__aux" not in plain and "__aux" in split, split
    assert answer_sets(plain) == answer_sets(split)


def test_split_rules_are_safe():
    split = compile_(2)
    ctl = clingo.Control(["--warn=none"]); ctl.add("base", [], split + FACTS)
    ctl.ground([("base", [])])   # raises on an unsafe rule


def test_split_keeps_head_variables():
    """A DuoAI query (ivy-254-0021, unsatisfiable): an early version of the pass eliminated a head variable of
    an auxiliary rule into a temporary, projecting it away, and the split program became satisfiable."""
    sl = os.path.join(ROOT, "tests", "inputs", "regressions", "split_keep_head_var.sl")
    lp = open(os.path.join(ROOT, "tests", "inputs", "regressions", "split_keep_head_var.lp")).read()
    for width in (0, 3):
        out = subprocess.run([sys.executable, "-m", "setlah", sl, "--print-asp", "--lowering", "direct", "--split-width", str(width)],
                             capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src")))
        assert out.returncode == 0, out.stderr
        ctl = clingo.Control(["1", "--warn=none"]); ctl.add("base", [], out.stdout + lp); ctl.ground([("base", [])])
        assert not ctl.solve().satisfiable, "width %d" % width
