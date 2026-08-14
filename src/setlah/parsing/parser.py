import os
from lark import Lark
from .transformer import AstTransformer
from ..ast import nodes

class Parser:
    def __init__(self):
        # Load grammar from the same directory
        grammar_path = os.path.join(os.path.dirname(__file__), 'grammar.lark')
        with open(grammar_path, 'r', encoding='utf-8') as f:
            grammar = f.read()
            
        self.lark = Lark(grammar, start='start', parser='earley', lexer='dynamic')
        self.transformer = AstTransformer()

    def parse(self, text: str) -> nodes.Program:
        try:
            # 1. Parse text into a generic Tree
            tree = self.lark.parse(text)
            
            # 2. Transform Tree into specific AST nodes
            ast = self.transformer.transform(tree)
            return ast
            
        except Exception as e:
            # You might want to catch specific Lark errors here
            # like lark.exceptions.UnexpectedToken
            print(f"Parsing Failed: {e}")
            raise e