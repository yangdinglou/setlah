"""``(\\acyclic r)`` lowers to clingo's ``#edge`` over the relation's edges."""
import os
import pytest

from setlah.parsing.parser import Parser
from setlah.lowering import DirectLowerer
from setlah.transpile import transpile_program_to_asp, transpile_program_to_clingo, run_clingo_ast

HERE = os.path.join(os.path.dirname(__file__), "inputs")


def compile_sl(path):
    program = Parser().parse(open(path).read())
    DirectLowerer().rewrite_program(program)
    return program


def solve(program, facts):
    pytest.importorskip("clingo")
    return run_clingo_ast(transpile_program_to_clingo(program).ast, extra_files=[facts]).satisfiable


def test_acyclic_lowers_to_edge():
    program = compile_sl(os.path.join(HERE, "acyclic", "external.sl"))
    assert "#edge (X0, Y0) : p(X0, Y0)." in transpile_program_to_asp(program)


def test_acyclic_external_relation():
    program = compile_sl(os.path.join(HERE, "acyclic", "external.sl"))
    assert solve(program, os.path.join(HERE, "order", "strict_order_chain.lp")) is True
    assert solve(program, os.path.join(HERE, "order", "strict_order_cycle.lp")) is False


def test_acyclic_over_a_chosen_relation():
    """Cobra's polygraph in miniature: fixed edges 1->2->3 and one constraint with two
    alternatives; satisfiable when one alternative closes no cycle, unsatisfiable when both do."""
    program = compile_sl(os.path.join(HERE, "acyclic", "polygraph.sl"))
    assert solve(program, os.path.join(HERE, "acyclic", "polygraph_sat.lp")) is True
    assert solve(program, os.path.join(HERE, "acyclic", "polygraph_unsat.lp")) is False


def test_acyclic_relation_defined_by_rules_is_inlined_into_edges():
    """The layered snapshot-isolation form: a 4-ary relation defined by three rules and used
    only under (\\acyclic ...) is not materialised; one #edge per rule with the body as condition."""
    program = compile_sl(os.path.join(HERE, "acyclic", "layered.sl"))
    asp = transpile_program_to_asp(program)
    assert "#edge ((X, 0), (Y, 0)) : n(X, Y)." in asp and "#edge ((X, 1), (Y, 0)) : n(X, Y)." in asp and "#edge ((X, 0), (Y, 1)) : rw(X, Y)." in asp
    assert "dl(" not in asp.replace("#edge", "")
    assert solve(program, os.path.join(HERE, "acyclic", "layered_sat.lp")) is True     # n 1->2, rw 2->3, rw 3->1: two adjacent anti-dependencies, allowed under SI
    assert solve(program, os.path.join(HERE, "acyclic", "layered_unsat.lp")) is False  # n cycle 1->2->3->1 on layer 0
