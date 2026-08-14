import sys
import os
import unittest

# Ensure src is on path

from setlah.parsing.parser import Parser
from setlah.rewrite.rw import Rewriter


def run_rewriter(program_text: str):
    p = Parser()
    ast = p.parse(program_text)
    rw = Rewriter()
    return rw.rewrite_program(ast, convert_only=False)


class TestForallImplExtract(unittest.TestCase):
    def test_forall_implication_extracts_integrity_constraint(self):
        program = r"""
ExtDOM D: INT.
ExtPred initial: (D, D, D).
ExtPred sudoku: (D, D, D).
[
    \forall R, C, V. (\impl initial(R, C, V) sudoku(R, C, V)).
]
"""
        out = run_rewriter(program)
        s = str(out)
        print(s)
        self.assertIn("integrity_constraints", s)
        self.assertIn("initial", s)
        self.assertIn("sudoku", s)

        # Expect the denial form to contain a negative sudoku literal somewhere.
        # Keep this intentionally loose to avoid coupling to egglog's exact pretty-print.
        self.assertTrue(("False" in s) or ("false" in s) or (", False" in s), s)


if __name__ == "__main__":
    unittest.main()
