"""
Test file for semantic checker.
Tests type checking, predicate signature inference, and dependency analysis.
"""

import sys
import os


from setlah.parsing.parser import Parser
from setlah.parsing.checker import SemanticChecker


def get_ast_from_file(filename):
    """Parse a file and return the AST."""
    # Path to the file (relative to test directory)
    file_path = os.path.join(os.path.dirname(__file__), 'inputs', filename)
    
    if not os.path.exists(file_path):
        print(f"Error: Could not find {file_path}")
        return None

    print(f"Reading from: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    p = Parser()
    try:
        ast = p.parse(content)
        print(f"✅ Parsing successful")
        print(f"  - Domains parsed: {len(ast.domains)}")
        print(f"  - Blocks parsed:  {len(ast.blocks)}")
        return ast
        
    except Exception as e:
        print(f"❌ Parse Error: {e}")
        return None


def test_semantic_check(filename='example.sl'):
    """Test semantic checking on a file."""
    print(f"\n{'='*60}")
    print(f"Testing semantic checker for: {filename}")
    print('='*60)
    
    # Parse the file
    ast = get_ast_from_file(filename)
    if not ast:
        print("❌ Failed to parse file")
        return False
    
    print()
    
    # Run semantic checker
    checker = SemanticChecker()
    success = checker.check_program(ast)
    
    print()
    if success:
        print("✅ Semantic check passed!")
        return True
    else:
        print("❌ Semantic check failed!")
        return False


def test_inline_programs():
    """Test semantic checking on inline program strings."""
    parser = Parser()
    
    # Program with undefined variable in body
    error_program_1 = r"""
ExtDOM D: INT.
ExtPred p: (D).
[
    p(X) :- p(Z).
]
"""

    # Valid program with external predicates and rules
    valid_program = r"""
ExtDOM D: INT.
ExtPred p: (D).
Const c: INT.
[
    q(X) :- p(X).
    q(c).
]
"""

    # Program with type mismatch
    error_program_2 = r"""
ExtDOM D1: INT.
ExtDOM D2: INT.
ExtPred p: (D1).
ExtPred q: (D2).
[
    r(X) :- p(X), q(X).
]
"""

    # Program with undefined predicate in body
    error_program_3 = r"""
ExtDOM D: INT.
[
    p(X) :- q(X).
]
"""

    tests = [
        ("Valid Program", valid_program, True),
        ("Undefined Variable", error_program_1, False),
        ("Type Mismatch", error_program_2, False),
        ("Undefined Predicate", error_program_3, False),
    ]
    
    for test_name, program, should_pass in tests:
        print(f"\n{'='*60}")
        print(f"TEST: {test_name}")
        print('='*60)
        
        try:
            ast = parser.parse(program)
            checker = SemanticChecker()
            success = checker.check_program(ast)
            
            if success == should_pass:
                print(f"✅ Test passed (expected {'success' if should_pass else 'failure'})")
            else:
                print(f"❌ Test failed (expected {'success' if should_pass else 'failure'}, got {'success' if success else 'failure'})")
        except Exception as e:
            print(f"❌ Unexpected exception: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Test a specific file
        filename = sys.argv[1]
        test_semantic_check(filename)
    else:
        # Run inline tests first
        print("\n" + "="*60)
        print("RUNNING INLINE TESTS")
        print("="*60)
        test_inline_programs()
        
        # Then test default file
        print("\n\n" + "="*60)
        print("TESTING DEFAULT FILE (example.sl)")
        print("="*60)
        test_semantic_check('example.sl')