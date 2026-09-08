"""
Source-level desugaring shared by both front halves
===================================================

Pure functions over the parser's AST (no egglog): ``Let`` + ``\\subset`` into
a first-order implication. Moved here from ``rewrite/converter.py`` so the
direct lowering does not import egglog.
"""

from __future__ import annotations

from ..ast import nodes

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
