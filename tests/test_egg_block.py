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

def make_constraint(body):
    return Constraint(lets=Vec[LetExpr](), body=body)

class TestEggRules(unittest.TestCase):
    
    def check_eq(self, lhs, rhs, steps=30):
        """Helper to register expressions and check equality after saturation."""
        egraph = EGraph()
        egraph.register(lhs)
        # egraph.register(rhs)
        egraph.run((split_set + term_set + equal_set).saturate())
        
        # Check if lhs is equivalent to rhs
        is_eq = egraph.check_bool(lhs==rhs)
        
        # Debug print if failed
        if not is_eq:
            print(f"\n[FAIL] Expected: {lhs}\n       To equal: {rhs}")
            # print(f"LHS Class: {egraph.extract(lhs)}")
            # print(f"RHS Class: {egraph.extract(rhs)}")
            
        self.assertTrue(is_eq, f"Failed to prove equivalence: {lhs} == {rhs}")

    def test_01_conjunction_split(self):
        """Test f(X) & g(Y) can be split into two constraints."""
        fX = make_atom("f", make_var("X"))
        gY = make_atom("g", make_var("Y"))
        
        lhs = Block(rules=Set[Rule](), constraints=cons_constraint(make_constraint(Formula.And(fX, gY)), nil_constraint()))
        rhs = Block(rules=Set[Rule](), constraints=cons_constraint(make_constraint(fX), cons_constraint(make_constraint(gY), nil_constraint())))
        self.check_eq(lhs, rhs)

if __name__ == '__main__':
    unittest.main()
    # A = make_atom("A")
    # lhs = Formula.Not(Formula.Not(A))
    # egraph.register(lhs)
    # egraph.saturate(30)
    # print(egraph.extract(lhs))
