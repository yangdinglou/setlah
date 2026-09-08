"""Regression tests for the defects recorded in docs/known-issues.md.

The models under ``inputs/regressions`` are minimal reproducers taken from
third-party finite-domain problems (DuoAI and mypyvy verification queries,
Alloy commands translated by PORTUS).
"""

import contextlib
import io
import os
import re

import pytest

from setlah.parsing.parser import Parser
from setlah.rewrite.rw import Rewriter
from setlah.transpile import transpile_program_to_asp

INPUTS = os.path.join(os.path.dirname(__file__), "inputs", "regressions")


def compile_model(name):
    """Compile a model to ASP through the same phases as the command line."""
    with open(os.path.join(INPUTS, name), encoding="utf-8") as fh:
        source = fh.read()
    program = Parser().parse(source)
    with contextlib.redirect_stdout(io.StringIO()):     # egglog is noisy
        rewritten = Rewriter().rewrite_program(program, convert_only=False)
    return transpile_program_to_asp(rewritten)


def read_facts(name):
    with open(os.path.join(INPUTS, name), encoding="utf-8") as fh:
        return fh.read()


# --------------------------------------------------------------------- B1

@pytest.mark.parametrize(
    "model",
    [
        "aux_c0_one_witness_ok.sl",
        "aux_c1_two_witness_crash.sl",
        "aux_c2_negated_disjunction_crash.sl",
    ],
)
def test_b1_auxiliary_call_is_lowered(model):
    """No Literal.AuxCall may reach the transpiler (docs/known-issues.md, B1)."""
    asp = compile_model(model)
    assert "AuxCall" not in asp
    assert "raw-constraint" not in asp


def test_b1_c2_encodes_the_constraint():
    """The witness-guarded clause becomes an integrity constraint over an aux predicate."""
    asp = compile_model("aux_c2_negated_disjunction_crash.sl")
    aux_rules = [l for l in asp.splitlines() if l.startswith("__aux_") and ":-" in l]
    assert len(aux_rules) == 2, asp
    # one rule per disjunct of the negated body
    assert any("response_sent" in r for r in aux_rules), asp
    assert any("not response_received" in r for r in aux_rules), asp
    assert any(l.startswith(":- k_n1(") and "__aux_" in l for l in asp.splitlines()), asp


# ------------------------------------------- B1 root cause: binding parsing

def test_binding_prefix_multiline_after_open_paren():
    """egglog's multi-line form: the first binding follows "(" and later ones may be indented."""
    prefix = (
        '(_Formula_1 = Formula.Lit(GeneralLit.from_literal(Literal(Atom.Pred("p", nil_var()), True)))\n'
        '_VarList_1 = cons_var(Term.Var("X"), nil_var())\n'
        '    _Set_1 = Set[Term](Term.Var("X"))\n'
    )
    bindings = Rewriter.__new__(Rewriter)._parse_binding_prefix(prefix)
    assert set(bindings) == {"_Formula_1", "_VarList_1", "_Set_1"}
    # no binding's value may swallow the text of the next one
    for value in bindings.values():
        assert "=" not in value.replace("==", ""), bindings
    assert bindings["_VarList_1"] == 'cons_var(Term.Var("X"), nil_var())'


def test_binding_prefix_single_line_comma_form():
    """egglog's one-line form: bindings separated by commas."""
    prefix = '(_VarList_1 = cons_var(Term.Var("X"), nil_var()), _Set_1 = Set[Term](Term.Var("X")), '
    bindings = Rewriter.__new__(Rewriter)._parse_binding_prefix(prefix)
    assert bindings == {
        "_VarList_1": 'cons_var(Term.Var("X"), nil_var())',
        "_Set_1": 'Set[Term](Term.Var("X"))',
    }


def test_binding_prefix_ignores_uses_inside_values():
    """A name used inside a value is not a new binding."""
    prefix = "(_A = Formula.And(_B, Formula.Lit(_C))\n_B = Formula.Lit(x)\n"
    bindings = Rewriter.__new__(Rewriter)._parse_binding_prefix(prefix)
    assert bindings["_A"] == "Formula.And(_B, Formula.Lit(_C))"
    assert bindings["_B"] == "Formula.Lit(x)"


def test_binding_prefix_empty():
    assert Rewriter.__new__(Rewriter)._parse_binding_prefix("") == {}


# ------------------------------------------------- B1 fallback in transpile

def test_transpiler_lowers_surviving_literal_auxcall():
    """A two-argument Literal.AuxCall left by the rewriter is lowered, not rendered."""
    from setlah.transpile.aux import _preprocess_aux_calls

    call = (
        'Formula.Lit(GeneralLit.from_literal(Literal.AuxCall('
        'Vec[Formula]('
        'Formula.And('
        'Formula.Lit(GeneralLit.from_literal(Literal(Atom.Pred("k_res1", cons_var(Term.Var("K_RES1"), nil_var())), True))), '
        'Formula.Lit(GeneralLit.from_literal(Literal(Atom.Pred("response_sent", '
        'cons_var(Term.Var("K_N1"), cons_var(Term.Var("K_RES1"), nil_var()))), True)))), '
        'Formula.Lit(GeneralLit.from_literal(Literal(Atom.Pred("q", cons_var(Term.Var("K_N1"), nil_var())), False)))'
        '), Set[Term](Term.Var("K_RES1")))))'
    )
    out, rules = _preprocess_aux_calls(call)
    assert "AuxCall" not in out
    assert len(rules) == 2, rules                      # one rule per DNF cube
    head = rules[0].split(" :- ")[0]
    assert head.endswith("(K_N1)"), rules              # K_RES1 is quantified, so not a parameter
    assert all(r.startswith(head) for r in rules), rules
    assert "not q(K_N1)" in rules[1], rules


# --------------------------------------------------------------------- B3

def test_b3_unbound_head_variable_is_guarded():
    """An auxiliary rule whose head variable is unbound in that disjunct gets a domain
    guard, so Clingo can ground it (docs/known-issues.md, B3)."""
    asp = compile_model("unsafe_u1_empty_domain_cube.sl")
    aux_rules = [l for l in asp.splitlines() if l.startswith("__aux_") and ":-" in l]
    assert aux_rules, asp
    for rule in aux_rules:
        head, _, body = rule.partition(" :- ")
        head_vars = set(re.findall(r"\b[A-Z][A-Za-z0-9_]*\b", head))
        positive = " ".join(
            lit for lit in body.split(", ") if not lit.strip().startswith("not ")
        )
        bound = set(re.findall(r"\b[A-Z][A-Za-z0-9_]*\b", positive))
        assert head_vars <= bound, "unsafe head variables in: %s" % rule


def test_b3_program_grounds_in_clingo():
    """The compiled program is accepted by Clingo, not merely produced."""
    clingo = pytest.importorskip("clingo")
    asp = compile_model("unsafe_u1_empty_domain_cube.sl")
    ctl = clingo.Control(["1", "--warn=none"])
    ctl.add("base", [], asp + "\n" + read_facts("unsafe_u1.lp"))
    ctl.ground([("base", [])])          # raises if the program has unsafe variables
    assert ctl.solve().satisfiable is not None


# --------------------------------------------------------------------- B2 (open)

@pytest.mark.xfail(strict=True, reason="known-issues B2: an ite-valued frame equality is emitted as a raw-constraint comment")
def test_b2_ite_frame_equality_is_lowered():
    """Ivy's frame axiom as written, post(V) = ite(V = K, new, pre(V)) under the witness
    guards, must not fall back to the raw-constraint comment. Strict xfail: this test
    starts failing the moment the lowering handles the shape, and then the mark is removed."""
    asp = compile_model("raw_f0_ite_frame_equality.sl")
    assert "raw-constraint" not in asp, asp


# --------------------------------------------------------------------- B7

def aux_heads(asp):
    """Names of the auxiliary predicates defined in the compiled program."""
    return {l.split("(")[0] for l in asp.splitlines() if l.startswith("__aux_") and ":-" in l}


def test_b7_sixth_auxiliary_gets_a_fresh_name():
    """Nested universal implications of depth 6 need six auxiliaries; the sixth,
    lowered by the transpiler after the rewriter's recursion depth is spent, must
    not reuse the rewriter's first name (docs/known-issues.md, B7)."""
    asp = compile_model("aux_collision_depth6.sl")
    assert "AuxCall" not in asp and "raw-constraint" not in asp, asp
    heads = aux_heads(asp)
    assert len(heads) == 6, asp
    # every auxiliary has exactly one definition: no accidental disjunction
    for head in heads:
        assert sum(1 for l in asp.splitlines() if l.startswith(head + "(")) == 1, asp


def compile_model_in_fresh_process(name):
    """Compile through the command line in a new interpreter, as the study's
    runners do, so module state left by earlier tests cannot mask a defect."""
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "setlah", os.path.join(INPUTS, name), "--print-asp"],
        capture_output=True, text=True, check=True,
    )
    return proc.stdout


def test_b7_program_answers_the_intended_question():
    """pick(V0) is allowed unless some 6-step rel path from V0 ends in a non-p
    node: with the facts that forbids node 7 only, so 2^7 answer sets remain.
    The unfixed compiler unions the two `__aux_0` definitions and leaves 8."""
    clingo = pytest.importorskip("clingo")
    asp = compile_model_in_fresh_process("aux_collision_depth6.sl")
    ctl = clingo.Control(["0", "--warn=none"])
    ctl.add("base", [], asp + "\n" + read_facts("aux_collision_depth6.lp"))
    ctl.ground([("base", [])])
    picks = []
    ctl.solve(on_model=lambda m: picks.append(
        {s.arguments[0].number for s in m.symbols(atoms=True) if s.name == "pick"}))
    assert len(picks) == 128, len(picks)
    assert not any(7 in p for p in picks)
    assert any(p == set(range(7)) for p in picks)


def test_b7_auxiliary_names_start_afresh_per_compilation():
    """One counter per compilation unit: compiling the same model twice in one
    process gives the same program, not names continuing from the first run."""
    first = compile_model("aux_c2_negated_disjunction_crash.sl")
    second = compile_model("aux_c2_negated_disjunction_crash.sl")
    assert first == second
    assert "__aux_0(" in first, first


# --------------------------------------------------------------------- B5

def test_normalize_printed_item_multiline_bindings():
    """A printed constraint with egglog's one-per-line bindings before the term."""
    from setlah.transpile.normalize import _normalize_printed_item

    text = (
        '_VarList_1 = cons_var(Term.Var("R"), cons_var(Term.Var("C"), nil_var()))\n'
        'Constraint.integrity_constraints(\n'
        '    Set[Term](Term.Var("C"), Term.Var("R")),\n'
        '    Set[GeneralLit](GeneralLit.from_literal(Literal(Atom.Pred("initial", _VarList_1), True)), '
        'GeneralLit.from_literal(Literal(Atom.Pred("sudoku", _VarList_1), False))),\n'
        ')'
    )
    out = _normalize_printed_item(text)
    assert out.startswith("Constraint.integrity_constraints(")
    assert "_VarList_1" not in out
    assert out.count('cons_var(Term.Var("R")') == 2


def test_normalize_printed_item_tuple_with_cost_and_comma_bindings():
    """The tuple form "(bindings, term, cost)" that extract(include_cost=True) prints."""
    from setlah.transpile.normalize import _normalize_printed_item

    text = '(_A_1 = Term.Var("X"), _B_2 = Formula.Lit(GeneralLit.from_literal(Literal(Atom.Pred("p", cons_var(_A_1, nil_var())), True))), Constraint(Vec[LetExpr](), _B_2), 12)'
    out = _normalize_printed_item(text)
    assert out.startswith("Constraint(") and out.endswith(")")
    assert "_A_1" not in out and "_B_2" not in out and ", 12" not in out


def test_b5_transpiler_takes_one_printed_term_per_constraint():
    """The transpiler parses statements one at a time, so a block of 1,000 constraints is
    not one 1,000-deep expression (docs/known-issues.md, B5)."""
    from setlah.transpile.ir import PrintedBlock
    from setlah.transpile.pipeline import transpile_printed_block_to_asp

    rule = (
        'Rule(Atom.Pred("pick", cons_var(Term.Var("X"), nil_var())), '
        'Set[Formula](Formula.Lit(GeneralLit.from_literal(Literal(Atom.Pred("dom_S", cons_var(Term.Var("X"), nil_var())), True)))), True)'
    )
    constraint = (
        'Constraint.integrity_constraints(Set[Term](Term.Var("X")), Set[GeneralLit]('
        'GeneralLit.from_literal(Literal(Atom.Pred("pick", cons_var(Term.Var("X"), nil_var())), True)), '
        'GeneralLit.from_literal(Literal(Atom.Pred("bad%d", cons_var(Term.Var("X"), nil_var())), True))))'
    )
    block = PrintedBlock(rules=[rule], constraints=[constraint % i for i in range(1000)])
    asp = transpile_printed_block_to_asp(block, pred_arg_types={"pick": ("S",), "dom_S": ("S",)})
    lines = asp.splitlines()
    assert sum(1 for l in lines if l.startswith(":- ")) == 1000
    assert ":- pick(X), bad999(X)." in lines


def test_b5_block_of_320_constraints_compiles():
    """320 constraints in one block: past both the parser cap (about 200) and egglog's
    own registration limit on a block-sized cons list (about 300)."""
    source = ["ExtDOM S: INT.", "ExtPred tag: (S).", "", "[", "    pick(X)? :- dom_S(X)."]
    for i in range(320):
        source.append("    (\\forall X. (\\impl (\\and pick(X) tag(X)) (\\neg bad%d(X))))." % i)
        source.append("    bad%d(X)? :- dom_S(X)." % i)
    source.append("]")
    program = Parser().parse("\n".join(source) + "\n")
    with contextlib.redirect_stdout(io.StringIO()):
        rewritten = Rewriter().rewrite_program(program, convert_only=False)
    asp = transpile_program_to_asp(rewritten)
    constraints = [l for l in asp.splitlines() if l.startswith(":- ")]
    assert len(constraints) == 320, len(constraints)
    assert any("bad319" in l for l in constraints)


# ------------------------------------------------- B2: limits-harness shapes

@pytest.mark.parametrize(
    "model",
    [
        "raw_v08_flat_antecedent.sl",
        "raw_v11_flat_antecedent.sl",
        "raw_n07_nested_universals.sl",
        "raw_f1_frame_axiom.sl",
        "raw_f2_forall_exists_forall.sl",
    ],
)
def test_b2_harness_shapes_are_lowered(model):
    """The shapes the limits harness found falling back (docs/known-issues.md, B2):
    a flat antecedent over 8 and 11 variables, nested universals of depth 7."""
    asp = compile_model(model)
    assert "raw-constraint" not in asp, asp
    assert "AuxCall" not in asp, asp


def test_b2_flat_antecedent_is_enforced():
    """The lowered 8-variable constraint means what it says: with p on the end of the
    only 7-step path the program is SAT with pick unconstrained, without it UNSAT."""
    clingo = pytest.importorskip("clingo")
    asp = compile_model("raw_v08_flat_antecedent.sl")
    facts = read_facts("raw_v08.lp")

    def count_models(program):
        ctl = clingo.Control(["0", "--warn=none"])
        ctl.add("base", [], program)
        ctl.ground([("base", [])])
        n = 0
        def on_model(_):
            nonlocal n
            n += 1
        ctl.solve(on_model=on_model)
        return n

    assert count_models(asp + "\n" + facts) == 256
    assert count_models(asp + "\n" + facts.replace("p(6).", "")) == 0


# --------------------------------------------------------------------- B8

@pytest.mark.parametrize("model", ["exists_binders8_ok.sl", "exists_binders9_varlist_crash.sl"])
def test_b8_wide_existential_is_lowered(model):
    """An existential over nine or more bound variables used to reach the transpiler
    with an unevaluated subst_varlist(...) in a variable list (docs/known-issues.md, B8)."""
    asp = compile_model(model)
    assert "subst_" not in asp and "raw-constraint" not in asp and "AuxCall" not in asp, asp
    assert any(l.startswith(":- ") for l in asp.splitlines()), asp


# ------------------------------------------ B2: or-of-and shape (open)

def test_b2_or_of_and_2x2_is_lowered():
    asp = compile_model("or_of_and_2x2_ok.sl")
    assert "raw-constraint" not in asp, asp


@pytest.mark.xfail(strict=True, reason="known-issues B2: a universal over three or more disjuncts of conjunctions of equalities falls back")
def test_b2_or_of_and_3x2_is_lowered():
    asp = compile_model("or_of_and_3x2_fallback.sl")
    assert "raw-constraint" not in asp, asp


# -------------------------------------------------------------------- B10

@pytest.mark.parametrize(
    "model,facts,forbidden",
    [
        ("wrongcode_b10_symmetry_breaking.sl", "wrongcode_b10.lp", "X < Y"),
        ("wrongcode_eq_consequent_lt_min.sl", "wrongcode_eq_consequent_lt.lp", "C < A"),
    ],
)
def test_b10_inequality_kept_in_non_symmetric_constraint(model, facts, forbidden):
    """Symmetry breaking (not X = Y -> X < Y) applies only to constraints that are
    symmetric in X and Y; a singleton witness elsewhere in the block must not turn
    other inequalities into orderings (docs/known-issues.md, B10)."""
    asp = compile_model(model)
    constraints = [l for l in asp.splitlines() if l.startswith(":- ")]
    assert not any(forbidden in l for l in constraints), asp
    assert any("not " in l and " = " in l for l in constraints), asp


def test_b10_program_enforces_the_constraint():
    clingo = pytest.importorskip("clingo")
    asp = compile_model("wrongcode_b10_symmetry_breaking.sl")
    ctl = clingo.Control(["0", "--warn=none"])
    ctl.add("base", [], asp + "\n" + read_facts("wrongcode_b10.lp"))
    ctl.ground([("base", [])])
    models = []
    ctl.solve(on_model=lambda m: models.append({str(s) for s in m.symbols(atoms=True)}))
    assert models and all("r(2,1)" in m for m in models), len(models)
