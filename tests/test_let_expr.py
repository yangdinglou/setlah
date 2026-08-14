"""
Test Let expression transpilation.
"""
import sys

from setlah.parsing.parser import Parser
from setlah.rewrite.rw import Rewriter
from setlah.transpile import transpile_program_to_asp


def test_let_simple():
    """Test a simple Let expression with partition."""
    code = r"""
ExtDOM Clause : Symbol.
ExtPred cl : (Symbol, Symbol, Symbol).

Const t : Symbol.

[
    c(t, I)? :- cl(I, L1, L2).
    ac(t, I)? :- cl(I, L1, L2).
    dc(t, I)? :- cl(I, L1, L2).
    
    Let {ClKey}(I) = { (t, I) | (I, L1, L2) in {Cl}, \true } in
        (\partition Set_clKey {{Set_c Set_ac Set_dc}}).
]
"""
    program = Parser().parse(code)
    rw = Rewriter(verbose=True)
    rewritten = rw.rewrite_program(program, convert_only=False)
    print("=== Rewritten (egg blocks) ===")
    for block in rewritten.blocks:
        print(block)
    print()
    
    result = transpile_program_to_asp(rewritten, grounding=False)
    print("=== ASP output ===")
    print(result)
    

def test_let_print_egg():
    """Just print the egg format to understand structure."""
    code = r"""
ExtDOM Clause : Symbol.
ExtPred cl : (Symbol, Symbol, Symbol).

Const t : Symbol.

[
    Let {ClKey}(I) = { (t, I) | (I, L1, L2) in {Cl}, \true } in
        \true.
]
"""
    program = Parser().parse(code)
    rw = Rewriter(verbose=True)
    rewritten = rw.rewrite_program(program, convert_only=True)
    print("=== Rewritten (egg blocks) ===")
    for block in rewritten.blocks:
        print(block)
        print()


if __name__ == "__main__":
    print("=== test_let_print_egg ===")
    test_let_print_egg()
    print("\n" + "="*50 + "\n")
    print("=== test_let_simple ===")
    test_let_simple()
