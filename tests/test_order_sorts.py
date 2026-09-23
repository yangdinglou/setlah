"""Order sorts (docs/order-sorts.md): the difference-logic lowering.

The strict-order model (``x(A) < x(B)`` along ``p``) is satisfiable on a chain
and unsatisfiable on a cycle; the DPQA placement model (the applications
study's Domain ten) is unsatisfiable with 3 stages and satisfiable with 4 on
the first 10-qubit graph, as the tool, the hand-written clingo-dl program and
Z3 all answer.
"""
import os
import pytest

from setlah.parsing.parser import Parser
from setlah.lowering import DirectLowerer
from setlah.transpile import transpile_program_to_asp, run_clingodl_source

HERE = os.path.join(os.path.dirname(__file__), "inputs", "order")


DL = ("dl",)


def compile_sl(name, order_lowering="dl", extensions=DL):
    """Compile with an explicit lowering (the default selection is tested on its own)."""
    program = Parser().parse(open(os.path.join(HERE, name)).read())
    DirectLowerer(order_lowering=order_lowering, extensions=extensions).rewrite_program(program)
    return transpile_program_to_asp(program)


def solve(asp, facts):
    pytest.importorskip("clingodl")
    return run_clingodl_source(asp, extra_files=[os.path.join(HERE, facts)]).satisfiable


def test_lowering_emits_theory_atoms():
    asp = compile_sl("strict_order.sl")
    assert "&diff{ x(A0) } <= 15" in asp and "&diff{ x(A0) } >= 0" in asp
    assert "{ __dl_0(" in asp and "&diff{ x(B) - x(A) } <= 0 :- __dl_0(B, A)." in asp
    assert ":- p(A, B), __dl_0(B, A)." in asp


def test_strict_order_chain_and_cycle():
    asp = compile_sl("strict_order.sl")
    assert solve(asp, "strict_order_chain.lp") is True
    assert solve(asp, "strict_order_cycle.lp") is False


def test_dpqa_stage_counts():
    asp = compile_sl("dpqa.sl")
    assert solve(asp, "dpqa_10_0_s3.lp") is False
    assert solve(asp, "dpqa_10_0_s4.lp") is True


def test_sum_of_two_values_falls_back_to_enumeration():
    src = open(os.path.join(HERE, "strict_order.sl")).read().replace("(< X1 X2)", "(< (+ X1 X2) 3)")
    program = Parser().parse(src)
    DirectLowerer(extensions=DL).rewrite_program(program)
    assert program._order_modes == {"X": "enum"}
    with pytest.raises(Exception, match="difference constraint"):
        DirectLowerer(order_lowering="dl", extensions=DL).rewrite_program(Parser().parse(src))


def compile_sl_with(name, order_lowering, extensions=DL):
    return compile_sl(name, order_lowering, extensions)


def solve_plain(asp, facts):
    from setlah.transpile import run_clingo_ast, _parse_asp_to_clingo_ast
    return run_clingo_ast(_parse_asp_to_clingo_ast(asp), extra_files=[os.path.join(HERE, facts)]).satisfiable


def test_enumeration_lowering_is_the_basic_one():
    asp = compile_sl("strict_order.sl", "enum", ())
    assert "dom_X(0..15)." in asp and "1 { x(A0, V) : dom_X(V) } 1 :- dom_Q(A0)." in asp and "&diff{" not in asp
    assert solve_plain(asp, "strict_order_chain.lp") is True
    assert solve_plain(asp, "strict_order_cycle.lp") is False


def test_dpqa_enumeration_unsat_at_three_stages():
    asp = compile_sl("dpqa_two_axes.sl", "enum", ())
    assert solve_plain(asp, "dpqa_10_0_s3.lp") is False


def test_relational_lowering_emits_a_preorder():
    asp = compile_sl_with("strict_order.sl", "rel")
    assert "&diff{" not in asp
    assert "{ __le_X(E1, E2) } :- __el_X(E1), __el_X(E2), E1 != E2." in asp
    assert ":- __le_X(E1, E2), __le_X(E2, E3), not __le_X(E1, E3)." in asp
    assert ":- p(A, B), __le_X(x(B), x(A))." in asp


def test_relational_lowering_chain_and_cycle():
    pytest.importorskip("clingo")
    from setlah.transpile import transpile_program_to_clingo, run_clingo_ast
    program = Parser().parse(open(os.path.join(HERE, "strict_order.sl")).read())
    DirectLowerer(order_lowering="rel").rewrite_program(program)
    tr = transpile_program_to_clingo(program)
    assert run_clingo_ast(tr.ast, extra_files=[os.path.join(HERE, "strict_order_chain.lp")]).satisfiable is True
    assert run_clingo_ast(tr.ast, extra_files=[os.path.join(HERE, "strict_order_cycle.lp")]).satisfiable is False


def test_relational_lowering_rejects_offsets():
    src = open(os.path.join(HERE, "strict_order.sl")).read().replace("(< X1 X2)", "(< (+ X1 1) X2)")
    program = Parser().parse(src)
    with pytest.raises(Exception, match="without offsets"):
        DirectLowerer(order_lowering="rel", extensions=DL).rewrite_program(program)
        transpile_program_to_asp(program)


def test_offsets_go_to_enumeration_without_the_extension():
    src = open(os.path.join(HERE, "strict_order.sl")).read().replace("(< X1 X2)", "(< (+ X1 1) X2)")
    program = Parser().parse(src)
    DirectLowerer(extensions=()).rewrite_program(program)
    assert program._order_modes == {"X": "enum"}


def test_dpqa_mixed_lowerings_agree():
    """Sites as a preorder per axis, AOD columns in difference logic: same verdicts as all-dl."""
    asp = compile_sl_with("dpqa_two_axes.sl", "X=rel,Y=rel,C=dl")
    assert "__le_X(" in asp and "__le_Y(" in asp and "&diff{ c(" in asp
    assert solve(asp, "dpqa_10_0_s3.lp") is False
    assert solve(asp, "dpqa_10_0_s4.lp") is True


def test_automatic_selection_prefers_the_relation_and_uses_theory_only_where_needed():
    program = Parser().parse(open(os.path.join(HERE, "dpqa_two_axes.sl")).read())
    DirectLowerer(extensions=DL).rewrite_program(program)
    assert program._order_modes == {"X": "rel", "Y": "rel", "C": "dl"}
    asp = transpile_program_to_asp(program)
    assert "__le_X(" in asp and "__le_Y(" in asp and "&diff{ c(" in asp and "&diff{ x(" not in asp
