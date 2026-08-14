from lark import Transformer, v_args
from ..ast import nodes as nodes

class AstTransformer(Transformer):
    def start(self, items):
        domains = [i for i in items if isinstance(i, nodes.DomainDecl)]
        blocks = [i for i in items if isinstance(i, nodes.Block)]
        return nodes.Program(domains=domains, blocks=blocks)
    
    def domain_decl(self, items): return items[0]
    def block(self, items): return nodes.Block(statements=items)

    def ext_dom(self, items):
        return nodes.ExtDOM(var=items[0], dtype=items[1], input_var=items[2] if len(items) > 2 else items[0])

    def ext_pred(self, items): return nodes.ExtPred(name=items[0], tuple_var=items[1]) 

    def pred_sig(self, items):
        vars_list = []
        for item in items:
            name = item.name if hasattr(item, 'name') and item.name else "Unknown"
            vars_list.append(nodes.Variable(name=name))
        return nodes.TupleVar(elements=vars_list)

    def const_decl(self, items):
        return nodes.ConstDecl(name=items[0], dtype=items[1], value=items[2] if len(items) > 2 else None)

    def type_int(self, _): return nodes.IntType()
    def type_sym(self, _): return nodes.SymbolType()
    def type_custom(self, items): return nodes.SymbolType(name=items[0].name)
    def type_tuple(self, items): return nodes.TupleType(subtypes=items)

    def rule(self, items):
        head = items[0]
        is_choice = isinstance(head, dict) and head.get('is_choice', False)
        return nodes.Rule(head=head['node'] if is_choice else head, body=items[1] if len(items) > 1 else [], is_choice=is_choice)

    def choice_head(self, items): return {'is_choice': True, 'node': items[0]}
    def head_part(self, items): return items[0]
    def body_part(self, items): return items
    def literal(self, items): return items[0]

    def set_constraint(self, items):
        return nodes.SetConstraint(let_exprs=[x for x in items if isinstance(x, nodes.LetExpr)], formula=items[-1])

    def let_expr(self, items): return nodes.LetExpr(variable=items[0], value=items[1])
    def empty_set(self, _): return nodes.EmptySet()
    def set_var(self, items):
        return nodes.SetVar(name=items[0].name, parameters=items[1] if len(items) > 1 else None)
    
    def set_op_expr(self, items):
        return nodes.SetOperation(left=items[1], op=str(items[0]), right=items[2])
    
    def set_comprehension(self, items):
        return nodes.SetComprehension(
            term=items[0], 
            domain_term=items[1], 
            domain_set=items[2],
            condition=items[3]
        )
    
    # def comp_item(self, items):
    #     # items[0] is either a Variable/Constant OR a TupleVar
    #     node = items[0]
    #     if isinstance(node, nodes.TupleVar):
    #         return node
    #     # Wrap single item in TupleVar to normalize AST  
    #     return nodes.TupleVar(elements=[node])

    def set_membership(self, items):
        return nodes.SetMembership(element=items[0], set_expr=items[1])
    
    def set_pred(self, items):
        return nodes.SetPred(predicate=items[0])

    def set_subset(self, items):
        return nodes.SetSubset(left_set=items[0], right_set=items[1])

    def set_partition(self, items):
        return nodes.SetPartition(target_set=items[0], parts=items[1])
    
    def set_of_sets(self, items):
        # items are already Variable nodes from upper_id rule
        return items

    def quantified_formula(self, items):
        q = str(items[0])
        q_norm = 'forall' if q in ('\\forall', '∀') else 'exists'
        body = items[-1]
        vars_list = items[1:-1]
        res = body
        for var in reversed(vars_list):
            res = nodes.QuantifiedFormula(quantifier=q_norm, variable=var, body=res)
        return res
    
    def true_const(self, _): return nodes.BooleanConst(val=True)
    def false_const(self, _): return nodes.BooleanConst(val=False)

    def logic_op(self, items):
        op = self._normalize_op(str(items[0]))
        return nodes.LogicalOp(op=op, operands=items[1:])
    
    def aggregation(self, items):
        op = str(items[0])
        set_var = items[1]
        idx = 2
        if idx < len(items) and isinstance(items[idx], nodes.TupleVar):
            set_var.parameters = items[idx]
            idx += 1
        comp_op = self._normalize_op(str(items[idx]))
        return nodes.Aggregation(op=op, set_var=set_var, comp_op=comp_op, value=items[idx + 1])
    
    def add(self, items): return nodes.BinaryExpr(op='+', left=items[0], right=items[1])
    def sub(self, items): return nodes.BinaryExpr(op='-', left=items[0], right=items[1])
    def mul(self, items): return nodes.BinaryExpr(op='*', left=items[0], right=items[1])
    def div(self, items): return nodes.BinaryExpr(op='/', left=items[0], right=items[1])

    def arith_expr(self, items):
        return nodes.BinaryExpr(op=str(items[0]), left=items[1], right=items[2])

    def infix_comp(self, items):
        return nodes.Comparison(op=self._normalize_op(str(items[1])), left=items[0], right=items[2])

    def prefix_comp(self, items):
        return nodes.Comparison(op=self._normalize_op(str(items[0])), left=items[1], right=items[2])
    
    def pred_atom(self, items):
        return nodes.PredAtom(predicate=items[0], args=items[1] if len(items) > 1 else [])
    
    def arg_list(self, items): return items
    def upper_id(self, items): return nodes.Variable(name=str(items[0]))
    def lower_id(self, items): return nodes.Identifier(name=str(items[0]))
    def constant(self, items): return nodes.Constant(value=int(items[0]))
    def constant_or_var(self, items): return items[0]
    def tuple_var(self, items): return nodes.TupleVar(elements=items)

    def _normalize_op(self, op: str) -> str:
        op_map = {
            '\\and': 'and', '∧': 'and', '&': 'and',
            '\\or': 'or', '∨': 'or', '|': 'or',
            '\\impl': 'impl', '→': 'impl', '->': 'impl',
            '\\neg': 'not', '¬': 'not', '!': 'not',
            '=': '==', '==': '==',
            '!=': '!=', '<>': '!=',
            '>': '>', '<': '<', '>=': '>=', '<=': '<=',
            'in': 'in', '∊': 'in'
        }
        return op_map.get(op, op)