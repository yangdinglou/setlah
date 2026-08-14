from __future__ import annotations
from egglog import *
from collections.abc import Callable


# ==========================================
# 1. Base Terms (Variables, Ints)
# ==========================================

class Term(Expr):
    @classmethod
    def Var(cls, name: StringLike) -> Term: ...
    @classmethod
    def Int(cls, val: i64) -> Term: ...
    @classmethod
    def Symbol(cls, name: StringLike) -> Term: ...
    @method(cost=0)
    @classmethod
    def Anon(cls) -> Term: ... # Anonymous variable (TODO: as extension or core?)
    
    # Arithmetic
    @classmethod
    def BinaryExpr(cls, op: StringLike, left: Term, right: Term) -> Term: ...

    def __add__(self, other: Term) -> Term: return Term.BinaryExpr("+", self, other)
    def __sub__(self, other: Term) -> Term: return Term.BinaryExpr("-", self, other)
    def __mul__(self, other: Term) -> Term: return Term.BinaryExpr("*", self, other)
    def __truediv__(self, other: Term) -> Term: return Term.BinaryExpr("/", self, other)

    def contains_var(self, v: Term) -> Unit: ...

    def contains_once(self, vs: MultiSet[Term]) -> Unit: ...

# ==========================================
# 2. Set Expressions (Algebra)
# ==========================================

VarSet = Set[Term]
class VarList(Expr):
    pass
@function
def nil_var() -> VarList: ...
@function
def cons_var(head: Term, tail: VarList) -> VarList: ...

converter(tuple, VarList, lambda t: nil_var() if not t else cons_var(t[0], t[1:]))
converter(list, VarList, lambda t: nil_var() if not t else cons_var(t[0], t[1:]))



class SetExpr(Expr):
    @classmethod
    def SetVar(cls, name: StringLike, tuple: VarList) -> SetExpr: ...
    @classmethod
    def Empty(cls) -> SetExpr: ...
    
    @classmethod
    def Union(cls, l: SetExpr, r: SetExpr) -> SetExpr: ...
    @classmethod
    def Inter(cls, l: SetExpr, r: SetExpr) -> SetExpr: ...
    @classmethod
    def Diff(cls, l: SetExpr, r: SetExpr) -> SetExpr: ...
    @classmethod
    def SymDiff(cls, l: SetExpr, r: SetExpr) -> SetExpr: ...

    @classmethod
    def Set_Comprehension(cls, tuple: VarList, dom_vars: Vec[StringLike], dom_set: SetExpr, condition: Formula) -> SetExpr: ...

# ==========================================
# 3. Atom (pred + comparison)
# ==========================================

class Atom(Expr):
    @classmethod
    def Pred(cls, name: StringLike, args: VarList) -> Atom: ...
    @classmethod
    def Comp(cls, op: StringLike, l: Term, r: Term) -> Atom: ...


class Literal(Expr):
    """
    Represents a signed Atom. 
    sign=True  =>  Atom
    sign=False => -Atom (negation)
    """
    def __init__(self, atom: Atom, sign: BoolLike) -> None: ...
    
    # Auxiliary predicate call - introduced during aux predicate flattening
    # Stores the DNF body cubes and quantified vars so transpiler can emit the aux rule(s).
    # free_vars = (all vars in body_cubes) - qvars; computed by the transpiler from the cubes.
    # Each cube in body_cubes is a grouped_and_lit(Set[Literal]); one ASP rule is emitted per cube.
    @method(cost=5)  # Prefer this over nested grouped_exists
    @classmethod
    def AuxCall(cls, body_cubes: Vec[Formula], qvars: Set[Term]) -> Literal: ...

class AggElement(Expr):
    """
    Represents a single element in an aggregate: t : L
    Example: X : p(X), q(X)
    """
    def __init__(self, terms: Vec[Term], condition: Set[Literal]) -> None: ...


class AggBody(Expr):
    """
    Represents the full body: { E1; E2; ... }
    """
    def __init__(self, elements: Vec[AggElement]) -> None: ...

    @method(cost=15000)
    @classmethod
    def set_comprehension(cls, vars: Set[Term], cubes: Vec[Formula]) -> AggBody: ...

    @method(cost=100)  # Higher cost version to prefer aux predicates over aggregates
    @classmethod
    def set_comp_costly(cls, vars: Set[Term], cubes: Vec[Formula]) -> AggBody: ...

# ==========================================
# 4. Formulas (Logic + Set Logic)
# ==========================================


# class FormulaList(Expr):
#     pass
# TODO: https://github.com/egraphs-good/egglog/issues/386 generic set?

class GeneralLit(Expr):
    @method(cost=0)
    @classmethod
    def from_literal(cls, lit: Literal) -> GeneralLit: ...
    @method(cost=500)  # High cost to prefer AuxCall over nested aggregates
    @classmethod
    def general_agg(cls, op: StringLike, body: AggBody, comp: StringLike, val: Term) -> GeneralLit: ...

converter(Literal, GeneralLit, lambda l: GeneralLit.from_literal(l))

class Formula(Expr):
    @classmethod
    def Bool(cls, val: BoolLike) -> Formula: ...
    
    # Uses built-in Vec[Term]
    @classmethod
    def Lit(cls, lit: GeneralLit) -> Formula: ...

    # Logic
    # Using binary for And/Or for simplicity
    @classmethod
    def And(cls, l: Formula, r: Formula) -> Formula: ...
    @classmethod
    def Or(cls, l: Formula, r: Formula) -> Formula: ...
    @classmethod
    def Not(cls, f: Formula) -> Formula: ...
    @method(cost=250)
    @classmethod
    def Implies(cls, l: Formula, r: Formula) -> Formula: ...
    
    # Quantifiers
    @method(cost=50)
    @classmethod
    def Forall(cls, var: Term, body: Formula) -> Formula: ...
    @method(cost=50)
    @classmethod
    def Exists(cls, var: Term, body: Formula) -> Formula: ...

    #Grouped Quantifiers
    @method(cost=200)
    @classmethod
    def grouped_forall(cls, vars: Set[Term], body: Formula) -> Formula: ...
    @method(cost=200)
    @classmethod
    def grouped_exists(cls, vars: Set[Term], body: Formula) -> Formula: ...
    @method(cost=200)
    @classmethod
    def grouped_and(cls, formulas: Set[GeneralLit]) -> Formula: ...

    # A conjunction of *non-aggregate* literals only (used for DNF cubes that
    # will become aggregate element conditions). This prevents nested aggregates
    # inside `AggBody.set_comprehension`.
    @method(cost=10)
    @classmethod
    def grouped_and_lit(cls, formulas: Set[Literal]) -> Formula: ...

    @method(cost=10)
    @classmethod
    def grouped_dnf(cls, formulas: Vec[Formula]) -> Formula: ...
    

    # Set Logic
    @classmethod
    def Belonging(cls, elem: Term, set_name: SetExpr) -> Formula: ...
    @classmethod
    def Subset(cls, l: Term, r: SetExpr) -> Formula: ...
    
    # Aggregates
    # #op{var} op Val
    @classmethod
    def Agg(cls, op: StringLike, var: SetExpr, comp_op: StringLike, val: Term) -> Formula: ...

    @classmethod
    def GeneralAgg(cls, op: StringLike, body: AggBody, comp: StringLike, val: Term) -> Formula: ...
    
    # partition(TargetSet, [Parts...]) - Using Vec[Term]
    @classmethod
    def Partition(cls, target: Term, parts: Vec[Term]) -> Formula: ...
    
    # # Operator Overloading
    # def __and__(self, other: Formula) -> Formula: return Formula.And(self, other)
    # def __or__(self, other: Formula) -> Formula: return Formula.Or(self, other)
    # def __invert__(self) -> Formula: return Formula.Not(self)

    def contains_var(self, v: Term) -> Unit: ...
    def contains_once(self, vs: MultiSet[Term]) -> Unit: ...


converter(Atom, Literal, lambda a: Literal(a, True))
converter(Literal, Formula, lambda l: Formula.Lit(l))
converter(Atom, Formula, lambda a: Formula.Lit(Literal(a, True)))




# ==========================================
# 5. Program Structure (Block & Constraints)
# ==========================================


class LetExpr(Expr):
    def __init__(cls, var:SetExpr, val: SetExpr) -> "LetExpr": ...


class Rule(Expr):
    def __init__(cls, head: Atom, body: Set[Formula], is_choice: BoolLike) -> "Rule": ...


class Constraint(Expr):
    # Uses built-in Vec[LetExpr] for the list of let bindings
    @method(cost=10000)
    def __init__(cls, lets: Vec[LetExpr], body: Formula) -> Constraint: ...

    @method(cost=0)
    @classmethod
    def integrity_constraints(cls, vars: Set[Term], formulas: Set[GeneralLit]) -> Constraint: ...


class ConsList(Expr):
    pass

class Block(Expr):
    # A Block is a Set of Rules and a Set of Constraints.
    # We use the built-in Set generic.
    def __init__(cls, rules: Set[Rule], constraints: ConsList) -> "Block": ...

@function(cost=0)
def cons_constraint(head: Constraint, tail: ConsList) -> ConsList: ...
@function
def nil_constraint() -> ConsList: ...
converter(tuple, ConsList, lambda t: nil_constraint() if not t else cons_constraint(t[0], t[1:]))
converter(list, ConsList, lambda t: nil_constraint() if not t else cons_constraint(t[0], t[1:]))


# ==========================================
# 6. Auxiliary Predicate Support
# ==========================================

# Collect all variables from a Set[Literal] (using var_set internally)
@function(merge=lambda a, b: a.__or__(b))
def vars_in_lits(lits: Set[Literal]) -> Set[Term]: ...

# A marker relation to track which formulas need aux predicates
# (The actual aux name assignment happens in Python post-processing)
needs_aux = relation("needs_aux", Formula, Set[Term])  # (formula, free_vars)
