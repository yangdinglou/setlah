import unittest
from egglog import *
from setlah.rewrite.egg_schema import *
from setlah.rewrite.egg_rules import *

# Helper to construct terms easily
def make_atom(name, *args):
    # Atom.Pred takes (StringLike, VarList)
    # VarList has a converter from list, so we pass list(args)
    return Formula.Lit((Atom.Pred(name, list(args))))

def make_var(name):
    return Term.Var(name)

class TestEggRules(unittest.TestCase):
    
    def check_eq(self, lhs, rhs, steps=30):
        """Helper to register expressions and check equality after saturation."""
        egraph = EGraph()
        egraph.register(lhs)
        # egraph.register(rhs)
        egraph.run((term_set + equal_set).saturate()+extraction*3)
        
        # Check if lhs is equivalent to rhs
        is_eq = egraph.check_bool(lhs==rhs)
        
        # Debug print if failed
        if not is_eq:
            print(f"\n[FAIL] Expected: {lhs}\n       To equal: {rhs}")
            egraph.saturate(visualize=True)
            
        self.assertTrue(is_eq, f"Failed to prove equivalence: {lhs} == {rhs}")

    def test_01_double_negation(self):
        """Test ~~A => A"""
        A = make_atom("A")
        lhs = Formula.Not(Formula.Not(A))
        self.check_eq(lhs, A)

    def test_02_de_morgan(self):
        """Test ~(A & B) => ~A | ~B"""
        A = make_atom("A")
        B = make_atom("B")
        
        # ~(A & B)
        lhs = Formula.Not(Formula.And(A, B))
        # ~A | ~B
        rhs = Formula.Or(Formula.Not(A), Formula.Not(B))
        
        self.check_eq(lhs, rhs)

    def test_03_implication(self):
        """Test A -> B => ~A | B"""
        A = make_atom("A")
        B = make_atom("B")
        
        lhs = Formula.Implies(A, B)
        rhs = Formula.Or(Formula.Not(A), B)
        
        self.check_eq(lhs, rhs)

    def test_04_distributivity_and_over_or(self):
        """Test A & (B | C) => (A & B) | (A & C)"""
        A = make_atom("A")
        B = make_atom("B")
        C = make_atom("C")
        
        # A & (B | C)
        or_inner = Formula.Or(B, C)
        lhs = Formula.And(A, or_inner)
        
        # (A & B) | (A & C)
        rhs = Formula.Or(
            Formula.And(A, B),
            Formula.And(A, C)
        )
        
        self.check_eq(lhs, rhs)

    def test_05_quantifier_negation(self):
        """Test ~Forall x. P(x) => Exists x. ~P(x)"""
        x = make_var("x")
        P_x = make_atom("P", x)
        
        lhs = Formula.Not(Formula.Forall(x, P_x))
        rhs = Formula.Exists(x, Formula.Not(P_x))
        
        self.check_eq(lhs, rhs)

    def test_06_vacuous_quantification(self):
        """
        Test Forall x. (P(x) & Q) => (Forall x. P(x)) & Q
        where Q does not contain x.
        """
        x = make_var("x")
        y = make_var("y")
        
        P_x = make_atom("P", x) # Contains x
        Q_y = make_atom("Q", y) # Does NOT contain x
        
        # Forall x. (P(x) & Q(y))
        inner = Formula.And(P_x, Q_y)
        lhs = Formula.Forall(x, inner)
        
        # (Forall x. P(x)) & Q(y)
        rhs = Formula.And(
            Formula.Forall(x, P_x),
            Q_y
        )
        
        self.check_eq(lhs, rhs)

    def test_07_quantifier_distributivity(self):
        """
        Test Forall x. (P(x) & R(x)) => (Forall x. P(x)) & (Forall x. R(x))
        (Lec10 Rule C)
        """
        x = make_var("x")
        P_x = make_atom("P", x)
        R_x = make_atom("R", x)
        
        # Forall x. (P(x) & R(x))
        inner = Formula.And(P_x, R_x)
        lhs = Formula.Forall(x, inner)
        
        # (Forall x. P(x)) & (Forall x. R(x))
        rhs = Formula.And(
            Formula.Forall(x, P_x),
            Formula.Forall(x, R_x)
        )
        
        self.check_eq(lhs, rhs)

    def test_08_quantifier_commutativity(self):
        """Test Forall x. Forall y. P(x,y) => Forall y. Forall x. P(x,y)"""
        x = make_var("x")
        y = make_var("y")
        P_xy = make_atom("P", x, y)
        
        lhs = Formula.Forall(x, Formula.Forall(y, P_xy))
        rhs = Formula.Forall(y, Formula.Forall(x, P_xy))
        
        self.check_eq(lhs, rhs)
    
    def test_09_neg_quantification(self):
        """Test ~Exists x. P(x) => Forall x. ~P(x)"""
        x = make_var("x")
        P_x = make_atom("P", x)
        
        lhs = Formula.Not(Formula.Exists(x, P_x))
        rhs = Formula.Forall(x, Formula.Not(P_x))
        
        self.check_eq(lhs, rhs)

    def test_10_implies_and_distribution(self):
        """Test A -> (B & C) => (A -> B) & (A -> C)"""
        A = make_atom("A")
        B = make_atom("B")
        C = make_atom("C")
        
        lhs = Formula.Implies(A, Formula.And(B, C))
        rhs = Formula.And(
            Formula.Implies(A, B),
            Formula.Implies(A, C)
        )
        
        self.check_eq(lhs, rhs)

    def test_11_grouped_quantifiers(self):
        """Test grouping of quantifiers"""
        x = make_var("x")
        y = make_var("y")
        P_xy = make_atom("P", x, y)
        
        # Forall x. Forall y. P(x,y)
        lhs = Formula.Forall(x, Formula.Forall(y, P_xy))
        # grouped_forall({x,y}, P(x,y))
        rhs = Formula.grouped_forall(Set[Term](x, y), P_xy)
        
        self.check_eq(lhs, rhs)

    def test_12_neg_quantifer_with_constant(self):
        """Test ~Exists x. P(x, c) => Forall x. ~P(x, c)"""
        x = make_var("x")
        c = Term.Symbol("c")
        P_xc = make_atom("P", x, c)
        
        lhs = Formula.Not(Formula.Exists(x, P_xc))
        rhs = Formula.Forall(x, Formula.Not(P_xc))
        
        self.check_eq(lhs, rhs)
if __name__ == '__main__':
    unittest.main()
    # A = make_atom("A")
    # lhs = Formula.Not(Formula.Not(A))
    # egraph.register(lhs)
    # egraph.saturate(30)
    # print(egraph.extract(lhs))
