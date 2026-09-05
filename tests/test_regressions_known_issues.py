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
