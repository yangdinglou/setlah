'''
The rewrite rules are defined for transforming SetLaH programs among equivalent forms, on two levels:
1. Set Constraint level: 
    - Propositional and First-Order Logic simplifications
    - Aggregate synthesis (e.g., transforming existential quantifiers into aggregate constraints)
    - Normalization to a target logical form 
    - TODO: lemma 6?
2. Block level:
    - Formula decomposition
    - Bi-implication <-> horn clauses
    - aggregate head
'''

from egglog import *
from .egg_schema import *

term_set=ruleset()
equal_set=ruleset()
grounding=ruleset()

cost_conversion = ruleset()

aux_set = ruleset()  # Auxiliary predicate introduction for nested formulas

split_set = ruleset()  # MARK: AND-split — minimal ruleset for conjunction splitting pre-pass

extraction=ruleset()

var_in_list = relation("var_in_list", Term, VarList)
# var_in_list_once = relation("var_in_list_once", Term, VarList, MultiSet[Term])

@function
def var_in_list_once(vs: VarList) -> MultiSet[Term]: ...

# Collects all variables from all terms in a VarList (recursively via contains_once)
@function
def vars_in_list_deep(vs: VarList) -> MultiSet[Term]: ...

@term_set.register
def var_in_list_rule(v: Term, v_:Term, vs1: VarList, vs2: VarList, vs: MultiSet[Term], vs_head: MultiSet[Term], vs_tail: MultiSet[Term]):
    yield rule(vs1==cons_var(v, vs2)).then(var_in_list(v, vs1))
    yield rule(var_in_list(v, vs2), vs1==cons_var(v_, vs2)).then(var_in_list(v, vs1))
    # yield rule(vs1==cons_var(v, nil_var())).then(var_in_list_once(v, vs1, MultiSet[Term]().insert(v)))
    yield rule(vs1==cons_var(v, nil_var())).then(set_(var_in_list_once(vs1)).to(MultiSet[Term]().insert(v)))
    # yield rule(var_in_list_once(v, vs2, vs), vs1==cons_var(v_, vs2), v_==v).then(var_in_list_once(v, vs1, vs.insert(v)))
    # yield rule(var_in_list_once(v, vs2, vs), vs1==cons_var(v_, vs2), v_!=v).then(var_in_list_once(v, vs1, vs))
    # 
    # yield rule(var_in_list_once(v, vs2, vs), vs1==cons_var(v_, vs2)).then(var_in_list_once(v, vs1, vs.insert(v_)))
    yield rule(vs==var_in_list_once(vs2), vs1==cons_var(v_, vs2)).then(set_(var_in_list_once(vs1)).to(vs.insert(v_)))
    
    # vars_in_list_deep: recursively collect all variables from all terms
    yield rule(vs1 == nil_var()).then(set_(vars_in_list_deep(vs1)).to(MultiSet[Term]()))
    yield rule(vs1 == cons_var(v, vs2), v.contains_once(vs_head), vs_tail == vars_in_list_deep(vs2)).then(
        set_(vars_in_list_deep(vs1)).to(vs_head.__add__(vs_tail))
    )



@function(merge=lambda a, b: a.__or__(b))
def var_set(f: Formula) -> VarSet: ...


@term_set.register
def term_contains_var(
    v: Term,
    t: Term,
    tl: Term,
    tr: Term,
    name: StringLike,
    op: StringLike,
    val: i64,
    sym: StringLike,
    vs1: MultiSet[Term],
    vs2: MultiSet[Term],
):
    yield rule(v == Term.Var(name), t == Term.Var(name)).then(t.contains_var(v))
    yield rule(t == Term.BinaryExpr(op, tl, tr), tl.contains_var(v)).then(t.contains_var(v))
    yield rule(t == Term.BinaryExpr(op, tl, tr), tr.contains_var(v)).then(t.contains_var(v))
    # contains_once for terms: derive a MultiSet of all variable occurrences
    yield rule(t == Term.Var(name), vs1 == MultiSet[Term]().insert(t)).then(t.contains_once(vs1))
    # Base cases: non-variable terms have empty variable sets
    yield rule(t == Term.Int(val), vs1 == MultiSet[Term]()).then(t.contains_once(vs1))
    yield rule(t == Term.Symbol(sym), vs1 == MultiSet[Term]()).then(t.contains_once(vs1))
    yield rule(t == Term.Anon(), vs1 == MultiSet[Term]()).then(t.contains_once(vs1))
    # yield rule(t == Term.Symbol(sym), vs1 == MultiSet[Term]()).then(t.contains_once(vs1))
    # yield rule(t == Term.Anon(), vs1 == MultiSet[Term]()).then(t.contains_once(vs1))
    yield rule(t == Term.BinaryExpr(op, tl, tr), tl.contains_once(vs1), tr.contains_once(vs2)).then(
        t.contains_once(vs1.__add__(vs2))
    )

@term_set.register
def formula_contains_var(v: Term, name:StringLike, name2:StringLike, f: Formula,a:Formula,b:Formula, args: VarList, formula_l: Formula, formula_r:Formula,qalter: Term, b_var:BoolLike,ta:Term,tb:Term, vs1:MultiSet[Term], vs2:MultiSet[Term], t:Term):
    # For Pred atoms: check both direct membership and containment within terms
    yield rule(v==Term.Var(name), f == Formula.Lit(Literal(Atom.Pred(name2, args),b_var)), var_in_list(v, args)).then(f.contains_var(v))
    # Also check if v is contained within any term in args (e.g., BinaryExpr like (+ H 1))
    yield rule(v==Term.Var(name), f == Formula.Lit(Literal(Atom.Pred(name2, args),b_var)), var_in_list(t, args), t.contains_var(v)).then(f.contains_var(v))
    yield rule(v==Term.Var(name), f == Formula.Lit(Literal(Atom.Comp(name2, ta, tb),b_var)), ta.contains_var(v)).then(f.contains_var(v))
    yield rule(v==Term.Var(name), f == Formula.Lit(Literal(Atom.Comp(name2, ta, tb),b_var)), tb.contains_var(v)).then(f.contains_var(v))
    yield rule(v==Term.Var(name), f == Formula.And(formula_l,formula_r), formula_l.contains_var(v)).then(f.contains_var(v))
    yield rule(v==Term.Var(name), f == Formula.Or(formula_l,formula_r), formula_l.contains_var(v)).then(f.contains_var(v))
    yield rule(v==Term.Var(name), f == Formula.And(formula_l,formula_r), formula_r.contains_var(v)).then(f.contains_var(v))
    yield rule(v==Term.Var(name), f == Formula.Or(formula_l,formula_r), formula_r.contains_var(v)).then(f.contains_var(v))
    yield rule(v==Term.Var(name), f == Formula.Not(a), a.contains_var(v)).then(f.contains_var(v))
    yield rule(v==Term.Var(name), f == Formula.Implies(a, b), a.contains_var(v)).then(f.contains_var(v))
    yield rule(v==Term.Var(name), f == Formula.Implies(a, b), b.contains_var(v)).then(f.contains_var(v))
    yield rule(v==Term.Var(name), f == Formula.Forall(qalter, b), b.contains_var(v)).then(f.contains_var(v))
    yield rule(v==Term.Var(name), f == Formula.Exists(qalter, b), b.contains_var(v)).then(f.contains_var(v)) #TODO: check if v != qalter?
    yield rule(f.contains_var(v)).then(set_(var_set(f)).to(VarSet.empty().insert(v)))
    
    # contains_once: derive a MultiSet of all variable occurrences (independent of which var)
    # TODO: Handle GeneralLit.general_agg (aggregates) - currently only Literal form is covered
    yield rule(f == Formula.Bool(b_var), vs1 == MultiSet[Term]()).then(f.contains_once(vs1))
    # Use vars_in_list_deep to recursively collect variables from BinaryExpr etc.
    yield rule(f == Formula.Lit(Literal(Atom.Pred(name2, args), b_var)), vs1 == vars_in_list_deep(args)).then(
        f.contains_once(vs1)
    )
    yield rule(f == Formula.Lit(Literal(Atom.Comp(name2, ta, tb), b_var)), ta.contains_once(vs1), tb.contains_once(vs2)).then(
        f.contains_once(vs1.__add__(vs2))
    )
    yield rule(f == Formula.And(formula_l, formula_r), formula_l.contains_once(vs1), formula_r.contains_once(vs2)).then(
        f.contains_once(vs1.__add__(vs2))
    )
    yield rule(f == Formula.Or(formula_l, formula_r), formula_l.contains_once(vs1), formula_r.contains_once(vs2)).then(
        f.contains_once(vs1.__add__(vs2))
    )
    yield rule(f == Formula.Not(a), a.contains_once(vs1)).then(f.contains_once(vs1))
    yield rule(f == Formula.Implies(a, b), a.contains_once(vs1), b.contains_once(vs2)).then(
        f.contains_once(vs1.__add__(vs2))
    )
    yield rule(f == Formula.Forall(qalter, b), b.contains_once(vs1)).then(f.contains_once(vs1))
    yield rule(f == Formula.Exists(qalter, b), b.contains_once(vs1)).then(f.contains_once(vs1))
    # TODO: Handle grouped quantifiers (grouped_forall, grouped_exists)
    # TODO: Handle grouped_and, grouped_and_lit, grouped_dnf forms





@term_set.register
def constraint_list_as_set(head1: Constraint, head2: Constraint, tail: ConsList):
    # Idempotency and commutativity of ConsList as Set
    yield rewrite(cons_constraint(head1, cons_constraint(head1, tail))).to(
        cons_constraint(head1, tail)
    )
    yield rewrite(cons_constraint(head1, cons_constraint(head2, tail))).to(
        cons_constraint(head2, cons_constraint(head1, tail))
    )

@equal_set.register
def neg_literal(a:Atom):
    # Negation of Literal
    yield birewrite(Formula.Not(Formula.Lit(Literal(a,True)))).to(Formula.Lit(Literal(a,False)))
    yield birewrite(Formula.Not(Formula.Lit(Literal(a,False)))).to(Formula.Lit(Literal(a,True)))
    yield rewrite(Formula.Not(Formula.Lit(GeneralLit.from_literal(Literal(a,True))))).to(Formula.Lit(Literal(a,False)))
    yield rewrite(Formula.Not(Formula.Lit(GeneralLit.from_literal(Literal(a,False))))).to(Formula.Lit(Literal(a,True)))



# https://math.stackexchange.com/questions/3418148/is-there-a-complete-set-of-equivalence-principles-for-first-order-logic
@equal_set.register
def propositional_rules(a: Formula, b: Formula, c: Formula):
    # Double Negation
    yield rewrite(Formula.Not(Formula.Not(a))).to(a)
    # Commutativity
    yield birewrite(Formula.And(a, b)).to(Formula.And(b, a))
    yield birewrite(Formula.Or(a, b)).to(Formula.Or(b, a))
    # Associativity
    yield birewrite(Formula.And(Formula.And(a, b), c)).to(Formula.And(a, Formula.And(b, c)))
    yield birewrite(Formula.Or(Formula.Or(a, b), c)).to(Formula.Or(a, Formula.Or(b, c)))
    # De Morgan's Laws
    yield birewrite(Formula.Not(Formula.And(a, b))).to(Formula.Or(Formula.Not(a), Formula.Not(b)))
    yield birewrite(Formula.Not(Formula.Or(a, b))).to(Formula.And(Formula.Not(a), Formula.Not(b)))
    # Implication
    yield rewrite(Formula.Implies(a, b)).to(Formula.Or(Formula.Not(a),b))
    # Distributivity
    yield birewrite(Formula.And(a, Formula.Or(b, c))).to(Formula.Or(Formula.And(a, b), Formula.And(a, c)))
    yield birewrite(Formula.Or(a, Formula.And(b, c))).to(Formula.And(Formula.Or(a, b), Formula.Or(a, c)))
    # Idempotency
    yield rewrite(Formula.And(a, a)).to(a)
    yield rewrite(Formula.Or(a, a)).to(a)
    # Identity
    yield rewrite(Formula.And(a, Formula.Bool(True))).to(a)
    yield rewrite(Formula.Or(a, Formula.Bool(False))).to(a)
    # For optimisation
    yield rewrite(Formula.Implies(a, Formula.And(b, c))).to(Formula.And(Formula.Implies(a, b), Formula.Implies(a, c)))




# TODO: subsume

@equal_set.register
def lec10_fo_A(f: Formula,x: Term):
    yield birewrite(Formula.Not(Formula.Forall(x, f))).to(Formula.Exists(x, Formula.Not(f)))
    yield birewrite(Formula.Not(Formula.Exists(x, f))).to(Formula.Forall(x, Formula.Not(f)))
    # yield birewrite(Formula.Forall(x,f)).to(Formula.Not(Formula.Exists(x, Formula.Not(f))))
    # yield birewrite(Formula.Exists(x,f)).to(Formula.Not(Formula.Forall(x, Formula.Not(f))))

@equal_set.register
def lec10_fo_B(f: Formula, g: Formula, x: Term, y: Term, vs: VarSet, phi: Formula):
    yield rule(var_set(g)==vs, vs.not_contains(x), phi==Formula.Forall(x, Formula.And(f,g))).then(
        union(phi).with_(Formula.And(Formula.Forall(x, f),g))
    )
    yield rule(var_set(g)==vs, vs.not_contains(x), phi==Formula.Forall(x, Formula.Or(f,g))).then(
        union(phi).with_(Formula.Or(Formula.Forall(x, f),g))
    )
    yield rule(var_set(g)==vs, vs.not_contains(x), phi==Formula.Exists(x, Formula.And(f,g))).then(
        union(phi).with_(Formula.And(Formula.Exists(x, f),g))
    )
    yield rule(var_set(g)==vs, vs.not_contains(x), phi==Formula.Exists(x, Formula.Or(f,g))).then(
        union(phi).with_(Formula.Or(Formula.Exists(x, f),g))
    )


@equal_set.register
def lec10_fo_C(f: Formula, g: Formula, x: Term):
    yield rewrite(Formula.Forall(x, Formula.And(f, g))).to(Formula.And(Formula.Forall(x, f), Formula.Forall(x, g)))
    yield rewrite(Formula.Or(Formula.Exists(x, f), Formula.Exists(x, g))).to(Formula.Exists(x, Formula.Or(f, g)))

@equal_set.register
def lec10_fo_D(f: Formula, x: Term, y: Term):
    yield rewrite(Formula.Forall(x, Formula.Forall(y, f))).to(Formula.Forall(y, Formula.Forall(x, f)))
    yield rewrite(Formula.Exists(x, Formula.Exists(y, f))).to(Formula.Exists(y, Formula.Exists(x, f)))

@equal_set.register
def exists_to_anonymous(phi: Formula, x: Term, body: Formula, vs: MultiSet[Term]):
    # Rewrite ∃X. body to subst(body, X, _) when X appears exactly once in body.
    # This drops the quantifier and replaces the single occurrence with Term.Anon().
    # TODO: The contains_once relation tracks all occurrences in a MultiSet.
    # We need to ensure vs has exactly one element (i.e., the variable appears once).
    # For now, we rely on contains_once being derived correctly, and check vs == MultiSet[Term]().insert(x)
    yield rule(
        phi == Formula.Exists(x, body),
        body.contains_once(vs),
        vs.remove(x).not_contains(x)
    ).then(
        union(phi).with_(subst_formula(body, x, Term.Anon()))
    )


# --- Substitution functions for trivial existential elimination ---
# Recursively replace all occurrences of `old` term with `new` term.
# Used to substitute a variable with Term.Anon() when dropping quantifiers.

@function(cost=10000)
def subst_varlist(args: VarList, old: Term, new: Term) -> VarList: ...

@function(cost=10000)
def subst_term(t: Term, old: Term, new: Term) -> Term: ...

@function(cost=10000)
def subst_formula(f: Formula, old: Term, new: Term) -> Formula: ...


@equal_set.register
def subst_varlist_rules(args: VarList, old: Term, new: Term, head: Term, tail: VarList, result: VarList):
    yield rewrite(subst_varlist(nil_var(), old, new)).to(nil_var())
    yield rewrite(subst_varlist(cons_var(old, tail), old, new)).to(
        cons_var(new, subst_varlist(tail, old, new))
    )
    yield rule(head != old, result == subst_varlist(cons_var(head, tail), old, new)).then(
        union(result).with_(cons_var(head, subst_varlist(tail, old, new)))
    )


@equal_set.register
def subst_term_rules(t: Term, old: Term, new: Term, name: StringLike, val: i64, op: StringLike, l: Term, r: Term, t2: Term):
    # Base cases
    yield rewrite(subst_term(old, old, new)).to(new)
    yield rule(t != old, t == Term.Var(name), t2 == subst_term(t, old, new)).then(
        union(t2).with_(t)
    )
    yield rule(t != old, t == Term.Int(val), t2 == subst_term(t, old, new)).then(
        union(t2).with_(t)
    )
    yield rule(t != old, t == Term.Symbol(name), t2 == subst_term(t, old, new)).then(
        union(t2).with_(t)
    )
    yield rule(t != old, t == Term.Anon(), t2 == subst_term(t, old, new)).then(
        union(t2).with_(t)
    )
    
    # Recursive case: BinaryExpr
    yield rewrite(subst_term(Term.BinaryExpr(op, l, r), old, new)).to(
        Term.BinaryExpr(op, subst_term(l, old, new), subst_term(r, old, new))
    )


@equal_set.register
def subst_formula_rules(
    f: Formula,
    old: Term,
    new: Term,
    lit: GeneralLit,
    atom: Atom,
    pred_name: StringLike,
    args: VarList,
    comp_op: StringLike,
    ta: Term,
    tb: Term,
    sign: BoolLike,
    a: Formula,
    b: Formula,
    qvar: Term,
):
    # Literal: substitute in the atom's arguments or comparison terms
    # TODO: Handle GeneralLit.general_agg (aggregates) - for now we only handle from_literal
    yield rewrite(
        subst_formula(Formula.Lit(GeneralLit.from_literal(Literal(Atom.Pred(pred_name, args), sign))), old, new)
    ).to(
        Formula.Lit(GeneralLit.from_literal(Literal(Atom.Pred(pred_name, subst_varlist(args, old, new)), sign)))
    )
    yield rewrite(
        subst_formula(Formula.Lit(GeneralLit.from_literal(Literal(Atom.Comp(comp_op, ta, tb), sign))), old, new)
    ).to(
        Formula.Lit(GeneralLit.from_literal(Literal(Atom.Comp(comp_op, subst_term(ta, old, new), subst_term(tb, old, new)), sign)))
    )
    
    # Connectives: recurse through subformulas
    yield rewrite(subst_formula(Formula.And(a, b), old, new)).to(
        Formula.And(subst_formula(a, old, new), subst_formula(b, old, new))
    )
    yield rewrite(subst_formula(Formula.Or(a, b), old, new)).to(
        Formula.Or(subst_formula(a, old, new), subst_formula(b, old, new))
    )
    yield rewrite(subst_formula(Formula.Not(a), old, new)).to(
        Formula.Not(subst_formula(a, old, new))
    )
    yield rewrite(subst_formula(Formula.Implies(a, b), old, new)).to(
        Formula.Implies(subst_formula(a, old, new), subst_formula(b, old, new))
    )
    
    # Quantifiers: recurse into body
    # TODO: Should we check qvar != old to avoid substituting under a shadowing binder?
    # For now, we assume contains_once already filtered out shadowed cases.
    yield rewrite(subst_formula(Formula.Forall(qvar, a), old, new)).to(
        Formula.Forall(qvar, subst_formula(a, old, new))
    )
    yield rewrite(subst_formula(Formula.Exists(qvar, a), old, new)).to(
        Formula.Exists(qvar, subst_formula(a, old, new))
    )
    
    # TODO: Handle grouped quantifiers (grouped_forall, grouped_exists)
    # TODO: Handle grouped_and, grouped_and_lit, grouped_dnf - these may contain aggregates
    # TODO: For aggregates inside GeneralLit.general_agg, we need to substitute in AggBody



@cost_conversion.register
def cost_conversion_rules(a: Set[Term], b: Vec[Formula], ab: AggBody):
    yield rewrite(AggBody.set_comprehension(a, b),subsume=True).to(AggBody.set_comp_costly(a, b))



@extraction.register
def grouping_quantifiers(vars: Set[Term], body: Formula, var: Term, vars1: Set[Term]):
    yield rewrite(Formula.Forall(var, body)).to(Formula.grouped_forall(Set[Term](var), body))
    yield rewrite(Formula.Exists(var, body)).to(Formula.grouped_exists(Set[Term](var), body))
    yield rewrite(Formula.grouped_forall(vars, Formula.Forall(var, body))).to(Formula.grouped_forall(vars.insert(var), body))
    yield rewrite(Formula.grouped_exists(vars, Formula.Exists(var, body))).to(Formula.grouped_exists(vars.insert(var), body))
    yield rewrite(Formula.grouped_forall(vars, Formula.grouped_forall(vars1, body))).to(Formula.grouped_forall(vars.__or__(vars1), body))
    yield rewrite(Formula.grouped_exists(vars, Formula.grouped_exists(vars1, body))).to(Formula.grouped_exists(vars.__or__(vars1), body))
    # # Helper function for non-quantified formula
    # yield rewrite(body).to(Formula.grouped_forall(Set[Term](), body))
    # yield rewrite(body).to(Formula.grouped_exists(Set[Term](), body))


@extraction.register
def grouped_forall_consumer(vars: Set[Term], f: Formula):
    # The consumer of grouped_forall: a universally quantified negation is a
    # negated existential, and every lowering below (integrity constraint,
    # auxiliary predicate, count aggregate) starts from grouped_exists.
    #     forall vs. not f   ==   not exists vs. f
    # equal_set has the same law one quantifier at a time
    # (lec10_fo_A), but under its iteration budget and back-off scheduler a
    # chain of n levels is not always flipped; the grouping in this ruleset
    # does complete, so the grouped form is the reliable entry point
    # (docs/known-issues.md, B2).
    yield rewrite(Formula.grouped_forall(vars, Formula.Not(f))).to(
        Formula.Not(Formula.grouped_exists(vars, f))
    )

@extraction.register
def grouping_and(formulas: Set[GeneralLit], f: GeneralLit,g: GeneralLit):
    yield rewrite(Formula.And(Formula.Lit(f), Formula.Lit(g))).to(Formula.grouped_and(Set[GeneralLit](f, g)))
    yield rewrite(Formula.And(Formula.Lit(f), Formula.grouped_and(formulas))).to(Formula.grouped_and(formulas.insert(f)))
    yield rewrite(Formula.Lit(f)).to(Formula.grouped_and(Set[GeneralLit](f)))


@extraction.register
def grouping_and_lit(formulas: Set[Literal], l1: Literal, l2: Literal):
    # Literal-only conjunction grouping for aggregate cubes.
    # This ensures aggregate element conditions cannot contain aggregates.
    yield rewrite(Formula.And(Formula.Lit(GeneralLit.from_literal(l1)), Formula.Lit(GeneralLit.from_literal(l2)))).to(
        Formula.grouped_and_lit(Set[Literal](l1, l2))
    )
    yield rewrite(Formula.And(Formula.Lit(GeneralLit.from_literal(l1)), Formula.grouped_and_lit(formulas))).to(
        Formula.grouped_and_lit(formulas.insert(l1))
    )
    yield rewrite(Formula.Lit(GeneralLit.from_literal(l1))).to(Formula.grouped_and_lit(Set[Literal](l1)))


@extraction.register
def grouping_dnf(cube1: Set[Literal], cube2: Set[Literal], cubes: Vec[Formula]):
    # IMPORTANT: DNF cubes are used as aggregate element conditions.
    # Restrict them to literal-only conjunctions so aggregates never nest.
    yield rewrite(Formula.Or(Formula.grouped_and_lit(cube1), Formula.grouped_and_lit(cube2))).to(
        Formula.grouped_dnf(Vec[Formula](Formula.grouped_and_lit(cube1), Formula.grouped_and_lit(cube2)))
    )
    yield rewrite(Formula.grouped_and_lit(cube1)).to(
        Formula.grouped_dnf(Vec[Formula](Formula.grouped_and_lit(cube1)))
    )
    yield rewrite(Formula.Or(Formula.grouped_dnf(cubes), Formula.grouped_and_lit(cube1))).to(
        Formula.grouped_dnf(cubes.push(Formula.grouped_and_lit(cube1)))
    )

@extraction.register
def quant_to_count(vs: Set[Term], cubes: Vec[Formula], a: Formula,ab:AggBody, t:Term):
    yield rewrite(Formula.grouped_exists(vs, Formula.grouped_dnf(cubes))).to(Formula.Lit(GeneralLit.general_agg(
        "count",
        AggBody.set_comprehension(vs, cubes),
        "!=",
        Term.Int(0)
    )))
    yield birewrite(Formula.Not(Formula.Lit(GeneralLit.general_agg(
        "count",
        ab,
        "!=",
        t
    )))).to(Formula.Lit(GeneralLit.general_agg(
        "count",
        ab,
        "==",
        t
    )))

# =============================================================================
# AGGREGATE CONSTRAINT CONVERSION
# =============================================================================
# Convert Formula.Agg (from source syntax like `#count {Set_X}(Y) >= k`)
# to an integrity constraint with GeneralLit.general_agg.
#
# The SetExpr.SetVar contains the set name (e.g., "Set_in_clique") and 
# the counting variables (e.g., cons_var(Term.Var("X"), nil_var())).
#
# This becomes:
#   Constraint with GeneralLit.general_agg("count", 
#       AggBody.set_comprehension({X}, [pred_lit(X)]),
#       comp_op, val)
#
# Note: We handle this in the transpiler rather than egg rules because
# we need to construct the predicate name from the set name, which
# requires string manipulation not easily done in egglog.


# MARK: AND-split — conjunction_split rule (split_set)
@split_set.register
def conjunction_split(s_rest: ConsList, a: Formula, b: Formula):
    # Split a conjunction in a constraint into two separate constraints.
    # Lives in split_set (a minimal ruleset for the splitting pre-pass)
    # together with just enough rules to surface top-level And.
    # A custom cost model (split_cost_model in rw.py) penalises top-level
    # Formula.And inside a Constraint, making the extractor prefer the
    # split form deterministically.
    yield rewrite(
        cons_constraint(Constraint(Vec[LetExpr](), Formula.And(a, b)), s_rest)
    ).to(
        cons_constraint(Constraint(Vec[LetExpr](), a), cons_constraint(Constraint(Vec[LetExpr](), b), s_rest))
    )

# MARK: AND-split — helper rules to expose top-level And
@split_set.register
def split_expose_and(a: Formula, b: Formula, c: Formula, x: Term):
    # Minimal rules to expose top-level And inside constraints:
    # 1. ∀x.(A∧B) → (∀x.A) ∧ (∀x.B)
    # NOTE: Do NOT include here — it interferes with inner And nodes during
    # extraction with the split cost model. Instead, rely on equal_set's
    # lec10_fo_C + extraction's conjunction_split_extraction for this case.
    # yield rewrite(Formula.Forall(x, Formula.And(a, b))).to(Formula.And(Formula.Forall(x, a), Formula.Forall(x, b)))
    # 2. And associativity (to flatten nested And before splitting)
    yield rewrite(Formula.And(Formula.And(a, b), c)).to(Formula.And(a, Formula.And(b, c)))

# MARK: AND-split — fallback split during extraction phase
@extraction.register
def conjunction_split_extraction(s_rest: ConsList, a: Formula, b: Formula):
    # Duplicate of conjunction_split for the extraction phase.
    # Needed because some conjunctions only appear after extraction rules
    # (e.g., after ∀-grouping, ∃→count conversion, etc.).
    yield rewrite(
        cons_constraint(Constraint(Vec[LetExpr](), Formula.And(a, b)), s_rest)
    ).to(
        cons_constraint(Constraint(Vec[LetExpr](), a), cons_constraint(Constraint(Vec[LetExpr](), b), s_rest))
    )

@extraction.register
def extract_constraint(vs: Set[Term], fs: Set[GeneralLit]):
    yield rewrite(Constraint(Vec[LetExpr](), Formula.Not(Formula.grouped_exists(vs, Formula.grouped_and(fs))))).to(
        Constraint.integrity_constraints(vs, fs)
    )
    yield rewrite(Constraint(Vec[LetExpr](), Formula.Not(Formula.grouped_and(fs)))).to(
        Constraint.integrity_constraints(Set[Term](), fs)
    )


# =============================================================================
# AUXILIARY PREDICATE INTRODUCTION
# =============================================================================
# Convert grouped_exists(vars, grouped_and_lit(lits)) to an aux predicate call,
# where the aux predicate has arguments =  (the free vars).
# This is used to flatten nested existentials that would otherwise create nested aggregates.
#



@aux_set.register
def aux_rewrite_nested_exists(
    qvars: Set[Term],
    cubes: Vec[Formula],
    inner_formula: Formula,
    body_formula: Formula,
):
    # Rewrite grouped_exists(qvars, grouped_dnf(cubes)) to Literal.AuxCall wrapped in Formula.Lit.
    # After the extraction phase runs grouping_dnf, every grouped_and_lit body is promoted to
    # grouped_dnf([grouped_and_lit(lits)]), so matching grouped_dnf covers all cases.
    # The transpiler will:
    #   1. Compute free_vars = (all vars in cubes) - qvars
    #   2. Generate a fresh aux predicate name
    #   3. Emit one aux rule per cube: aux_N(free_vars) :- lits_in_cube
    #   4. Output the aux predicate call: aux_N(free_vars)
    # Note: free_vars is NOT stored in AuxCall; the transpiler computes it from the cubes.
    yield rule(
        inner_formula == Formula.grouped_exists(qvars, body_formula),
        body_formula == Formula.grouped_dnf(cubes),
    ).then(
        union(inner_formula).with_(Formula.Lit(GeneralLit.from_literal(Literal.AuxCall(cubes, qvars)))),
    )


# # Combine all phases
# all_rules = fol_rules + agg_synthesis_rules + normalization_rules + set_splitting_rules