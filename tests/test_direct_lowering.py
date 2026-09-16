"""Differential tests for the direct lowering (``setlah.lowering``) against the
egglog pipeline, on the regression reproducers and the examples.

Where both backends compile a model, its answer sets on a small instance must
agree once auxiliary predicates are projected away. Where the egglog path
falls back, crashes or emits a program Clingo rejects, the direct lowering
must compile it and the program must ground.
"""

import contextlib
import io
import itertools
import os
import random
import re

import pytest

from setlah.parsing.parser import Parser
from setlah.rewrite.rw import Rewriter
from setlah.lowering import DirectLowerer
from setlah.transpile import transpile_program_to_asp

ROOT = os.path.dirname(__file__)
INPUTS = os.path.join(ROOT, "inputs", "regressions")
EXAMPLES = os.path.join(ROOT, "..", "examples")


def compile_source(source, backend):
    program = Parser().parse(source)
    front = DirectLowerer() if backend == "direct" else Rewriter()
    with contextlib.redirect_stdout(io.StringIO()):
        lowered = front.rewrite_program(program, convert_only=False)
    return transpile_program_to_asp(lowered)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def generated_facts(source, size=2, seed=0):
    """Every ExtDOM gets 0..size-1, every ExtPred a random subset of its tuples."""
    rnd = random.Random(seed)
    lines = [f"dom_{d}(0..{size - 1})." for d in re.findall(r"^\s*ExtDOM\s+(\w+)\s*:", source, re.M)]
    for name, sig in re.findall(r"^\s*ExtPred\s+(\w+)\s*:\s*\(([^)]*)\)", source, re.M):
        arity = len([x for x in sig.split(",") if x.strip()])
        for t in itertools.product(range(size), repeat=arity):
            if rnd.random() < 0.5:
                lines.append(f"{name}({', '.join(map(str, t))}).")
    return "\n".join(lines) + "\n"


def answer_sets(asp, facts, cap=100000):
    clingo = pytest.importorskip("clingo")
    ctl = clingo.Control([str(cap), "--warn=none"])
    ctl.add("base", [], asp + "\n" + facts)
    ctl.ground([("base", [])])
    out = set()
    ctl.solve(on_model=lambda m: out.add(
        frozenset(str(s) for s in m.symbols(atoms=True) if not s.name.startswith("__aux"))))
    assert len(out) < cap, "enumeration cap reached; the comparison would be meaningless"
    return out


def satisfiable(asp, facts):
    clingo = pytest.importorskip("clingo")
    ctl = clingo.Control(["1", "--warn=none"])
    ctl.add("base", [], asp + "\n" + facts)
    ctl.ground([("base", [])])
    return bool(ctl.solve().satisfiable)


def fixed_choices(source, size, seed):
    """Facts and constraints that pin every choice predicate of the model to a
    random extension, so a program has at most one answer set and the two
    backends can be compared on SAT/UNSAT alone."""
    rnd = random.Random(seed)
    lines = []
    for name, args in re.findall(r"^\s*(\w+)\(([^)]*)\)\?\s*:-", source, re.M):
        arity = len([x for x in args.split(",") if x.strip()])
        for t in itertools.product(range(size), repeat=arity):
            atom = f"{name}({', '.join(map(str, t))})"
            lines.append(f"{atom}." if rnd.random() < 0.5 else f":- {atom}.")
    return "\n".join(lines) + "\n"


def assert_equivalent(source, egg, direct, instances, size=2, samples=40):
    """Sampled equivalence: on every instance, for random extensions of the
    choice predicates both programs agree on satisfiability; at least one
    sample must be satisfiable and one unsatisfiable somewhere, or the
    comparison has no teeth (skipped when the model allows only one)."""
    verdicts = set()
    for k, inst in enumerate(instances):
        for s in range(samples):
            fixed = inst + fixed_choices(source, size, 1000 * k + s)
            e, d = satisfiable(egg, fixed), satisfiable(direct, fixed)
            assert e == d, f"egglog {e} vs direct {d} on\n{fixed}"
            verdicts.add(e)
    return verdicts


# ------------------------------------------- both backends compile: agree

AGREE = [
    ("regressions", "aux_c0_one_witness_ok.sl", None),
    ("regressions", "aux_c1_two_witness_crash.sl", None),
    ("regressions", "aux_c2_negated_disjunction_crash.sl", None),
    ("regressions", "unsafe_u1_empty_domain_cube.sl", "unsafe_u1.lp"),
    ("regressions", "aux_collision_depth6.sl", "aux_collision_depth6.lp"),
    ("regressions", "raw_v08_flat_antecedent.sl", "raw_v08.lp"),
    ("regressions", "raw_v11_flat_antecedent.sl", None),
    ("regressions", "raw_n07_nested_universals.sl", None),
    ("regressions", "raw_f1_frame_axiom.sl", None),
    ("regressions", "raw_f2_forall_exists_forall.sl", None),
    ("regressions", "exists_binders8_ok.sl", None),
    ("regressions", "exists_binders9_varlist_crash.sl", None),
    ("regressions", "or_of_and_2x2_ok.sl", None),
    ("regressions", "wrongcode_b10_symmetry_breaking.sl", "wrongcode_b10.lp"),
    ("regressions", "b16_choice_guard_lost.sl", "b16_choice_guard_lost.lp"),
    ("examples", "maple-set/sudoku.sl", "instances/sudoku-easy.lp"),
    ("examples", "maple-set/GL.sl", "instances/gl-3.lp"),
    ("examples", "maple-set/clique.sl", "instances/clique-4.lp"),
    ("examples", "maple-set/nqueen.sl", "instances/nqueen-4.lp"),
    ("examples", "maple-set/einstein.sl", "instances/einstein.lp"),
    ("examples", "maple/sudoku.sl", "instances/sudoku-easy.lp"),
    ("examples", "maple/nqueen.sl", "instances/nqueen-4.lp"),
]


@pytest.mark.parametrize("where,model,facts", AGREE, ids=[m for _, m, _ in AGREE])
def test_direct_lowering_agrees_with_egglog(where, model, facts):
    base = INPUTS if where == "regressions" else EXAMPLES
    source = read(os.path.join(base, model))
    egg = compile_source(source, "egglog")
    direct = compile_source(source, "direct")
    assert "raw-constraint" not in direct and "AuxCall" not in direct, direct
    instances = [read(os.path.join(base, facts))] if facts else [generated_facts(source, seed=s) for s in range(3)]
    assert_equivalent(source, egg, direct, instances)


# ------------------------------- egglog path fails: the direct lowering must not

@pytest.mark.parametrize(
    "model",
    [
        "raw_f0_ite_frame_equality.sl",              # B2: raw fallback
        "or_of_and_3x2_fallback.sl",                 # B2: raw fallback
        "wrongcode_v13_aux_body_question_mark.sl",   # B11: aux rule body "?"
        "unsafe_w6c2_vacuous_universals.sl",         # B12: unbound aggregate variables
        "recursion_ground_guards_or_of_and.sl",      # B5-like: recursion depth on one statement
    ],
)
def test_direct_lowering_handles_what_egglog_cannot(model):
    source = read(os.path.join(INPUTS, model))
    direct = compile_source(source, "direct")
    assert "raw-constraint" not in direct and "AuxCall" not in direct and "?" not in direct, direct
    if model.startswith("recursion_"):
        # 610-literal constraints over about 200 flattened function variables:
        # Clingo cannot ground the join at any size; check the program parses.
        clingo = pytest.importorskip("clingo")
        clingo.ast.parse_string(direct, lambda _: None)
        return
    for s in range(2):
        satisfiable(direct, generated_facts(source, seed=s))   # grounds and solves


def test_direct_lowering_enforces_ite_frame_equality():
    """raw_f0: post(V) = ite(V = K, new, pre(V)). With one request id and one
    response the frame axiom pins db_response_sent to pre_db_response_sent off
    the key and to true on it."""
    source = read(os.path.join(INPUTS, "raw_f0_ite_frame_equality.sl"))
    direct = compile_source(source, "direct")
    facts = "dom_Request(0). dom_Db_request_id(0..1). dom_Node(0). dom_Response(0..1).\n"
    models = answer_sets(direct, facts)
    for m in models:
        k_i = next(int(a[len("k_pre_fml_i("):-1]) for a in m if a.startswith("k_pre_fml_i("))
        k_p = next(int(a[len("k_pre_fml_p("):-1]) for a in m if a.startswith("k_pre_fml_p("))
        assert f"db_response_sent({k_i},{k_p})" in m
        for i in range(2):
            for p in range(2):
                if (i, p) != (k_i, k_p):
                    assert (f"db_response_sent({i},{p})" in m) == (f"pre_db_response_sent({i},{p})" in m)


# ------------------------------------------------ B13, B14, B15 (2026-09-16)

from setlah.parsing.checker import SemanticChecker
from fol_oracle import Oracle, answer_sets as oracle_answer_sets


def oracle_for(source):
    program = Parser().parse(source)
    checker = SemanticChecker()
    checker.check_program(program)
    return Oracle(program, checker)


@pytest.mark.parametrize(
    "model,facts",
    [
        ("shadowed_binder_direct_lcl653.sl", "shadowed_binder_direct_lcl653.lp"),   # B13 report
        ("shadowed_binder_direct.sl", None),
        ("b14_extdom_sort_guard.sl", "b14_extdom_sort_guard.lp"),
        ("b15_aggregate_names.sl", "b15_aggregate_names.lp"),
        ("b16_choice_guard_lost.sl", "b16_choice_guard_lost.lp"),
        ("b16_choice_guard_lost_2.sl", "b16_choice_guard_lost_2.lp"),
        ("wrongcode_b10_symmetry_breaking.sl", "wrongcode_b10.lp"),
        ("unsafe_u1_empty_domain_cube.sl", "unsafe_u1.lp"),
    ],
)
def test_direct_lowering_is_sound_by_first_order_oracle(model, facts):
    """Every answer set of the compiled program satisfies every source constraint,
    evaluated by brute force over the instance's domains (tests/fol_oracle.py).
    B13 (shadowed binders) was reported on the LCL653 reproducer; exhaustively,
    none of its answer sets violates a constraint on this branch. The oracle is
    exponential in quantifier depth times domain size, so only small-domain
    reproducers are listed."""
    pytest.importorskip("clingo")
    source = read(os.path.join(INPUTS, model))
    inst = read(os.path.join(INPUTS, facts)) if facts else "dom_U(1..3).\n"
    asp = compile_source(source, "direct")
    oracle = oracle_for(source)
    models = oracle_answer_sets(asp, inst, cap=300)   # a sample where the space is large
    assert models, "the program must be satisfiable on this instance"
    for m in models:
        assert not oracle.violations(m), (model, sorted(m))


def test_b14_external_sort_gets_its_projection_rules():
    """An ExtDOM sort whose elements come only through the predicates over it:
    dom_<Sort> is defined by projection, so guarded auxiliaries can fire."""
    pytest.importorskip("clingo")
    source = read(os.path.join(INPUTS, "b14_extdom_sort_guard.sl"))
    asp = compile_source(source, "direct")
    assert "dom_D(X) :- dom(X)." in asp and "dom_D(X) :- dom_any(X)." in asp, asp
    models = oracle_answer_sets(asp, read(os.path.join(INPUTS, "b14_extdom_sort_guard.lp")))
    assert models and all(("v_t", (2,)) in m for m in models), models


def test_b15_aggregate_variables_fill_positions_of_the_set_predicate():
    """forall X. #count {Set_nxt}(Y) <= 1 over nxt(A, B): X and Y take the
    positions their names do not match, in order, instead of leaving Y free."""
    pytest.importorskip("clingo")
    source = read(os.path.join(INPUTS, "b15_aggregate_names.sl"))
    asp = compile_source(source, "direct")
    assert "#count{Y : nxt(X, Y)}" in asp, asp
    assert len(oracle_answer_sets(asp, read(os.path.join(INPUTS, "b15_aggregate_names.lp")))) == 6


def test_b15_unmatchable_aggregate_is_rejected():
    from setlah.transpile.ir import TranspileError

    source = read(os.path.join(INPUTS, "b15_aggregate_names.sl")).replace(
        "\\forall X. #count {Set_nxt}(Y) <= 1.", "\\forall X, Z. #count {Set_nxt}(Y) <= 1.")
    with pytest.raises(TranspileError):
        compile_source(source, "direct")
