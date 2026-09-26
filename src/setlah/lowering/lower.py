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

import os
import re

from typing import Any

from ..ast import nodes
from ..parsing.checker import SemanticChecker, export_entailment_specs, export_pred_arg_types
from .desugar import _desugar_subset_with_let
from ..transpile.ir import IRRule, IRConstraint, LoweredBlock, TranspileError
from ..transpile.rendering import _general_lit_to_body_lit
from . import pyir
from .order import OrderLowering, NeedsOther, _Conj
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

    def __init__(self, verbose: bool = False, *, entailment_elim: str = "asp", enable_cost_conversion: bool = False, order_lowering: str | None = None, acyclic_inlining: str | None = None, acyclic_lowering: str | None = None, acyclic_range: int | None = None, extensions: tuple[str, ...] | None = None):
        self.verbose = verbose
        self.order_modes = self._parse_order_modes(order_lowering)
        self.acyclic_inlining = self._parse_acyclic_inlining(acyclic_inlining)
        self.acyclic_lowering = self._parse_modes(acyclic_lowering, "SETLAH_ACYCLIC_LOWERING", "edge", ("edge", "closure", "positions"), "acyclic lowering")
        self.acyclic_range = acyclic_range if acyclic_range is not None else int(os.environ.get("SETLAH_ACYCLIC_RANGE", 1 << 24))
        self.extensions = tuple(extensions) if extensions is not None else tuple(x for x in os.environ.get("SETLAH_EXT", "").split(",") if x)
        self.entailment_elim = entailment_elim
        self.checker: SemanticChecker | None = None
        self.builder: NNFBuilder | None = None
        self.aux_rules: list[str] = []
        self._next_aux = 0
        self._var_types: dict[str, str] = {}
        self.order: OrderLowering | None = None
        self.extra_rules: list[str] = []

    @staticmethod
    def _parse_order_modes(spec: str | None) -> dict[str, str]:
        """``dl`` / ``rel`` for every order sort, or ``X=rel,C=dl`` per sort (``*`` for the rest)."""
        spec = spec or os.environ.get("SETLAH_ORDER_LOWERING") or "auto"
        modes: dict[str, str] = {}
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            if "=" in part:
                sort, mode = part.split("=", 1)
                modes[sort.strip()] = mode.strip()
            else:
                modes["*"] = part
        for mode in modes.values():
            if mode not in ("auto", "enum", "rel", "dl"):
                raise TranspileError(f"Unknown order-sort lowering {mode!r} (auto, enum, rel or dl)")
        return modes

    @staticmethod
    def _parse_modes(spec: str | None, env: str, default: str, allowed: tuple, what: str) -> dict[str, str]:
        """``mode`` for every relation, or ``r=mode,*=mode`` per relation; the environment
        variable ``env`` supplies the default."""
        spec = spec or os.environ.get(env) or default
        modes: dict[str, str] = {}
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            if "=" in part:
                rel, mode = part.split("=", 1)
                modes[rel.strip()] = mode.strip()
            else:
                modes["*"] = part
        for mode in modes.values():
            if mode not in allowed:
                raise TranspileError(f"Unknown {what} mode {mode!r} ({', '.join(allowed)})")
        return modes

    def _acyclic_mode(self, name: str) -> str:
        """``edge`` (clingo's propagator), ``closure`` (the transitive closure as rules with
        an irreflexivity constraint) or ``positions`` (a total function into an order sort
        with ``r(a, b) -> pos(a) < pos(b)``, the SMT baselines' idiom) for ``(\\acyclic name)``."""
        return self.acyclic_lowering.get(name, self.acyclic_lowering.get("*", "edge"))

    def _acyclic_positions(self, program: nodes.Program) -> bool:
        """Rewrite every ``(\\acyclic r)`` selected for the ``positions`` lowering into an
        order sort ``Pos_r``, a function ``pos_r`` from the node tuples into it, and the
        constraint ``r(a, b) -> pos_r(a) < pos_r(b)``; the order sort is then lowered like
        any other (difference logic when the extension is enabled, else enumeration over
        ``acyclic_range``). Returns whether the program changed."""
        assert self.checker is not None
        from ..parsing.parser import Parser
        todo = [(b, i) for b, block in enumerate(program.blocks) for i, st in enumerate(block.statements)
                if isinstance(st, nodes.SetConstraint) and isinstance(st.formula, nodes.Acyclic) and self._acyclic_mode(st.formula.predicate.name) == "positions"]
        if not todo:
            return False
        decls, cons = [], []
        for b, i in todo:
            name = program.blocks[b].statements[i].formula.predicate.name
            info = self.checker.predicates[name]; k = info.arity // 2
            sorts = [str(t) for t in info.arg_types[:k]]
            if any(not re.match(r"^[A-Z]", t) for t in sorts):
                raise TranspileError(f"(\\acyclic {name}) as positions: the node sorts must be declared sorts, got {sorts}")
            P, f = f"Pos_{name}", f"pos_{name}"
            xs = [f"X{j}" for j in range(k)]; ys = [f"Y{j}" for j in range(k)]
            decls.append(f"OrdDOM {P}: 0..{self.acyclic_range}.\nFun {f}: ({', '.join(sorts)}) -> {P}.")
            cons.append(f"\\forall {', '.join(xs + ys)}, P1, P2. (\\impl (\\and {name}({', '.join(xs + ys)}) {f}({', '.join(xs)}, P1) {f}({', '.join(ys)}, P2)) (< P1 P2)).")
            if P not in self.order_modes:
                self.order_modes[P] = "dl" if "dl" in self.extensions else "enum"
        parsed = Parser().parse("\n".join(decls) + "\n[\n" + "\n".join(cons) + "\n]\n")
        program.domains = list(program.domains) + list(parsed.domains)
        for (b, i), st in zip(todo, parsed.blocks[0].statements):
            program.blocks[b].statements[i] = st
        return True

    @staticmethod
    def _parse_acyclic_inlining(spec: str | None) -> dict[str, str]:
        """``auto`` (default: inline a relation's defining rules into ``#edge`` only when
        they project nothing away), ``all`` (inline every eligible rule) or ``none``, for
        every acyclic relation or per relation (``hbc=all,*=auto``); env
        ``SETLAH_ACYCLIC_INLINING``."""
        spec = spec or os.environ.get("SETLAH_ACYCLIC_INLINING") or "auto"
        modes: dict[str, str] = {}
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            if "=" in part:
                rel, mode = part.split("=", 1)
                modes[rel.strip()] = mode.strip()
            else:
                modes["*"] = part
        for mode in modes.values():
            if mode not in ("auto", "all", "none"):
                raise TranspileError(f"Unknown acyclic inlining mode {mode!r} (auto, all or none)")
        return modes

    # --- program / block -----------------------------------------------------

    def rewrite_program(self, program: nodes.Program, convert_only: bool = False) -> nodes.Program:
        self.checker = SemanticChecker(verbose=self.verbose)
        self.checker.check_program(program)
        if self._acyclic_positions(program):
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
        self.order = None
        self.extra_rules = []
        checker = self.checker
        if getattr(checker, "functions", None):
            # The selection rule (docs/order-sorts.md, T6): a sort is lowered relationally
            # when all its comparisons are between two values without offsets; a sort that
            # needs an offset, a constant or a distance goes to dl when that extension is
            # enabled and to enumeration otherwise; a sort whose values occur outside
            # comparisons goes to enumeration. "auto" tries the relation first and retries
            # a sort with the lowering the failure names.
            modes = {s_: self.order_modes.get(s_, self.order_modes.get("*", "auto")) for s_ in checker.order_sorts}
            trial = {s_: ("rel" if m == "auto" else m) for s_, m in modes.items()}
            blocks = list(program.blocks)
            while True:
                self.aux_rules = []
                self._next_aux = 0
                self.extra_rules = []
                self.order = OrderLowering(dict(checker.functions), dict(checker.order_sorts), lambda v: None, trial, self.extensions,
                                           self._deterministic_predicates(blocks), self._may_definitions(blocks))
                try:
                    lowered = [self.lower_block(block) for block in blocks]
                    break
                except NeedsOther as e:
                    if modes.get(e.sort) != "auto":
                        raise
                    want = e.want
                    if want == "dl" and "dl" not in self.extensions:
                        want = "enum"
                    if trial[e.sort] == want:
                        raise
                    trial[e.sort] = want   # rel -> dl -> enum, or rel -> enum: each retry strictly weaker
            program.blocks = lowered
            program._order_modes = dict(trial)  # type: ignore[attr-defined]
        else:
            program.blocks = [self.lower_block(block) for block in program.blocks]
        extra = (self.order.finalize() if self.order is not None else []) + self.extra_rules
        if extra:
            program._theory_rules = extra  # type: ignore[attr-defined]
        elif hasattr(program, "_theory_rules"):
            delattr(program, "_theory_rules")
        projections = self.domain_projections(program)
        if projections and program.blocks:
            first = program.blocks[0]
            program.blocks[0] = LoweredBlock(rules=projections + first.rules, constraints=first.constraints)
        program._aux_next = self._next_aux  # type: ignore[attr-defined]
        if self.aux_rules:
            program._aux_rules = self.aux_rules  # type: ignore[attr-defined]
        if self.verbose:
            print(f"Direct lowering: {len(self.aux_rules)} aux rules")
            for r in self.aux_rules:
                print(f"  {r}")
        return program

    def domain_projections(self, program: nodes.Program) -> list[IRRule]:
        """``dom_S(X) :- p(.., X, ..)`` for every external predicate argument of an
        ``ExtDOM`` sort ``S``.

        The compiler guards variables with ``dom_S`` (auxiliary heads here,
        integrity constraints in the safety pass, aggregate outer variables in
        the renderer), and ``dom_S`` is supplied by the input for ``ExtDOM``
        sorts. Inputs that give the sort's elements only through the
        predicates over it left ``dom_S`` undefined and every guarded rule
        dead (docs/known-issues.md, B14). The projections define ``dom_S`` as
        the sort's active domain; with well-typed ``dom_S`` facts they add
        nothing. The renderer drops the projections of a sort whose ``dom_S``
        no other rule mentions (``transpile_program_to_asp``): over a large
        fact table they are pure grounding cost (deadlock traces of 435,000
        events: 31 projections, 11 s).
        """
        assert self.checker is not None
        ext_sorts = {d.var.name for d in program.domains if isinstance(d, nodes.ExtDOM)}
        rules: list[IRRule] = []
        sorts: set[str] = set()
        for decl in program.domains:
            if not isinstance(decl, nodes.ExtPred):
                continue
            info = self.checker.predicates.get(decl.name.name)
            if info is None:
                continue
            for i, sort in enumerate(info.arg_types):
                if sort not in ext_sorts:
                    continue
                sorts.add(sort)
                args = [pyir.term_var("X") if j == i else pyir.term_anon() for j in range(info.arity)]
                head = pyir.atom_pred(f"dom_{sort}", [pyir.term_var("X")])
                body = pyir.formula_lit(pyir.general_lit(pyir.literal(pyir.atom_pred(info.name, args), True)))
                rules.append(IRRule(head=head, body=[body], is_choice=False))
        program._projection_sorts = sorts  # type: ignore[attr-defined]
        return rules

    def lower_block(self, block: nodes.Block) -> LoweredBlock:
        rules: list[IRRule] = []
        constraints: list[IRConstraint] = []
        self._inline_edges = self._acyclic_inlining(block)
        for stmt in block.statements:
            if isinstance(stmt, nodes.Rule):
                if stmt.head.predicate.name in self._inline_edges:
                    continue    # emitted as #edge statements by the (\acyclic ...) constraint
                rules.extend(self.lower_rules(stmt))
            elif isinstance(stmt, nodes.SetConstraint):
                constraints.extend(self.lower_constraint(stmt))
            else:
                raise TranspileError(f"Unsupported statement: {stmt!r}")
        return LoweredBlock(rules=rules, constraints=constraints)

    _inline_edges: dict = {}

    @classmethod
    def _collect_term_vars(cls, t: Any, out: set) -> None:
        if isinstance(t, nodes.Variable): out.add(t.name)
        elif isinstance(t, nodes.BinaryExpr): cls._collect_term_vars(t.left, out); cls._collect_term_vars(t.right, out)

    def _deterministic_predicates(self, blocks: list) -> set[str]:
        """External predicates and those derived from them by non-choice rules only
        (a fixpoint from below); a predicate with a choice rule, or a rule whose body
        mentions a non-deterministic predicate, is not deterministic. The reified
        comparison Booleans of the dl extension are guarded by deterministic literals
        only (docs/order-sorts.md Section 7)."""
        assert self.checker is not None
        det = {n for n, i in self.checker.predicates.items() if i.is_external} | {n for n in self.checker.predicates if n.startswith("dom_")}
        rules: dict = {}
        for block in blocks:
            for st in getattr(block, "statements", []):
                if isinstance(st, nodes.Rule):
                    rules.setdefault(st.head.predicate.name, []).append(st)
        changed = True
        while changed:
            changed = False
            for name, sts in rules.items():
                if name in det:
                    continue
                if all(not st.is_choice and all(not isinstance(l, nodes.PredAtom) or l.predicate.name in det for l in st.body) for st in sts):
                    det.add(name); changed = True
        return det

    def _may_definitions(self, blocks: list) -> dict:
        """For every predicate defined by rules (choice or not) whose truth depends on a
        choice, a deterministic over-approximation ``__may_p``: one rule per defining
        rule, keeping the deterministic body literals, replacing a non-deterministic
        defined literal by its own ``__may_``, dropping comparisons, and guarding a head
        variable bound by nothing else with its domain atom. ``p`` is contained in
        ``__may_p`` in every answer set, so ``__may_p`` may guard the reified comparison
        Booleans of the dl extension where ``p`` itself, being chosen, may not (Cobra's
        ``edge`` under the positions lowering: one Boolean per candidate edge, as the
        SMT baseline has, instead of one per pair of transactions)."""
        assert self.checker is not None
        det = self._deterministic_predicates(blocks)
        rules: dict = {}
        for block in blocks:
            for st in getattr(block, "statements", []):
                if isinstance(st, nodes.Rule):
                    rules.setdefault(st.head.predicate.name, []).append(st)
        def text(atom):
            def t(a):
                if isinstance(a, nodes.Variable): return a.name
                if isinstance(a, nodes.Constant): return str(a.value)
                if isinstance(a, nodes.Identifier): return a.name
                return None
            parts = [t(a) for a in atom.args]
            return None if any(x is None for x in parts) else f"{atom.predicate.name}({', '.join(parts)})" if parts else atom.predicate.name
        out: dict = {}
        for name, sts in rules.items():
            if name in det:
                continue
            defs = []
            for st in sts:
                head = text(st.head)
                if head is None:
                    defs = None; break
                head_vars = [a.name for a in st.head.args if isinstance(a, nodes.Variable) and a.name != "_"]
                body, bound = [], set()
                for l in st.body:
                    if not isinstance(l, nodes.PredAtom):
                        continue
                    lt = text(l)
                    if lt is None:
                        continue
                    if l.predicate.name not in det and l.predicate.name in rules:
                        lt = "__may_" + lt
                    elif l.predicate.name not in det:
                        continue   # neither deterministic nor defined here: no bound available from it
                    body.append(lt); bound |= {a.name for a in l.args if isinstance(a, nodes.Variable)}
                info = self.checker.predicates.get(name)
                for i, a in enumerate(st.head.args):
                    if isinstance(a, nodes.Variable) and a.name != "_" and a.name not in bound:
                        sort = info.arg_types[i] if info and i < len(info.arg_types) else None
                        if not sort or str(sort) == "UNKNOWN":
                            defs = None; break
                        body.append(f"dom_{sort}({a.name})")
                if defs is None:
                    break
                defs.append((head, ", ".join(body)))
            if defs:
                out[name] = (any(st.is_choice for st in sts), defs)
        return out

    def _acyclic_inlining(self, block: nodes.Block) -> dict:
        """Relations under (\\acyclic r) that are defined only by deterministic rules
        with predicate-atom and comparison bodies in this block and occur nowhere
        else: name -> [(head argument texts, body text)] for inlining into #edge."""
        acyc = {st.formula.predicate.name for st in block.statements if isinstance(st, nodes.SetConstraint) and isinstance(st.formula, nodes.Acyclic) and self._acyclic_mode(st.formula.predicate.name) == "edge"}
        if not acyc:
            return {}
        used: dict = {n: 0 for n in acyc}
        def count(node):
            if isinstance(node, nodes.PredAtom):
                if node.predicate.name in used: used[node.predicate.name] += 1
            elif isinstance(node, nodes.LogicalOp):
                for x in node.operands: count(x)
            elif isinstance(node, nodes.QuantifiedFormula): count(node.body)
            elif isinstance(node, nodes.SetComprehension): count(node.condition)
        defs: dict = {n: [] for n in acyc}
        for st in block.statements:
            if isinstance(st, nodes.Rule):
                for lit in st.body:
                    count(lit) if isinstance(lit, nodes.PredAtom) else None
                if st.head.predicate.name in acyc:
                    # inlinable only when the rule projects nothing away: a body variable
                    # absent from the head would turn one edge into one per binding of it,
                    # and the propagator would see the duplicates the relation deduplicated
                    # (measured on Cobra: 3.5 s against 1.9 s)
                    head_vars = {a.name for a in st.head.args if isinstance(a, nodes.Variable)}
                    body_vars: set = set()
                    for l in st.body:
                        for t in (l.args if isinstance(l, nodes.PredAtom) else [l.left, l.right]):
                            self._collect_term_vars(t, body_vars)
                    mode = self.acyclic_inlining.get(st.head.predicate.name, self.acyclic_inlining.get("*", "auto"))
                    projecting = not body_vars <= head_vars
                    if st.is_choice or not st.body or not all(isinstance(l, (nodes.PredAtom, nodes.Comparison)) for l in st.body) or mode == "none" or (mode == "auto" and projecting):
                        used[st.head.predicate.name] += 10 ** 6   # not inlinable
                    else:
                        defs[st.head.predicate.name].append(st)
            elif isinstance(st, nodes.SetConstraint) and not isinstance(st.formula, nodes.Acyclic):
                count(st.formula)
                for le in st.let_exprs: count(le.value) if isinstance(le.value, nodes.SetComprehension) else None
        def text(t):
            if isinstance(t, nodes.Variable): return t.name
            if isinstance(t, nodes.Constant): return str(t.value)
            if isinstance(t, nodes.Identifier): return t.name
            if isinstance(t, nodes.BinaryExpr): return f"({text(t.left)} {t.op} {text(t.right)})"
            raise TranspileError(f"Unsupported term in an acyclic relation: {t!r}")
        out: dict = {}
        for n in acyc:
            if used[n] == 0 and defs[n] and self.checker is not None and n in self.checker.predicates and not self.checker.predicates[n].is_external:
                items = []
                for st in defs[n]:
                    body = []
                    for lit in st.body:
                        if isinstance(lit, nodes.PredAtom): body.append(f"{lit.predicate.name}({', '.join(text(a) for a in lit.args)})")
                        else: body.append(f"{text(lit.left)} {lit.op} {text(lit.right)}")
                    items.append(([text(a) for a in st.head.args], ", ".join(body)))
                out[n] = items
        return out

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

    def lower_rules(self, stmt: nodes.Rule) -> list[IRRule]:
        if self.order is None:
            return [self.lower_rule(stmt)]
        if stmt.head.predicate.name in self.order.functions:
            raise TranspileError(f"Order sorts: {stmt.head.predicate.name} is a Fun and cannot be defined by a rule")
        var_types = self._var_types_of_body(stmt.body)
        head = pyir.atom_pred(stmt.head.predicate.name, [self.term(t) for t in stmt.head.args])
        out = []
        for cube in self.order.rewrite_rule_body(stmt.body, var_types):
            body = [pyir.formula_lit(self.literal(it.atom, it.positive)) for it in self._flatten(cube)]
            out.append(IRRule(head=head, body=body, is_choice=bool(stmt.is_choice)))
        return out

    def _var_types_of_body(self, body: list) -> dict[str, str]:
        assert self.checker is not None
        types: dict[str, str] = {}
        for lit in body:
            if isinstance(lit, nodes.PredAtom):
                info = self.checker.predicates.get(lit.predicate.name)
                if info is None:
                    continue
                for t, ty in zip(lit.args, info.arg_types):
                    if isinstance(t, nodes.Variable) and ty not in ("UNKNOWN", "CONST"):
                        types.setdefault(t.name, ty)
        return types

    @staticmethod
    def _flatten(cube: list) -> list:
        out = []
        for it in cube:
            if isinstance(it, _Conj):
                out.extend(it)
            else:
                out.append(it)
        return out

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

        if isinstance(formula, nodes.Acyclic):
            # (\acyclic r): clingo's acyclicity propagator over the relation's edges;
            # a relation of arity 2k has k-tuples as nodes (the layered SI encoding).
            # When r is defined only by positive rules and used nowhere else, the edges
            # are emitted from the rules' bodies and r is not materialised (the
            # relation would only be grounded to be read once by the propagator).
            assert self.checker is not None
            name = formula.predicate.name
            info = self.checker.predicates[name]
            k = info.arity // 2
            def node(terms):
                return terms[0] if k == 1 else "(" + ", ".join(terms) + ")"
            if self._acyclic_mode(name) == "closure":
                # the transitive closure as rules (the "closure in the language" form the
                # study measured by hand) with irreflexivity as the constraint
                xs = [f"X{i}" for i in range(k)]; ys = [f"Y{i}" for i in range(k)]; zs = [f"Z{i}" for i in range(k)]
                tc = f"__tc_{name}"
                self.extra_rules.append(f"{tc}({', '.join(xs + ys)}) :- {name}({', '.join(xs + ys)}).")
                self.extra_rules.append(f"{tc}({', '.join(xs + zs)}) :- {tc}({', '.join(xs + ys)}), {name}({', '.join(ys + zs)}).")
                self.extra_rules.append(f":- {tc}({', '.join(xs + xs)}).")
                return []
            inl = self._inline_edges.get(name)
            if inl:
                for head_terms, body in inl:
                    self.extra_rules.append(f"#edge ({node(head_terms[:k])}, {node(head_terms[k:])}) : {body}.")
                return []
            src = [f"X{i}" for i in range(k)]; dst = [f"Y{i}" for i in range(k)]
            self.extra_rules.append(f"#edge ({node(src)}, {node(dst)}) : {name}({', '.join(src + dst)}).")
            return []

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
        cubes = dnf(violation)
        if self.order is not None:
            cubes = [self._flatten(c) for cube in cubes for c in self.order.rewrite_cube(cube, self._var_types)]
        for cube in cubes:
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

        inner = pyir.formula_lit(self.aggregate(self.builder.aggregate(agg, tuple(quantified)), agg.comp_op))
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
            lits = [_general_lit_to_body_lit(self.item(it)) for it in cube]
            bound = self._positively_bound(cube)
            guards = []
            for v in list(fv) + [v for v in vars_ if v not in fv]:
                if v not in bound and v in self._var_types:
                    guards.append(f"dom_{self._var_types[v]}({v})")
            lits = guards + lits
            self.aux_rules.append(f"{head} :- {', '.join(lits) if lits else '#true'}.")
        return name, fv

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
