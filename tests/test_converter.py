from setlah.parsing.parser import Parser
from setlah.rewrite.rw import Rewriter

import sys
import os

# Add parent directory to path


def get_ast_from_file(filename):
    # Path to the example.mylang file (assumed to be in root or same dir)
    # We look one level up from 'tests/'
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

        
        return ast
        
    except Exception as e:
        print(f"❌ Parse Error: {e}")
        # Print a snippet of the file around the error if possible
        # (Lark usually handles this, but we can add custom debug here if needed)
        return None

if __name__ == "__main__":
    filename = sys.argv[1] if len(sys.argv) > 1 else 'example.sl'
    print(f"Testing parsing for file: {filename}")
    ast = get_ast_from_file(filename)
    if ast:
        rewriter = Rewriter(enable_cost_conversion=True,verbose=True)
        new_ast = rewriter.rewrite_program(ast, convert_only=False)