import os
from functools import lru_cache

from lark import Lark
from .transformer import AstTransformer
from ..ast import nodes


@lru_cache(maxsize=1)
def _build_lark() -> Lark:
    """The Lark parser, built once per process.

    LALR with the contextual lexer: linear in the input, where the Earley
    parser with the dynamic lexer took about 8 ms per statement and was the
    whole compile time of a large model (94 s of 96 s at 12,000 statements).
    The grammar reserves a bare predicate atom statement for facts so that it
    is LALR(1); see grammar.lark.
    """
    grammar_path = os.path.join(os.path.dirname(__file__), "grammar.lark")
    with open(grammar_path, "r", encoding="utf-8") as f:
        grammar = f.read()
    return Lark(grammar, start="start", parser="lalr", lexer="contextual")


class Parser:
    def __init__(self):
        self.lark = _build_lark()
        self.transformer = AstTransformer()

    def parse(self, text: str) -> nodes.Program:
        try:
            tree = self.lark.parse(text)
            return self.transformer.transform(tree)
        except Exception as e:
            print(f"Parsing Failed: {e}")
            raise
