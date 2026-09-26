"""
Ground programs and their completion
====================================

The solver-level lowerings (``setlah.ext.sat``, ``setlah.ext.mono``) share this
module: the compiled ASP program is grounded by clingo's grounder, captured
through the observer interface, and turned into clauses by Clark's completion,
which is exact for *tight* programs (no positive cycle through the ground
rules). A program with a positive cycle (a transitive closure, the deadlock
model's executed-event closure) is refused with ``NotTight``; the ASP backend
stays the general one. Aggregates arrive as weight rules and become cardinality
constraints; ``#edge`` directives arrive as edges with a condition and are
handed to a graph theory (MonoSAT) or refused (plain SAT).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..transpile.ir import TranspileError


class NotTight(TranspileError):
    pass


class NotSupported(TranspileError):
    pass


@dataclass
class GroundProgram:
    rules: list = field(default_factory=list)          # (choice, [head atoms], [body lits])
    weight_rules: list = field(default_factory=list)   # (choice, [head atoms], lower, [(lit, weight)])
    edges: list = field(default_factory=list)          # (u, v, [cond lits])
    symbols: dict = field(default_factory=dict)        # atom -> symbol text (atom 0: facts)
    facts: list = field(default_factory=list)          # symbols reported with atom 0
    minimize: bool = False
    externals: set = field(default_factory=set)


def ground(source: str, extra_files: list[str] | None = None) -> GroundProgram:
    import clingo
    if "&diff{" in source or "&sum{" in source:
        raise NotSupported("theory atoms in the program: use the clingo-dl backend")
    gp = GroundProgram()

    class Obs(clingo.Observer):
        def rule(self, choice, head, body): gp.rules.append((choice, list(head), list(body)))
        def weight_rule(self, choice, head, lower, body): gp.weight_rules.append((choice, list(head), lower, [(l, w) for l, w in body]))
        def acyc_edge(self, u, v, cond): gp.edges.append((u, v, list(cond)))
        def output_atom(self, sym, atom):
            if atom == 0: gp.facts.append(str(sym))
            else: gp.symbols[atom] = str(sym)
        def minimize(self, prio, lits): gp.minimize = True
        def external(self, atom, value): gp.externals.add(atom)
        def theory_atom(self, *a): raise NotSupported("theory atoms in the program: use the clingo-dl backend")

    ctl = clingo.Control(["--warn=none"])
    ctl.register_observer(Obs())
    ctl.add("base", [], source)
    for f in extra_files or []:
        ctl.load(f)
    ctl.ground([("base", [])])
    if gp.minimize:
        raise NotSupported("an objective in the program: the SAT backends decide satisfiability only")
    return gp


@dataclass
class Completion:
    clauses: list                       # list of [int]
    cards: list                         # (head var, [lits], lower): head <-> (#true lits >= lower)
    edges: list                         # (u, v, [cond lits])
    nvars: int
    symbols: dict
    facts: list


def complete(gp: GroundProgram) -> Completion:
    """Clark's completion of a tight ground program, with cardinality constraints
    and edges left symbolic for the backend."""
    atoms: set = set()
    for _, head, body in gp.rules:
        atoms.update(head); atoms.update(abs(l) for l in body)
    for _, head, _, body in gp.weight_rules:
        atoms.update(head); atoms.update(abs(l) for l, _ in body)
    for _, _, cond in gp.edges:
        atoms.update(abs(l) for l in cond)
    atoms.discard(0)
    top = max(atoms) if atoms else 0
    normal: dict = {}; choice: dict = {}; wnormal: dict = {}; wchoice: dict = {}
    clauses: list = []
    for ch, head, body in gp.rules:
        if not head:
            clauses.append([-l for l in body]); continue
        if len(head) > 1 and not ch:
            raise NotSupported("a disjunctive rule in the ground program")
        for a in head:
            (choice if ch else normal).setdefault(a, []).append(body)
    for ch, head, lower, body in gp.weight_rules:
        if not head:
            raise NotSupported("a weight constraint without a head in the ground program")
        if len(head) > 1 and not ch:
            raise NotSupported("a disjunctive weight rule in the ground program")
        for a in head:
            (wchoice if ch else wnormal).setdefault(a, []).append((lower, body))
    # tightness: the positive dependency graph over defining and choice bodies
    dep: dict = {}
    for a, bodies in list(normal.items()) + list(choice.items()):
        for body in bodies:
            dep.setdefault(a, set()).update(l for l in body if l > 0)
    for a, wb in list(wnormal.items()) + list(wchoice.items()):
        for _, body in wb:
            dep.setdefault(a, set()).update(l for l, _ in body if l > 0)
    color: dict = {}
    for start in dep:
        if start in color:
            continue
        stack = [(start, iter(dep.get(start, ())))]; color[start] = 1
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                color[node] = 2; stack.pop(); continue
            c = color.get(nxt)
            if c == 1:
                raise NotTight(f"the ground program is not tight: a positive cycle through {gp.symbols.get(nxt, nxt)}; the SAT backends decide tight programs only")
            if c is None:
                color[nxt] = 1; stack.append((nxt, iter(dep.get(nxt, ()))))
    defined = set(normal) | set(choice) | set(wnormal) | set(wchoice)
    cards: list = []
    def fresh():
        nonlocal top
        top += 1; return top
    def conj(body):
        """a literal equivalent to the conjunction of ``body``"""
        if not body:
            return None
        if len(body) == 1:
            return body[0]
        b = fresh()
        for l in body:
            clauses.append([-b, l])
        clauses.append([b] + [-l for l in body])
        return b
    def card(lower, body):
        """a literal equivalent to sum(w * lit) >= lower"""
        weights = {w for _, w in body}
        if len(weights) == 1:
            w = weights.pop()
            lits = [l for l, _ in body]; bound = -(-lower // w) if w > 0 else None
            if bound is None:
                raise NotSupported("a non-positive weight in an aggregate")
            if bound <= 0:
                return None
            if bound > len(lits):
                return False
            h = fresh()
            cards.append((h, lits, bound))
            return h
        raise NotSupported("an aggregate with mixed weights (a #sum): not encoded by the SAT backends")
    for a in sorted(defined):
        supports: list = []; fact = False; free = False
        for body in normal.get(a, []):
            b = conj(body)
            if b is None:
                fact = True; break
            clauses.append([a, -b]); supports.append(b)
        if fact:
            clauses.append([a]); continue
        for lower, body in wnormal.get(a, []):
            h = card(lower, body)
            if h is None:
                fact = True; break
            if h is False:
                continue
            clauses.append([a, -h]); supports.append(h)
        if fact:
            clauses.append([a]); continue
        for body in choice.get(a, []):
            b = conj(body)
            if b is None:
                free = True; break
            supports.append(b)
        if free:
            continue
        for lower, body in wchoice.get(a, []):
            h = card(lower, body)
            if h is None:
                free = True; break
            if h is False:
                continue
            supports.append(h)
        if free:
            continue
        clauses.append([-a] + supports)
    for a in atoms - defined:
        clauses.append([-a])
    return Completion(clauses, cards, list(gp.edges), top, gp.symbols, gp.facts)


def card_clauses(comp: Completion) -> tuple[list, int]:
    """The cardinality constraints of a completion as clauses (pysat's sequential
    counter), ``h <-> atleast`` in both directions; returns (clauses, top var)."""
    from pysat.card import CardEnc, EncType
    out: list = []; top = comp.nvars
    for h, lits, bound in comp.cards:
        enc = CardEnc.atleast(lits=lits, bound=bound, top_id=top, encoding=EncType.seqcounter)
        top = max(top, enc.nv)
        out += [c + [-h] for c in enc.clauses]
        enc = CardEnc.atmost(lits=lits, bound=bound - 1, top_id=top, encoding=EncType.seqcounter)
        top = max(top, enc.nv)
        out += [c + [h] for c in enc.clauses]
    return out, top


def model_symbols(comp: Completion, true_lits: Callable[[int], bool]) -> list[str]:
    return comp.facts + [s for a, s in sorted(comp.symbols.items()) if true_lits(a)]
