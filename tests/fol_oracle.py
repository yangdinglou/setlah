"""A brute-force first-order oracle for compiled programs.

Evaluates a model's source constraints directly over the finite domains of an
instance, so an answer set of the compiled program can be checked against
the source semantics without any second compiler. Domains come from the
``dom_<Sort>`` facts, or from the active domain of the sort when an input
gives none (the B14 case). Aggregates follow the lowering's matching of
formula variables to the set predicate's arguments (by name, then by
position).
"""

from __future__ import annotations

import clingo

from setlah.ast import nodes
from setlah.parsing.checker import SemanticChecker


def answer_sets(asp: str, facts: str, cap: int = 100000) -> list[set]:
    ctl = clingo.Control([str(cap), "--warn=none"])
    ctl.add("base", [], asp + "\n" + facts)
    ctl.ground([("base", [])])
    out: list[set] = []

    def on_model(m):
        out.append({
            (s.name, tuple(x.number if x.type == clingo.SymbolType.Number else str(x) for x in s.arguments))
            for s in m.symbols(atoms=True)
        })

    ctl.solve(on_model=on_model)
    return out


class Oracle:
    def __init__(self, program: nodes.Program, checker: SemanticChecker):
        self.program = program
        self.checker = checker
        self.sorts = [d.var.name for d in program.domains if isinstance(d, (nodes.ExtDOM, nodes.DefDOM))]

    def constraints(self) -> list[nodes.SetConstraint]:
        return [s for b in self.program.blocks for s in b.statements if isinstance(s, nodes.SetConstraint)]

    def domain(self, sort: str, atoms: set) -> list:
        given = {args[0] for (n, args) in atoms if n == f"dom_{sort}"}
        if given:
            return sorted(given, key=str)
        active = set()
        for name, info in self.checker.predicates.items():
            for i, t in enumerate(info.arg_types):
                if t == sort:
                    active |= {args[i] for (n, args) in atoms if n == name and len(args) > i}
        return sorted(active, key=str)

    def term(self, t, env: dict):
        if isinstance(t, nodes.Variable):
            return env[t.name]
        if isinstance(t, nodes.Constant):
            return t.value
        if isinstance(t, nodes.Identifier):
            return t.name
        if isinstance(t, nodes.BinaryExpr):
            l, r = self.term(t.left, env), self.term(t.right, env)
            return {"+": l + r, "-": l - r, "*": l * r, "/": (l // r if r else 0)}[t.op]
        raise ValueError(f"unsupported term {t!r}")

    def var_sort(self, f, name: str) -> str:
        found: list[str] = []

        def walk(g):
            if isinstance(g, nodes.PredAtom):
                info = self.checker.predicates.get(g.predicate.name)
                for i, x in enumerate(g.args):
                    if isinstance(x, nodes.Variable) and x.name == name and info and i < len(info.arg_types):
                        found.append(info.arg_types[i])
            elif isinstance(g, nodes.LogicalOp):
                for x in g.operands:
                    walk(x)
            elif isinstance(g, nodes.QuantifiedFormula):
                if g.variable.name != name:
                    walk(g.body)

        walk(f)
        return found[0] if found else self.sorts[0]

    def holds(self, f, env: dict, atoms: set) -> bool:
        if isinstance(f, nodes.PredAtom):
            return (f.predicate.name, tuple(self.term(x, env) for x in f.args)) in atoms
        if isinstance(f, nodes.Comparison):
            l, r = self.term(f.left, env), self.term(f.right, env)
            return {"==": l == r, "!=": l != r, "<": l < r, "<=": l <= r, ">": l > r, ">=": l >= r}[f.op]
        if isinstance(f, nodes.BooleanConst):
            return bool(f.val)
        if isinstance(f, nodes.LogicalOp):
            if f.op == "and":
                return all(self.holds(x, env, atoms) for x in f.operands)
            if f.op == "or":
                return any(self.holds(x, env, atoms) for x in f.operands)
            if f.op == "not":
                return not self.holds(f.operands[0], env, atoms)
            if f.op == "impl":
                return (not self.holds(f.operands[0], env, atoms)) or self.holds(f.operands[1], env, atoms)
        if isinstance(f, nodes.QuantifiedFormula):
            dom = self.domain(self.var_sort(f.body, f.variable.name), atoms)
            results = []
            for v in dom:
                inner = dict(env)
                inner[f.variable.name] = v
                results.append(self.holds(f.body, inner, atoms))
            return all(results) if f.quantifier in ("forall", "∀") else any(results)
        if isinstance(f, nodes.Aggregation):
            return self.aggregate(f, env, atoms)
        raise ValueError(f"unsupported formula {type(f).__name__}")

    def aggregate(self, f: nodes.Aggregation, env: dict, atoms: set) -> bool:
        pred = f.set_var.name[4:].lower()
        info = self.checker.predicates[pred]
        counted = [x.name for x in f.set_var.parameters.elements]
        canonical = list(info.canonical_args) or [f"_{i}" for i in range(info.arity)]
        by_name = set(counted) | set(env)
        unmatched = [i for i, a in enumerate(canonical) if a not in by_name]
        spare = [v for v in list(env) + counted if v not in canonical]
        fill = dict(zip(unmatched, spare))
        roles = [fill.get(i, a) for i, a in enumerate(canonical)]   # formula variable per position
        projected = set()
        for (name, args) in atoms:
            if name != pred:
                continue
            ok = True
            proj = []
            for i, v in enumerate(roles):
                if v in counted:
                    proj.append(args[i])
                elif v in env and env[v] != args[i]:
                    ok = False
                    break
            if ok:
                projected.add(tuple(proj))
        n, val = len(projected), self.term(f.value, env)
        return {"==": n == val, "!=": n != val, "<": n < val, "<=": n <= val, ">": n > val, ">=": n >= val}[f.comp_op]

    def violations(self, atoms: set) -> list[nodes.SetConstraint]:
        return [c for c in self.constraints() if not self.holds(c.formula, {}, atoms)]
