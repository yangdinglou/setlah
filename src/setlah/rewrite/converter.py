from functools import singledispatch
from ..ast import nodes
from .egg_schema import *
from functools import reduce

import sys

# Debug flags
DEBUG_MODE = False
_DEPTH = 0

# Predicate signature info (set by Rewriter before conversion)
_pred_canonical_args: dict[str, list[str]] = {}  # pred_name -> canonical arg names

# Forall context stack (tracks universally quantified variables during conversion)
_forall_vars: list[str] = []

def set_pred_signatures(pred_info: dict) -> None:
    """Set predicate signatures from checker. Called by Rewriter before conversion."""
    global _pred_canonical_args
    _pred_canonical_args = {
        name: info.canonical_args
        for name, info in pred_info.items()
        if info.canonical_args
    }

def debug_log(msg):
    if DEBUG_MODE:
        print(f"{'  ' * _DEPTH} [DEBUG] {msg}", file=sys.stderr)

class TraceContext:
    """Context manager to handle indentation automatically."""
    def __enter__(self):
        global _DEPTH
        _DEPTH += 1
    def __exit__(self, exc_type, exc_val, exc_tb):
        global _DEPTH
        _DEPTH -= 1

# 1. Create a dispatcher for each major Egglog Sort (Formula, Term, SetExpr)
@singledispatch
def to_egg(node) -> Expr:
    """Default handler for unknown nodes."""
    raise NotImplementedError(f"No egglog conversion for {type(node)}\nNode: {node}")

# --- Term Converters ---
@to_egg.register
def _(node: nodes.Constant):
    return Term.Int(node.value)

@to_egg.register
def _(node: nodes.Variable):
    return Term.Var(node.name)

@to_egg.register
def _(node: nodes.Identifier):
    return Term.Symbol(name=node.name)  # Treat identifier as a variable/constant term

@to_egg.register
def _(node: nodes.BinaryExpr):
    return Term.BinaryExpr(
        node.op, 
        to_egg(node.left), 
        to_egg(node.right)
    )

# --- Set Expression Converters ---
@to_egg.register
def _(node: nodes.SetVar):
    if not node.parameters:
        return SetExpr.SetVar(node.name, [])
    print("SetVar with parameters?")
    params = [to_egg(param) for param in node.parameters.elements]
    
    tmp = SetExpr.SetVar(node.name, params)
    print(f"Converted SetVar: {tmp}")
    return tmp

@to_egg.register
def _(node: nodes.EmptySet):
    return SetExpr.Empty()


@to_egg.register
def _(node: nodes.SetOperation):
    l, r = to_egg(node.left), to_egg(node.right)
    # Map string op to class method
    op_map = {
        '∪': SetExpr.Union, 'union': SetExpr.Union,
        '∩': SetExpr.Inter, 'inter': SetExpr.Inter,
        'Δ': SetExpr.Diff,  'diff':  SetExpr.Diff,
        '⊕': SetExpr.SymDiff, 'symdiff': SetExpr.SymDiff
    }
    return op_map[node.op](l, r)

@to_egg.register
def _(node: nodes.SetComprehension):
    # Convert term, domain variables, domain set, and condition
    term = [to_egg(t) for t in node.term.elements]
    print(1)
    dom_vars = Vec[StringLike](*[v.name for v in node.domain_term.elements])
    print(2)
    dom_set = to_egg(node.domain_set)
    condition = to_egg(node.condition)
    return SetExpr.Set_Comprehension(term, dom_vars, dom_set, condition)

# --- Atom Converters ---
@to_egg.register
def _(node: nodes.PredAtom):
    # debug_log(f"Converting PredAtom: {node}")
    args = [to_egg(arg) for arg in node.args]
    # debug_log(f"Converted args: {args}")
    return Atom.Pred(node.predicate.name, args)
@to_egg.register
def _(node: nodes.Comparison):
    left = to_egg(node.left)
    right = to_egg(node.right)
    return Atom.Comp(node.op, left, right)

# --- Formula Converters ---
@to_egg.register
def _(node: nodes.LogicalOp):
    # Convert all children recursively
    ops = [to_egg(op) for op in node.operands]
    debug_log(f"LogicalOp conversion: op={node.op}, operands={ops}")
    if node.op in ('and', '∧'): 
        assert len(ops) >= 2, "And requires at least two operands"
        return reduce(lambda right, left: Formula.And(left, right), reversed(ops))
    if node.op in ('or', '∨'):  
        assert len(ops) >= 2, "Or requires at least two operands"
        return reduce(lambda right, left: Formula.Or(left, right), reversed(ops))
    if node.op in ('not', '¬'): 
        assert len(ops) == 1, "Not requires exactly one operand"
        return Formula.Not(ops[0])
    if node.op in ('impl', '→'): 
        assert len(ops) == 2, "Implies requires exactly two operands"
        return Formula.Implies(ops[0], ops[1])
    raise ValueError(f"Unknown op {node.op}")

@to_egg.register
def _(node: nodes.BooleanConst):
    return Formula.Bool(node.val)

# @to_egg.register
# def _(node: nodes.Literal):
#     # Dispatch to Atom conversion
#     return Formula.Literal(node.
@to_egg.register
def _(node: nodes.QuantifiedFormula):
    var_name = to_egg(node.variable)
    if node.quantifier in ('forall', '∀'):
        _forall_vars.append(node.variable.name)
        body_formula = to_egg(node.body)
        _forall_vars.pop()
        return Formula.Forall(var_name, body_formula)
    elif node.quantifier in ('exists', '∃'):
        body_formula = to_egg(node.body)
        return Formula.Exists(var_name, body_formula)
    else:
        raise ValueError(f"Unknown quantifier {node.quantifier}")


@to_egg.register
def _(node: nodes.SetMembership):
    element = to_egg(node.element)
    # Assuming set_expr is a SetVar for simplicity
    set_name = to_egg(node.set_expr)
    return Formula.Belonging(element, set_name)

@to_egg.register
def _(node: nodes.SetSubset):
    left_set = to_egg(node.left_set)
    right_set = to_egg(node.right_set)
    return Formula.Subset(left_set, right_set)

@to_egg.register
def _(node: nodes.SetPartition):
    target_set = to_egg(node.target_set)
    parts = [to_egg(part) for part in node.parts]
    return Formula.Partition(target_set, parts)

@to_egg.register
def _(node: nodes.Aggregation):
    op = node.op
    comp_op = node.comp_op
    value = to_egg(node.value)

    # Normalize comparison operator to match egglog conventions
    # Parser produces "=" but egglog birewrite rules use "=="
    if comp_op == "=":
        comp_op = "=="

    if node.set_var.parameters:
        # Desugar projected aggregation to GeneralLit.general_agg
        # #count {Set_pred}(counted_vars) op val  (under \forall param_vars)
        # → Lit(general_agg("count", set_comprehension({counted}, [pred(all_args)]), op, val))
        set_name = node.set_var.name
        # Strip "Set_" prefix and lowercase to get predicate name
        pred_name = set_name[4:] if set_name.startswith("Set_") else set_name
        pred_name = pred_name.lower()

        # Counted vars from projection tuple
        counted_terms = [to_egg(p) for p in node.set_var.parameters.elements]
        counted_names = {p.name for p in node.set_var.parameters.elements
                        if isinstance(p, nodes.Variable)}

        # Reconstruct full predicate args using canonical arg names
        # The canonical args tell us the full arg list and order
        canonical = _pred_canonical_args.get(pred_name, [])
        if canonical and len(counted_terms) < len(canonical):
            # Build full arg list in canonical order
            full_terms = []
            for arg_name in canonical:
                if arg_name in counted_names:
                    # Find the corresponding counted term
                    for p in node.set_var.parameters.elements:
                        if isinstance(p, nodes.Variable) and p.name == arg_name:
                            full_terms.append(to_egg(p))
                            break
                elif arg_name in _forall_vars:
                    # Forall-bound variable — include in predicate call but not in counted set
                    full_terms.append(Term.Var(arg_name))
                else:
                    # Variable not in counted or forall — treat as free var
                    full_terms.append(Term.Var(arg_name))
        else:
            # Fallback: projection lists all args (original behavior)
            full_terms = counted_terms

        # Build the predicate literal with full args
        pred_atom = Atom.Pred(pred_name, full_terms)
        pred_literal = Literal(pred_atom, True)

        # Only projection vars as counted vars in the set comprehension
        counted_vars = Set[Term](*counted_terms)

        # Single cube containing the predicate literal
        pred_formula = Formula.Lit(pred_literal)
        cubes = Vec[Formula](pred_formula)

        # Build aggregate body
        agg_body = AggBody.set_comprehension(counted_vars, cubes)

        # Strip "#" from op (e.g., "#count" -> "count")
        agg_op = op.lstrip("#") if op.startswith("#") else op

        general_lit = GeneralLit.general_agg(agg_op, agg_body, comp_op, value)
        return Formula.Lit(general_lit)
    else:
        # No parameters - use existing path (Formula.Agg)
        set_var = to_egg(node.set_var)
        return Formula.Agg(op, set_var, comp_op, value)

# --- Individual Converters (for constraint-level rewriting) ---

def convert_rule(stmt: nodes.Rule) -> Rule:
    """Convert a single Rule AST node to egglog Rule."""
    debug_log(f"Converting Rule Head: {stmt.head}")
    head_atom = to_egg(stmt.head)
    debug_log(f"Converted Head: {head_atom}")
    
    debug_log(f"Converting Rule Body ({len(stmt.body)} items)")
    body_vec = Set[Formula](*[to_egg(lit) for lit in stmt.body])
    debug_log(f"Converted Body: {body_vec}")
    
    r = Rule(head_atom, body_vec, stmt.is_choice)
    debug_log(f"Constructed Rule: {r}")
    return r


def _desugar_subset_with_let(stmt: nodes.SetConstraint) -> nodes.FoSet | None:
    """Try to desugar Let + \\subset into FOL implication.

    Pattern:
        Let {A}(x, y) = { (x, y) | (x) in {S}, cond } in (\\subset A {B})
    Becomes:
        \\forall x. \\forall y. (\\impl (\\and S_pred(x) cond) B_pred(x, y))

    Returns the desugared FoSet formula, or None if not applicable.
    """
    if not isinstance(stmt.formula, nodes.SetSubset):
        return None
    subset = stmt.formula
    left_name = subset.left_set.name

    # Find the Let binding for the left set
    let_binding = None
    let_set_var = None
    for let in stmt.let_exprs:
        if let.variable.name == left_name:
            if isinstance(let.value, nodes.SetComprehension):
                let_binding = let.value
                let_set_var = let.variable
                break
    if let_binding is None or let_set_var is None:
        return None

    # Extract comprehension components
    comp = let_binding
    term_vars = comp.term.elements  # The result tuple variables
    domain_vars = comp.domain_term.elements  # Variables bound by domain set
    domain_set = comp.domain_set  # The domain set (e.g., {In_clique})
    condition = comp.condition  # The filtering condition

    # Build domain membership: domain_var ∈ domain_set → pred(domain_var)
    # domain_set is typically a SetVar like SetVar("In_clique")
    domain_membership = None
    if isinstance(domain_set, nodes.SetVar):
        set_name = domain_set.name
        pred_name = set_name[4:] if set_name.startswith("Set_") else set_name
        pred_name = pred_name.lower()
        # Build pred(domain_vars...)
        domain_membership = nodes.PredAtom(
            predicate=nodes.Identifier(pred_name),
            args=list(domain_vars)
        )

    # Build right set membership: term_vars ∈ right_set → pred(term_vars...)
    right_set = subset.right_set
    if isinstance(right_set, nodes.SetVar):
        right_name = right_set.name
        right_pred = right_name[4:] if right_name.startswith("Set_") else right_name
        right_pred = right_pred.lower()
        consequent = nodes.PredAtom(
            predicate=nodes.Identifier(right_pred),
            args=list(term_vars)
        )
    else:
        return None  # Can't handle non-SetVar right sets

    # Build antecedent: domain_membership ∧ condition
    if domain_membership is not None:
        antecedent = nodes.LogicalOp(op='and', operands=[domain_membership, condition])
    else:
        antecedent = condition

    # Build implication: antecedent → consequent
    impl = nodes.LogicalOp(op='impl', operands=[antecedent, consequent])

    # Wrap in ∀ quantifiers for all term variables
    result = impl
    for var in reversed(term_vars):
        if isinstance(var, nodes.Variable):
            result = nodes.QuantifiedFormula(quantifier='forall', variable=var, body=result)

    return result


def convert_constraint(stmt: nodes.SetConstraint) -> Constraint:
    """Convert a single SetConstraint AST node to egglog Constraint."""
    # Try to desugar Let + \subset into FOL implication
    desugared = _desugar_subset_with_let(stmt)
    if desugared is not None:
        debug_log(f"Desugared subset to FOL: {desugared}")
        formula = to_egg(desugared)
        c = Constraint(Vec[LetExpr](), formula)
        return c

    debug_log("Converting SetConstraint LetExprs")
    lets = Vec[LetExpr](*[
        LetExpr(to_egg(let.variable), to_egg(let.value))
        for let in stmt.let_exprs
    ])

    debug_log(f"Converting Formula: {stmt.formula}")
    formula = to_egg(stmt.formula)

    c = Constraint(lets, formula)
    return c


# --- Block / Program Converter ---
# In class AstToEgg:
def convert_block(block: nodes.Block) -> Block:
    egg_rules = Set[Rule]()
    egg_constrs = list[Constraint]()

    debug_log(f"--- Starting Block Conversion ({len(block.statements)} stmts) ---")

    for i, stmt in enumerate(block.statements):
        try:
            debug_log(f"Stmt {i}: {type(stmt).__name__}")
            
            # Use the context manager to indent inner recursive calls
            with TraceContext():
                if isinstance(stmt, nodes.Rule):
                    r = convert_rule(stmt)
                    egg_rules = egg_rules | Set(r)

                elif isinstance(stmt, nodes.SetConstraint):
                    c = convert_constraint(stmt)
                    egg_constrs.append(c)
                    
        except Exception as e:
            print(f"\n!!! ERROR converting statement {i} !!!")
            print(f"Statement Node: {stmt}")
            print(f"Error: {e}")
            raise e # Re-raise to stop execution

    return Block(egg_rules, egg_constrs)

