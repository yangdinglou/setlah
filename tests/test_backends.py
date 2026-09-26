"""Solver-level lowerings (docs/order-sorts.md, Section 12): the compiled program grounded,
completed and decided by a SAT solver (pysat) or by MonoSAT with its graph theory for
``#edge``; tight programs only."""
import os
import pytest

from setlah.parsing.parser import Parser
from setlah.lowering import DirectLowerer
from setlah.transpile import transpile_program_to_asp, run_sat_source, run_monosat_source
from setlah.ext.ground import NotTight, NotSupported

HERE = os.path.join(os.path.dirname(__file__), "inputs")


def compile_sl(path, **kw):
    program = Parser().parse(open(path).read())
    DirectLowerer(**kw).rewrite_program(program)
    return transpile_program_to_asp(program)


def test_sat_backend_on_an_enumerated_order_sort():
    """The strict-order model under the enumeration lowering (choice rules, grounded
    comparisons): pysat agrees with clingo on the chain and the cycle."""
    pytest.importorskip("pysat")
    asp = compile_sl(os.path.join(HERE, "order", "strict_order.sl"), order_lowering="enum")
    assert run_sat_source(asp, extra_files=[os.path.join(HERE, "order", "strict_order_chain.lp")]).satisfiable
    assert not run_sat_source(asp, extra_files=[os.path.join(HERE, "order", "strict_order_cycle.lp")]).satisfiable


def test_sat_backend_on_the_relational_lowering():
    """The relational lowering has a class bound as a #count aggregate: the cardinality
    encoding in both directions."""
    pytest.importorskip("pysat")
    asp = compile_sl(os.path.join(HERE, "order", "strict_order.sl"), order_lowering="rel")
    assert "#count" in asp
    r = run_sat_source(asp, extra_files=[os.path.join(HERE, "order", "strict_order_chain.lp")])
    assert r.satisfiable and r.stats["cards"] >= 1
    assert not run_sat_source(asp, extra_files=[os.path.join(HERE, "order", "strict_order_cycle.lp")]).satisfiable


def test_sat_backend_refuses_edges_and_closures():
    pytest.importorskip("pysat")
    asp = compile_sl(os.path.join(HERE, "acyclic", "polygraph.sl"))
    with pytest.raises(NotSupported):
        run_sat_source(asp, extra_files=[os.path.join(HERE, "acyclic", "polygraph_sat.lp")])
    asp = compile_sl(os.path.join(HERE, "acyclic", "polygraph.sl"), acyclic_lowering="closure")
    with pytest.raises(NotTight):
        run_sat_source(asp, extra_files=[os.path.join(HERE, "acyclic", "polygraph_sat.lp")])


def test_monosat_backend_decides_polygraphs():
    """Cobra's solver from the same model text: the completion plus the graph theory."""
    pytest.importorskip("monosat")
    asp = compile_sl(os.path.join(HERE, "acyclic", "polygraph.sl"))
    r = run_monosat_source(asp, extra_files=[os.path.join(HERE, "acyclic", "polygraph_sat.lp")])
    assert r.satisfiable and r.stats["edges"] >= 1
    assert not run_monosat_source(asp, extra_files=[os.path.join(HERE, "acyclic", "polygraph_unsat.lp")]).satisfiable


def test_monosat_backend_on_the_layered_relation():
    pytest.importorskip("monosat")
    asp = compile_sl(os.path.join(HERE, "acyclic", "layered.sl"))
    assert run_monosat_source(asp, extra_files=[os.path.join(HERE, "acyclic", "layered_sat.lp")]).satisfiable
    assert not run_monosat_source(asp, extra_files=[os.path.join(HERE, "acyclic", "layered_unsat.lp")]).satisfiable
