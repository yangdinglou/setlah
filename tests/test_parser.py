import sys
import os

# Add parent directory to path

from setlah.parsing.parser import Parser

def test_file_parsing(filename='example.sl'):
    # Path to the example.mylang file (assumed to be in root or same dir)
    # We look one level up from 'tests/'
    file_path = os.path.join(os.path.dirname(__file__), 'inputs', filename)
    
    if not os.path.exists(file_path):
        print(f"Error: Could not find {file_path}")
        return

    print(f"Reading from: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    print("--- Parsing Content ---")
    p = Parser()
    try:
        ast = p.parse(content)
        print("✅ Success! AST Generated.")
        print(f"  - Domains parsed: {len(ast.domains)}")
        print(f"  - Blocks parsed:  {len(ast.blocks)}")
        
        # print the AST, in a tree format
        print("\n--- AST Structure ---")
        print(ast.dump())
        
        
    except Exception as e:
        print(f"❌ Parse Error: {e}")
        # Print a snippet of the file around the error if possible
        # (Lark usually handles this, but we can add custom debug here if needed)

if __name__ == "__main__":
    filename = sys.argv[1] if len(sys.argv) > 1 else 'example.sl'
    print(f"Testing parsing for file: {filename}")
    test_file_parsing(filename)

# ---------------------------------------------------------- LALR (2026-09-18)

import time as _time

from setlah.ast import nodes as _nodes
from setlah.parsing.parser import Parser as _Parser


def _statements(source):
    return _Parser().parse(source).blocks[0].statements


def test_bare_atom_statement_is_a_fact_and_other_shapes_are_constraints():
    """The LALR grammar reserves a bare predicate atom statement for facts, the
    reading the Earley parser already gave it; comparisons, quantified formulas,
    aggregates and parenthesised formulas are constraints."""
    src = """ExtDOM U: INT.
ExtPred q: (U).
[
    p(X)? :- dom_U(X).
    p(1).
    (= X X).
    X = X.
    \\forall X. p(X).
    (\\neg p(3)).
    #count {Set_p}(X) >= 1.
    #count {Set_p} = 1.
    Let {A} = { (X) | (X) in {P}, \\true } in (\\subset A {P}).
]
"""
    stmts = _statements(src)
    kinds = [type(s).__name__ for s in stmts]
    assert kinds == ["Rule", "Rule"] + ["SetConstraint"] * 7, kinds
    agg_with, agg_without = stmts[6], stmts[7]
    assert agg_with.formula.set_var.parameters is not None and agg_with.formula.comp_op == ">="
    assert agg_without.formula.set_var.parameters is None and agg_without.formula.comp_op == "=="
    let = stmts[8]
    assert let.let_exprs[0].variable.name == "A"


def test_atom_without_arguments_parses():
    src = "ExtDOM U: INT.\nConst k: INT = 3.\n[\n    flag()? :- dom_U(X).\n    flag().\n    (\\neg flag()).\n]\n"
    program = _Parser().parse(src)
    assert program.domains[1].value.value == 3
    stmts = program.blocks[0].statements
    assert isinstance(stmts[1], _nodes.Rule) and stmts[1].head.args == []


def test_parse_time_is_linear_in_statements():
    """A performance regression guard: 2,000 constraint statements must parse in
    a few seconds (LALR), not the tens of seconds the Earley parser took."""
    body = ["ExtDOM D: INT.", "ExtPred base: (D, D).", "ExtPred tag: (D).", "", "[", "    pick(X, Y)? :- base(X, Y)."]
    for i in range(2000):
        body.append("    \\forall X, Y. (\\impl (\\and pick(X, Y) tag(X)) (\\exists Z. (\\and base(Y, Z) tag(Z))))." )
    body.append("]")
    src = "\n".join(body) + "\n"
    t0 = _time.perf_counter()
    stmts = _statements(src)
    dt = _time.perf_counter() - t0
    assert len(stmts) == 2001
    assert dt < 8.0, f"parse took {dt:.1f}s"
