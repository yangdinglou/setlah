"""
Test automatic entailment registration and simplification.
"""

import sys
import os

from setlah.parsing.parser import Parser
from setlah.rewrite.rw import Rewriter


def test_auto_entailment():
    """
    Test that entailments are automatically detected and used for simplification.
    """
    program = r"""
ExtDOM Index: INT.

[
    % greek entails dom_Index on first argument
    greek(A, B, C)? :- dom_Index(A), dom_Index(B), dom_Index(C).
]

[
    % This conjunction should simplify: greek(R,C,A) ∧ dom_Index(R) → greek(R,C,A)
    (\forall R, C, A. (\impl (\and greek(R, C, A) dom_Index(R)) 
                              (\exists X. dom_Index(X)))).
]
"""
    
    print("=== Testing Automatic Entailment Registration ===\n")
    
    p = Parser()
    ast = p.parse(program)
    
    rw = Rewriter()
    result = rw.rewrite_program(ast, convert_only=False)
    
    print("\n=== Test Complete ===")
    return result


if __name__ == "__main__":
    test_auto_entailment()
