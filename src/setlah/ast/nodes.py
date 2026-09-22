from dataclasses import dataclass, field
from typing import List, Optional, Union, Any

@dataclass
class AstNode:
    def __repr__(self):
        return f"{self.__class__.__name__}(...)"

    def dump(self, level=0, prefix=""):
        indent = "  " * level
        lines = [f"{indent}{prefix}{self.__class__.__name__}"]
        for k, v in self.__dict__.items():
            if k.startswith('_'): continue
            if isinstance(v, AstNode):
                lines.append(v.dump(level + 1, f"{k}: "))
            elif isinstance(v, list) and v and isinstance(v[0], AstNode):
                lines.append(f"{indent}  {k}: [")
                for item in v:
                    lines.append(item.dump(level + 2, ""))
                lines.append(f"{indent}  ]")
            elif v is not None:
                lines.append(f"{indent}  {k}: {repr(v)}")
        return "\n".join(lines)

ExprType = Union['Variable', 'Constant', 'BinaryExpr']

@dataclass
class BinaryExpr(AstNode):
    left: ExprType
    op: str
    right: ExprType
    def __repr__(self): return f"({self.left} {self.op} {self.right})"

@dataclass
class TypeNode(AstNode): pass
@dataclass
class IntType(TypeNode): 
    def __repr__(self): return "INT"
@dataclass
class SymbolType(TypeNode): 
    name: Optional[str] = None
    def __repr__(self): return f"Sym({self.name or ''})"
@dataclass
class TupleType(TypeNode):
    subtypes: List[TypeNode]
    def __repr__(self): return f"Tuple({self.subtypes})"

@dataclass
class Identifier(AstNode):
    name: str
    def __repr__(self): return f"Id({self.name})"
@dataclass
class Variable(AstNode):
    name: str
    def __repr__(self): return f"Var({self.name})"
@dataclass
class Constant(AstNode):
    value: Any 
    def __repr__(self): return f"Const({self.value})"
@dataclass
class TupleVar(AstNode):
    elements: List[ExprType]
    def __repr__(self): return f"({', '.join(map(str, self.elements))})"

@dataclass
class DomainDecl(AstNode): pass
@dataclass
class SetDefinition(AstNode): pass
@dataclass
class SetEnum(SetDefinition):
    values: List[Constant]
@dataclass
class IntRange(SetDefinition):
    start: Constant
    end: Constant
    def __repr__(self): return f"Range({self.start}..{self.end})"
@dataclass
class DefDOM(DomainDecl):
    var: Variable
    dtype: TypeNode
    set_def: SetDefinition
@dataclass
class ExtDOM(DomainDecl):
    var: Variable
    dtype: TypeNode
    input_var: Variable
@dataclass
class OrdDOM(DomainDecl):
    """An order sort: integers in [lo, hi], used only in comparisons (docs/order-sorts.md)."""
    var: Variable
    lo: Constant
    hi: Constant

@dataclass
class FunDecl(DomainDecl):
    """A total function from finite sorts into an order sort, written as a predicate
    with the value as its last argument."""
    name: Identifier
    args: List[Variable]
    result: Variable

@dataclass
class ExtPred(DomainDecl):
    name: Identifier
    tuple_var: TupleVar
@dataclass
class ConstDecl(DomainDecl):
    name: Identifier
    dtype: TypeNode
    value: Optional[Constant] = None

@dataclass
class SetExpr(AstNode): pass
@dataclass
class EmptySet(SetExpr): 
    def __repr__(self): return "EMPTY"
@dataclass
class SetVar(SetExpr):
    name: str
    parameters: Optional[TupleVar] = None
    def __repr__(self):
        p = f"({self.parameters})" if self.parameters else ""
        return f"SetVar({self.name}{p})"
@dataclass
class SetOperation(SetExpr):
    op: str
    left: SetExpr
    right: SetExpr

@dataclass
class SetComprehension(SetExpr):
    # Normalized: Always store as TupleVar (e.g., P -> TupleVar([P]))
    term: TupleVar 
    domain_term: TupleVar
    domain_set: SetExpr
    condition: 'FoSet'

@dataclass
class FoSet(AstNode): pass
@dataclass
class PredAtom(FoSet):
    predicate: Identifier
    args: List[ExprType]
    def __repr__(self):
        return f"{self.predicate.name}({', '.join(map(str, self.args))})"

@dataclass
class LogicalOp(FoSet):
    op: str
    operands: List[FoSet]
    def __repr__(self): return f"{self.op}{self.operands}"
@dataclass
class QuantifiedFormula(FoSet):
    quantifier: str
    variable: Variable
    body: FoSet
    def __repr__(self): return f"{self.quantifier} {self.variable}. {self.body}"
@dataclass
class SetMembership(FoSet):
    element: Variable
    set_expr: SetExpr
    def __repr__(self): return f"belonging({self.element}, {self.set_expr})"
@dataclass
class SetSubset(FoSet):
    left_set: Variable
    right_set: SetExpr
    def __repr__(self): return f"subset({self.left_set}, {self.right_set})"
@dataclass
class SetPartition(FoSet):
    target_set: Variable 
    parts: List[Variable] 
    def __repr__(self): return f"partition({self.target_set}, {self.parts})"
@dataclass
class SetPred(FoSet):
    predicate: str
    def __repr__(self): return f"Set_{{{self.predicate}}}"
@dataclass
class BooleanConst(FoSet):
    val: bool
    def __repr__(self): return str(self.val)
@dataclass
class Comparison(FoSet):
    left: ExprType
    op: str
    right: ExprType
    def __repr__(self): return f"({self.left} {self.op} {self.right})"
@dataclass
class Aggregation(FoSet):
    op: str
    set_var: SetVar
    comp_op: str
    value: ExprType
    def __repr__(self): return f"{self.op} {self.set_var} {self.comp_op} {self.value}"

Literal = Union[PredAtom, Comparison]

@dataclass
class Statement(AstNode): pass
@dataclass
class Rule(Statement):
    head: PredAtom
    body: List[Literal]
    is_choice: bool
    def __repr__(self):
        h = f"{{{self.head}}}" if self.is_choice else f"{self.head}"
        b = f" :- {self.body}" if self.body else "."
        return f"{h}{b}"

@dataclass
class LetExpr(AstNode):
    variable: SetVar
    value: SetExpr
    def __repr__(self): return f"Let {self.variable} = {self.value}"
@dataclass
class SetConstraint(Statement):
    let_exprs: List[LetExpr]
    formula: FoSet
    def __repr__(self):
        lets = " ".join(map(str, self.let_exprs))
        return f"{lets} {self.formula}" if lets else f"{self.formula}"
@dataclass
class Block(AstNode):
    statements: List[Statement]
    def __repr__(self): 
        return f"Block(\n    " + "\n    ".join(map(str, self.statements)) + "\n  )"
@dataclass
class Program(AstNode):
    domains: List[DomainDecl]
    blocks: List[Block]