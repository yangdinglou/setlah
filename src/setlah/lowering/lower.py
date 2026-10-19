"""
Direct lowering
===============

A syntax-directed lowering of SetLaH blocks to the transpiler's IR
(``IRRule`` / ``IRConstraint``), replacing the egglog front half. No
e-graph, no printed-term round trip, linear in the size of the input up to
the DNF of each constraint (bounded, see ``MAX_DNF_CUBES``).

For each constraint ``phi`` (which must hold) the violation ``not phi`` is put
in negation normal form; each cube of its DNF becomes one integrity
constraint (this reproduces the egglog pipeline's conjunction splitting).
Quantified subformulas inside a cube become auxiliary predicates over their
free variables, one rule per DNF cube of their body; an existential over one
positive literal is inlined with anonymous variables, as egglog's
``exists_to_anonymous`` did. Projected count aggregates that are the whole
matrix of a constraint are handed to the kept renderer in the raw shape it
already handles. Sorts are assumed non-empty (egglog's quantifier
elimination kept ``not dom_S(_)`` cubes for the empty case).
"""

from __future__ import annotations

from typing import Any

from ..ast import nodes
from ..parsing.checker import SemanticChecker, export_entailment_specs, export_pred_arg_types
from .desugar import _desugar_subset_with_let
from ..transpile.ir import IRRule, IRConstraint, LoweredBlock, TranspileError
from ..transpile.rendering import _general_lit_to_body_lit
from . import pyir
from .formula import (
    AggA, And, CompA, Const, Exists, Forall, Lit, NNFBuilder, Or, PredA,
    all_vars, dnf, dnf_size, free_vars, make_and, make_or, negate, negate_comp, var_occurrences,
)


def peel_existentials(f: Any) -> Any:
    """Drop existential binders that can be free in an integrity constraint.

    The violation of a constraint is existentially closed, so an outermost
    ``exists`` is redundant, and so is one under a disjunction or inside a
    conjunction whose bound names occur nowhere else in that conjunction (a
    clash would identify two different variables, so those stay bound and
    become auxiliaries).
    """
    if isinstance(f, Exists):
        return peel_existentials(f.body)
    if isinstance(f, Or):
        return make_or(peel_existentials(x) for x in f.items)
    if isinstance(f, And):
        items = list(f.items)
        out: list = []
        for i, x in enumerate(items):
            if isinstance(x, Exists):
                others: set = set()
                for j, y in enumerate(items):
                    if j != i:
                        others.update(all_vars(y))
                if not (set(x.vars) & others):
                    out.append(peel_existentials(x.body))
                    continue
            out.append(x)
        return make_and(out)
    return f


class DirectLowerer:
    """Drop-in for ``rewrite.rw.Rewriter``: ``rewrite_program`` sets the same
    attributes on the program (``blocks``, ``_aux_rules``, ``_aux_next``,
    ``_pred_arg_types``, ``_entailment_specs``)."""

    #: Above this many cubes, conjunctions under a disjunction become
    #: auxiliary predicates instead of being distributed.
    MAX_DNF_CUBES = 32

    def __init__(self, verbose: bool = False, *, entailment_elim: str = "asp", enable_cost_conversion: bool = False, split_width: int = 0):
        self.verbose = verbose
        #: rule decomposition: an integrity constraint whose cube has more than this many variables is
        #: split along a tree decomposition of its variable graph (lpopt's construction); 0 disables it
        self.split_width = split_width
        self.split_count = 0
        self.entailment_elim = entailment_elim
        self.checker: SemanticChecker | None = None
        self.builder: NNFBuilder | None = None
        self.aux_rules: list[str] = []
        self._next_aux = 0
        self._var_types: dict[str, str] = {}

    # --- program / block -----------------------------------------------------

    def rewrite_program(self, program: nodes.Program, convert_only: bool = False) -> nodes.Program:
        self.checker = SemanticChecker(verbose=self.verbose)
        self.checker.check_program(program)
        canonical = {
            name: info.canonical_args
            for name, info in self.checker.predicates.items()
            if info.canonical_args
        }
        self.builder = NNFBuilder(canonical)

        if self.entailment_elim in ("asp", "both"):
            program._entailment_specs = export_entailment_specs(self.checker)  # type: ignore[attr-defined]
        elif hasattr(program, "_entailment_specs"):
            delattr(program, "_entailment_specs")
        program._pred_arg_types = export_pred_arg_types(self.checker)  # type: ignore[attr-defined]

        self.aux_rules = []
        self._next_aux = 0
        program.blocks = [self.lower_block(block) for block in program.blocks]
        program._aux_next = self._next_aux  # type: ignore[attr-defined]
        if self.aux_rules:
            program._aux_rules = self.aux_rules  # type: ignore[attr-defined]
        if self.verbose:
            print(f"Direct lowering: {len(self.aux_rules)} aux rules")
            for r in self.aux_rules:
                print(f"  {r}")
        return program

    def lower_block(self, block: nodes.Block) -> LoweredBlock:
        rules: list[IRRule] = []
        constraints: list[IRConstraint] = []
        for stmt in block.statements:
            if isinstance(stmt, nodes.Rule):
                rules.append(self.lower_rule(stmt))
            elif isinstance(stmt, nodes.SetConstraint):
                constraints.extend(self.lower_constraint(stmt))
            else:
                raise TranspileError(f"Unsupported statement: {stmt!r}")
        return LoweredBlock(rules=rules, constraints=constraints)

    # --- terms, atoms, literals ---------------------------------------------

    def term(self, t: Any) -> Any:
        if isinstance(t, nodes.Variable):
            return pyir.term_var(t.name)
        if isinstance(t, nodes.Constant):
            return pyir.term_int(t.value)
        if isinstance(t, nodes.Identifier):
            return pyir.term_symbol(t.name)
        if isinstance(t, nodes.BinaryExpr):
            return pyir.term_binexpr(t.op, self.term(t.left), self.term(t.right))
        raise TranspileError(f"Unsupported term: {t!r}")

    def atom(self, a: Any, anon: frozenset = frozenset()) -> Any:
        if isinstance(a, PredA):
            terms = [
                pyir.term_anon() if isinstance(t, nodes.Variable) and t.name in anon else self.term(t)
                for t in a.args
            ]
            return pyir.atom_pred(a.name, terms)
        if isinstance(a, CompA):
            return pyir.atom_comp(a.op, self.term(a.left), self.term(a.right))
        raise TranspileError(f"Unsupported atom: {a!r}")

    def literal(self, a: Any, positive: bool, anon: frozenset = frozenset()) -> Any:
        """A ``GeneralLit`` node for an atom with a sign."""
        if isinstance(a, AggA):
            comp = a.comp if positive else negate_comp(a.comp)
            return self.aggregate(a, comp)
        return pyir.general_lit(pyir.literal(self.atom(a, anon), positive))

    def aggregate(self, a: AggA, comp: str) -> Any:
        cube = pyir.formula_lit(pyir.general_lit(pyir.literal(self.atom(a.pred), True)))
        body = pyir.agg_body([self.term(c) for c in a.counted], [cube])
        return pyir.general_agg(a.op, body, comp, self.term(a.value))

    # --- rules ----------------------------------------------------------------

    def lower_rule(self, stmt: nodes.Rule) -> IRRule:
        head = pyir.atom_pred(stmt.head.predicate.name, [self.term(t) for t in stmt.head.args])
        body: list[Any] = []
        for lit in stmt.body:
            if isinstance(lit, nodes.PredAtom):
                body.append(pyir.formula_lit(self.literal(PredA(lit.predicate.name, tuple(lit.args)), True)))
            elif isinstance(lit, nodes.Comparison):
                body.append(pyir.formula_lit(self.literal(CompA(lit.op, lit.left, lit.right), True)))
            else:
                raise TranspileError(f"Unsupported rule body literal: {lit!r}")
        return IRRule(head=head, body=body, is_choice=bool(stmt.is_choice))

    # --- constraints ----------------------------------------------------------

    def lower_constraint(self, stmt: nodes.SetConstraint) -> list[IRConstraint]:
        assert self.builder is not None
        formula = stmt.formula
        desugared = _desugar_subset_with_let(stmt)
        if desugared is not None:
            formula = desugared
        elif stmt.let_exprs:
            raise TranspileError(
                "The direct lowering supports Let only in the form Let {A}(...) = {...} in (\\subset A B)"
            )

        if isinstance(formula, nodes.SetPartition):
            body = pyir.formula_partition(
                pyir.term_var(formula.target_set.name),
                [pyir.term_var(p.name) for p in formula.parts],
            )
            return [IRConstraint(kind="raw", vars=None, lits=None, body=body)]

        if isinstance(formula, nodes.Aggregation) and not formula.set_var.parameters:
            body = pyir.formula_agg(
                formula.op,
                pyir.setexpr_setvar(formula.set_var.name, []),
                formula.comp_op,
                self.term(formula.value),
            )
            return [IRConstraint(kind="raw", vars=None, lits=None, body=body)]

        raw_agg = self._aggregate_matrix(formula)
        if raw_agg is not None:
            return [raw_agg]

        violation = self.builder.build(formula, positive=False)
        self._var_types = self._collect_var_types(violation)
        violation = peel_existentials(violation)
        violation = self._bound(violation)
        out: list[IRConstraint] = []
        for cube in dnf(violation):
            if self.split_width > 0:
                cube = self._split_cube(cube)
            lits = [self.item(it) for it in cube]
            if not lits:
                # the constraint is unsatisfiable: an always-violated integrity constraint
                lits = [pyir.general_lit(pyir.literal(pyir.atom_comp("==", pyir.term_int(1), pyir.term_int(1)), True))]
            vars_ = free_vars(make_and(cube))
            out.append(IRConstraint(
                kind="integrity",
                vars=[pyir.term_var(v) for v in vars_],
                lits=lits,
                body=None,
            ))
        return out

    def _aggregate_matrix(self, formula: nodes.FoSet) -> IRConstraint | None:
        """A projected count aggregate as the whole matrix under universals, optionally
        guarded by an implication from positive atoms, in the raw shape the kept
        renderer (``_try_general_agg_raw_to_asp``) handles, including its domain guards."""
        assert self.builder is not None
        quantified: list[str] = []
        cur = formula
        while isinstance(cur, nodes.QuantifiedFormula) and cur.quantifier in ("forall", "∀"):
            quantified.append(cur.variable.name)
            cur = cur.body

        guards: list[nodes.PredAtom] = []
        agg: nodes.Aggregation | None = None
        if isinstance(cur, nodes.Aggregation) and cur.set_var.parameters:
            agg = cur
        elif (
            isinstance(cur, nodes.LogicalOp) and cur.op == "impl" and len(cur.operands) == 2
            and isinstance(cur.operands[1], nodes.Aggregation) and cur.operands[1].set_var.parameters
        ):
            ante, agg = cur.operands
            if isinstance(ante, nodes.PredAtom):
                guards = [ante]
            elif isinstance(ante, nodes.LogicalOp) and ante.op == "and" and all(
                isinstance(x, nodes.PredAtom) for x in ante.operands
            ):
                guards = list(ante.operands)
            else:
                return None
        if agg is None:
            return None

        inner = pyir.formula_lit(self.aggregate(self.builder.aggregate(agg), agg.comp_op))
        if guards:
            acc = None
            for g in guards:
                lit = pyir.formula_lit(self.literal(PredA(g.predicate.name, tuple(g.args)), False))
                acc = lit if acc is None else pyir.formula_or(acc, lit)
            inner = pyir.formula_or(acc, inner)
        body = inner
        for v in reversed(quantified):
            body = pyir.formula_forall(pyir.term_var(v), body)
        return IRConstraint(kind="raw", vars=None, lits=None, body=body)

    # --- cube items -----------------------------------------------------------

    def item(self, it: Any) -> Any:
        """A ``GeneralLit`` node for one item of a cube."""
        if isinstance(it, Lit):
            return self.literal(it.atom, it.positive)
        if isinstance(it, Exists):
            anon = self._inlinable(it.vars, it.body)
            if anon is not None:
                return self.literal(it.body.atom, True, anon)
            name, fv = self.make_aux(it.vars, it.body)
            return pyir.general_lit(pyir.literal(pyir.atom_pred(name, [pyir.term_var(v) for v in fv]), True))
        if isinstance(it, Forall):
            neg = negate(it.body)          # forall vs. body == not exists vs. not body
            anon = self._inlinable(it.vars, neg)
            if anon is not None:
                return self.literal(neg.atom, False, anon)
            name, fv = self.make_aux(it.vars, neg)
            return pyir.general_lit(pyir.literal(pyir.atom_pred(name, [pyir.term_var(v) for v in fv]), False))
        raise TranspileError(f"Unexpected cube item: {it!r}")

    @staticmethod
    def _inlinable(vars_: tuple, body: Any) -> frozenset | None:
        """``exists vs. p(..)`` with one positive predicate literal in which every
        bound variable occurs exactly once as a plain argument: those variables
        become anonymous. Returns the set to anonymise, or None."""
        if not (isinstance(body, Lit) and body.positive and isinstance(body.atom, PredA)):
            return None
        plain = {t.name for t in body.atom.args if isinstance(t, nodes.Variable)}
        for v in vars_:
            if v not in plain or var_occurrences(body, v) != 1:
                return None
        return frozenset(vars_)

    def make_aux(self, vars_: tuple, body: Any) -> tuple[str, list[str]]:
        """Auxiliary predicate for ``exists vars. body``: one rule per DNF cube of
        the body, over the free variables of the subformula.

        A rule's variables must be bound by a positive predicate literal in
        its body; a head variable or a bound variable that a cube mentions only
        under negation, in a comparison or not at all gets a domain guard from
        the types the checker knows (the safety pass would infer the same
        guard where it can, but through auxiliary predicates that inference is
        order-dependent, B6)."""
        fv = free_vars(Exists(tuple(vars_), body))
        name = f"__aux_{self._next_aux}"
        self._next_aux += 1
        head = f"{name}({', '.join(fv)})" if fv else name
        for cube in dnf(self._bound(body)):
            if self.split_width > 0:
                cube = self._split_cube(cube, keep=frozenset(fv))
            lits = [_general_lit_to_body_lit(self.item(it)) for it in cube]
            bound = self._positively_bound(cube)
            guards = []
            for v in list(fv) + [v for v in vars_ if v not in fv]:
                if v not in bound and v in self._var_types:
                    guards.append(f"dom_{self._var_types[v]}({v})")
            lits = guards + lits
            self.aux_rules.append(f"{head} :- {', '.join(lits) if lits else '#true'}.")
        return name, fv

    # --- rule decomposition ---------------------------------------------------

    def _split_cube(self, cube: list, keep: frozenset = frozenset()) -> list:
        """Rule decomposition of one integrity-constraint cube (``:- item_1, ..., item_n``).

        The cube's variable graph joins two variables that share an item. A
        min-fill elimination order gives a tree decomposition; the bag of each
        eliminated variable takes the items whose variables it covers, becomes
        a rule ``__aux_k(separator) :- guards, items, child temporaries`` over
        its separator (the eliminated variable's neighbours), and the root bag
        stays the constraint. Grounding then costs about d^(treewidth+1) per
        rule instead of d^(variables) (Bichler, Morak, Woltran, lpopt). The
        program is a conservative extension: the temporaries are defined
        positively, so answer sets projected to the original signature are
        unchanged. Cubes with at most ``split_width`` variables are returned
        as they are. Variables in ``keep`` (the head variables of a rule whose
        body the cube is) are never eliminated, so they stay in the root bag
        and the head remains bound by the root's body."""
        items = list(cube)
        var_of = [set(free_vars(it)) for it in items]
        allv = set().union(*var_of) if var_of else set()
        if len(allv) <= self.split_width or len(items) < 2:
            return items
        adj: dict = {v: set() for v in allv}
        for vs in var_of:
            for x in vs:
                adj[x] |= vs - {x}
        g = {v: set(n) for v, n in adj.items()}; order: list = []
        # kept variables (a rule's head) are never eliminated: they form the root bag, so the head stays
        # bound by the root's own body and no temporary projects a head variable away
        while any(v not in keep for v in g):
            def fill(v: str) -> int:
                nb = list(g[v]); return sum(1 for i, x in enumerate(nb) for y in nb[i + 1:] if y not in g[x])
            cands = [v for v in g if v not in keep]
            v = min(sorted(cands), key=lambda v: (fill(v), len(g[v])))
            nb = set(g[v]); order.append((v, nb))
            for x in nb:
                g[x] |= nb - {x}; g[x].discard(v)
            del g[v]
        root_size = len(set(g)) + 0   # the kept variables left in the graph
        if not order or max([len(nb) + 1 for _, nb in order] + [root_size]) >= len(allv):
            return items   # no decomposition narrows it
        remaining = list(range(len(items))); temps: list = []   # (predicate name, separator vars)
        for i, (v, nb) in enumerate(order):
            bag = nb | {v}
            mine = [k for k in remaining if var_of[k] <= bag]; remaining = [k for k in remaining if k not in mine]
            kids = [t for t in temps if set(t[1]) <= bag]; temps = [t for t in temps if t not in kids]
            if (i == len(order) - 1 and not keep) or (not remaining and not temps and not mine and not kids):
                remaining_items = [items[k] for k in remaining] + [items[k] for k in mine]
                return remaining_items + [Lit(PredA(n, tuple(nodes.Variable(name=x) for x in sv)), True) for n, sv in temps + kids]
            if not mine and not kids:
                continue
            sep = sorted(nb)
            body_items = [items[k] for k in mine]
            name = f"__aux_{self._next_aux}"; self._next_aux += 1; self.split_count += 1
            lits = [_general_lit_to_body_lit(self.item(it)) for it in body_items]
            lits += [f"{n}({', '.join(sv)})" if sv else n for n, sv in kids]
            bound = self._positively_bound(body_items) | {x for _, sv in kids for x in sv}
            # every variable of the bag must be bound positively in its rule: the separator (head) and any
            # variable that the bag mentions only under negation or in a comparison
            bag_vars = set(sep) | set().union(*[var_of[k] for k in mine]) if mine else set(sep)
            guards = [f"dom_{self._var_types[x]}({x})" for x in sorted(bag_vars) if x not in bound and x in self._var_types]
            head = f"{name}({', '.join(sep)})" if sep else name
            self.aux_rules.append(f"{head} :- {', '.join(guards + lits) if (guards or lits) else '#true'}.")
            temps.append((name, sep))
        return [items[k] for k in remaining] + [Lit(PredA(n, tuple(nodes.Variable(name=x) for x in sv)), True) for n, sv in temps]

    @staticmethod
    def _positively_bound(cube: list) -> set:
        """Variables that are plain arguments of a positive predicate literal in the cube."""
        out: set = set()
        for it in cube:
            if isinstance(it, Lit) and it.positive and isinstance(it.atom, PredA):
                for t in it.atom.args:
                    if isinstance(t, nodes.Variable):
                        out.add(t.name)
        return out

    def _collect_var_types(self, f: Any) -> dict[str, str]:
        """Variable name -> domain name, from every predicate literal of ``f``."""
        assert self.checker is not None
        types: dict[str, str] = {}

        def walk(g: Any) -> None:
            if isinstance(g, Lit):
                atoms = [g.atom] if isinstance(g.atom, PredA) else ([g.atom.pred] if isinstance(g.atom, AggA) else [])
                for a in atoms:
                    info = self.checker.predicates.get(a.name)
                    if info is None:
                        continue
                    for t, ty in zip(a.args, info.arg_types):
                        if isinstance(t, nodes.Variable) and ty not in ("UNKNOWN", "CONST") and t.name not in types:
                            types[t.name] = ty
            elif isinstance(g, (And, Or)):
                for x in g.items:
                    walk(x)
            elif isinstance(g, (Exists, Forall)):
                walk(g.body)

        walk(f)
        return types

    # --- DNF bounding -----------------------------------------------------------

    def _bound(self, f: Any) -> Any:
        """Keep the DNF of ``f`` under ``MAX_DNF_CUBES`` cubes by turning
        non-atomic children into auxiliary predicates where needed."""
        if dnf_size(f) <= self.MAX_DNF_CUBES:
            return f
        if isinstance(f, And):
            items: list = []
            product = 1
            for x in f.items:
                bx = self._bound(x)
                n = dnf_size(bx)
                if n > 1 and product * n > self.MAX_DNF_CUBES:
                    bx = self._aux_item(bx)
                    n = 1
                product *= n
                items.append(bx)
            return make_and(items)
        if isinstance(f, Or):
            items = [self._bound(x) for x in f.items]
            if sum(dnf_size(x) for x in items) > self.MAX_DNF_CUBES:
                items = [self._aux_item(x) if dnf_size(x) > 1 else x for x in items]
            return make_or(items)
        return f

    def _aux_item(self, g: Any) -> Lit:
        name, fv = self.make_aux((), g)
        return Lit(PredA(name, tuple(nodes.Variable(name=v) for v in fv)), True)
