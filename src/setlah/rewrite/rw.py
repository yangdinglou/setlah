import re
import time
from egglog import EGraph, Expr, ruleset, rewrite, var, Set, get_callable_args  # MARK: AND-split — added Expr, get_callable_args
from ..ast import nodes as nodes
from .converter import convert_block, convert_constraint, convert_rule, to_egg, set_pred_signatures
from .egg_schema import Term, Atom, Literal, Formula, GeneralLit, Constraint, Block, Rule, nil_constraint, cons_constraint, nil_var, cons_var, Vec, LetExpr, ConsList  # MARK: AND-split — added ConsList
from .egg_rules import *
from ..parsing.checker import SemanticChecker, export_entailment_specs, export_pred_arg_types
from ..transpile.ir import PrintedBlock


# MARK: AND-split — custom cost model for extraction
def split_cost_model(egraph: EGraph, expr: Expr, children_costs: list[int]) -> int:
    """Custom cost model that heavily penalises Formula.And.

    By making And very expensive, the extractor will always prefer the
    split form  cons(Constraint(a), cons(Constraint(b), rest))  over
    the unsplit  cons(Constraint(And(a,b)), rest)  when both are in the
    same e-class (established by the conjunction_split equality rule).

    Everything else uses the default cost (1 + sum of children costs).
    """
    # Check if this node is Formula.And
    args = get_callable_args(expr, Formula.And)
    if args is not None:
        return 1_000_000 + sum(children_costs)

    # Default: base cost 1 + children
    return 1 + sum(children_costs)

class Rewriter:
    # Schedule knobs for _rewrite_single_constraint (docs/known-issues.md, B2).
    # Phase 1 runs the extraction rules in _EXTRACTION_CHUNKS runs of
    # _EXTRACTION_CHUNK_ITERS iterations each, resetting the back-off
    # scheduler between runs; Phase 2 repeats the aux round at most
    # _AUX_ROUNDS times, stopping as soon as the term is lowered.
    _EXTRACTION_CHUNKS = 4
    _EXTRACTION_CHUNK_ITERS = 5
    _AUX_ROUNDS = 4

    def __init__(self, verbose: bool = False, *, entailment_elim: str = "asp", enable_cost_conversion: bool = False):
        self.egraph = None
        self.checker = None
        self.entailment_ruleset = None
        self.verbose = verbose
        self.entailment_elim = entailment_elim
        self.enable_cost_conversion = enable_cost_conversion
        self.aux_rules: list[str] = []  # Collected aux rules
        # Next free index for ``__aux_N`` names. One counter per compilation
        # unit: reset in :meth:`rewrite_program` and handed to the transpiler
        # as ``program._aux_next`` so that the auxiliaries it lowers itself
        # continue the numbering instead of restarting at zero (B7).
        self._next_aux = 0

    def rewrite_program(self, program: nodes.Program, convert_only=False) -> nodes.Program:
        # Run semantic checker first to collect entailment information
        if not convert_only:
            if self.verbose:
                print("Running semantic checker...")
            self.checker = SemanticChecker(verbose=self.verbose)
            self.checker.check_program(program)

            # Pass predicate signatures to converter for projected aggregation desugaring
            set_pred_signatures(self.checker.predicates)

            # Entailment elimination can be done in egglog (during rewriting),
            # during egg->ASP rendering, or both.
            if self.entailment_elim in ("egg", "both"):
                self.entailment_ruleset = self._generate_entailment_ruleset()
            else:
                self.entailment_ruleset = None

            if self.entailment_elim in ("asp", "both"):
                # Export a lightweight entailment spec for the transpiler.
                # This lets us drop redundant entailed literals that may only become
                # apparent after extraction (e.g. inside integrity constraints).
                program._entailment_specs = self._export_entailment_specs()  # type: ignore[attr-defined]
            else:
                # Make sure stale specs don't leak across runs.
                if hasattr(program, "_entailment_specs"):
                    try:
                        delattr(program, "_entailment_specs")
                    except Exception:
                        pass

            # Export predicate signatures (arg domains) for post-processing rewrites
            # in the ASP transpiler (e.g., adding dom_ guards for safety).
            program._pred_arg_types = self._export_pred_arg_types()  # type: ignore[attr-defined]
            if self.verbose:
                print()
        
        new_blocks = []
        self.aux_rules = []  # Reset aux rules for this program
        self._next_aux = 0   # ... and the auxiliary name counter with them
        for block in program.blocks:
            if self.verbose:
                print("Rewriting Block:")
            self.egraph=EGraph()
            new_blocks.append(self.rewrite_block(block,convert_only))
            if self.verbose:
                print("Finished Rewriting Block.\n")
        program.blocks = new_blocks
        
        # Store collected aux rules in the program for the transpiler, and the
        # next free auxiliary index so its own auxiliaries do not collide.
        program._aux_next = self._next_aux  # type: ignore[attr-defined]
        if self.aux_rules:
            program._aux_rules = self.aux_rules  # type: ignore[attr-defined]
            if self.verbose:
                print(f"Collected {len(self.aux_rules)} aux rules:")
                for r in self.aux_rules:
                    print(f"  {r}")

        if self.verbose:
            print("Finished Rewriting Program.")
        return program

    def rewrite_block(self, block: nodes.Block, convert_only=False) -> PrintedBlock:
        """Rewrite a block at the constraint level.

        Strategy:
        1. Convert rules directly (no egg rewriting needed for rules)
        2. Convert and rewrite each constraint individually through egg
           - Wrap as cons_constraint(phi, nil) for input
           - Output may be multiple constraints (cons_constraint chain)
        3. Hand the result to the transpiler as a ``PrintedBlock``: one
           printed egglog term per rule and per constraint.  A single
           ``Block(...)`` term nests one level per constraint, and egglog
           can neither register such a chain past about 300 cells nor
           print it in linear space, while Python's parser refuses it near
           200 (docs/known-issues.md, B5).
        """
        try:
            # 1. Convert rules - they don't need egg rewriting
            egg_rules = [convert_rule(stmt) for stmt in block.statements if isinstance(stmt, nodes.Rule)]

            # 2. Convert and rewrite each constraint individually
            all_rewritten_constraints: list[Constraint] = []
            constraint_stmts = [s for s in block.statements if isinstance(s, nodes.SetConstraint)]

            if self.verbose:
                print(f"Block has {len(constraint_stmts)} constraints to rewrite")

            # Combine entailment rewrites with equal_set
            eq_rules = equal_set if not self.entailment_ruleset else (equal_set | self.entailment_ruleset)
            extraction_rules = extraction if not self.entailment_ruleset else (extraction | self.entailment_ruleset)

            # MARK: AND-split — Phase 0: Conjunction splitting ─────────
            # Convert all constraints, put them in a single ConsList,
            # saturate split_set (conjunction_split + And-associativity),
            # then extract with a custom cost model that penalises And.
            egg_constraints = []
            for stmt in constraint_stmts:
                egg_constraints.append(convert_constraint(stmt))

            if convert_only:
                all_rewritten_constraints.extend(egg_constraints)
            else:
                split_constraints = self._split_constraints(egg_constraints)

                if self.verbose:
                    print(f"After splitting: {len(egg_constraints)} -> {len(split_constraints)} constraints")

                # ── Phase 1+: Rewrite each split constraint ─────────────
                for i, c in enumerate(split_constraints):
                    if self.verbose:
                        print(f"\n--- Processing Constraint {i+1}/{len(split_constraints)} ---")
                    rewritten_list = self._rewrite_single_constraint(c, eq_rules, extraction_rules)
                    all_rewritten_constraints.extend(rewritten_list)
                    if self.verbose and len(rewritten_list) > 1:
                        print(f"  -> Produced {len(rewritten_list)} constraints")

            # 3. Print statement by statement for the transpiler
            final_block = PrintedBlock(
                rules=[str(r) for r in egg_rules],
                constraints=[str(c) for c in all_rewritten_constraints],
            )

            if self.verbose:
                print("\nRewritten Block:")
                for text in final_block.rules + final_block.constraints:
                    print(text)

            return final_block

        except Exception as e:
            if self.verbose:
                print(f"Rewrite failed: {e}")
                import traceback
                traceback.print_exc()
            raise
    
    # MARK: AND-split — core splitting method
    def _split_constraints(self, constraints: list[Constraint]) -> list[Constraint]:
        """Split top-level conjunctions using split_set + custom cost model.

        Uses a dedicated *minimal* ruleset (split_set) that only contains:
          - conjunction_split: cons(Constraint(And(a,b)), rest) → cons(Constraint(a), cons(Constraint(b), rest))
          - Implies(a, And(b,c)) → And(Implies(a,b), Implies(a,c))
          - ∀x.(A∧B) → (∀x.A) ∧ (∀x.B)
          - And associativity

        This avoids running the full equal_set (with commutativity, De Morgan,
        distributivity, etc.) which would pollute e-classes and cause
        constraint merging via the idempotency rule.

        Each constraint is split in its own e-graph.  The split rules only
        ever look at one cons cell, so this is the same rewrite as splitting
        the whole block at once, without the block-sized cons list that
        egglog cannot register past about 300 cells (B5).

        Returns the list of individual (split) Constraints.
        """
        if self.verbose:
            print(f"Splitting: {len(constraints)} constraints, one e-graph each")
            t0 = time.perf_counter()

        split_result: list[Constraint] = []
        for c in constraints:
            egraph = EGraph()
            cons_list: ConsList = cons_constraint(c, nil_constraint())
            egraph.register(cons_list)

            # Saturate with only split_set — deliberately NOT equal_set.
            egraph.run(
                run(split_set, scheduler=back_off()) * 15
            )

            # Extract with the custom cost model that penalises And
            best = egraph.extract(cons_list, include_cost=True, cost_model=split_cost_model)
            if isinstance(best, tuple):
                best = best[0]
            split_result.extend(self._extract_constraints_from_cons_list(best))

        if self.verbose:
            print(f"  Splitting: {time.perf_counter() - t0:.3f}s, {len(split_result)} constraints after splitting")

        return split_result

    def _rewrite_single_constraint(self, constraint: Constraint, eq_rules, extraction_rules, max_depth: int = 64) -> list[Constraint]:
        """Rewrite a single constraint through egg, handling aux predicate introduction.

        Input: single Constraint
        Output: list of Constraints (one constraint may become multiple)

        Uses recursion for aux replacement: after replacing AuxCall patterns,
        recursively calls itself to fully rewrite the modified constraint.
        Each pass lowers one quantifier level to an auxiliary predicate, so
        the recursion depth needed equals the nesting depth of the
        constraint; a cap of 5 stopped nested universals at depth 7
        (docs/known-issues.md, B2).

        Args:
            constraint: The constraint to rewrite
            eq_rules: Equality rules for normalization
            extraction_rules: Extraction rules for IC conversion
            max_depth: Safety stop on the recursion; every pass strictly
                reduces the quantifier depth, so it is not reached by any
                finite input in practice (default: 64)
        
        Internally wraps as cons_constraint(phi, nil_constraint()) for egg processing.
        """
        # Create fresh egraph for this constraint
        self.egraph = EGraph()
        
        # Wrap constraint in a ConsList: cons_constraint(phi, nil_constraint())
        cons_list = cons_constraint(constraint, nil_constraint())
        self.egraph.register(cons_list)
        
        if self.verbose:
            print(f"Registered: cons_constraint(phi, nil) [depth={max_depth}]")
        
        # Phase 1: Initial normalization and extraction
        if self.verbose:
            print("Running base rewrite rules...")
            t0 = time.perf_counter()
        self.egraph.run(
            run(term_set).saturate()
            + run(eq_rules, scheduler=back_off()) * 15
        )
        # The extraction rules build grouped forms one literal and one
        # quantifier level per iteration. Under one back-off scheduler a rule
        # banned early stays banned for a doubling number of iterations, so
        # with 20 iterations in one run the chains did not finish for some
        # literal counts (8 variables fell back, 9 lowered). Running the same
        # 20 iterations as four runs of five resets the scheduler's bans
        # between them (docs/known-issues.md, B2).
        for _ in range(self._EXTRACTION_CHUNKS):
            self.egraph.run(run(extraction_rules, scheduler=back_off()) * self._EXTRACTION_CHUNK_ITERS)
        if self.verbose:
            print(f"  Phase 1 (base rules): {time.perf_counter() - t0:.3f}s")
        
        # Phase 1.5: Cost conversion (make aggregates more costly to prefer aux predicates)
        if not self.enable_cost_conversion:
            if self.verbose:
                print("Running cost conversion rules...")
                t0 = time.perf_counter()
            self.egraph.run(
                run(cost_conversion).saturate()
            )
            if self.verbose:
                print(f"  Phase 1.5 (cost conversion): {time.perf_counter() - t0:.3f}s")
        
        # Phase 2: Auxiliary predicate introduction.
        # The aux rule needs the grouped forms (grouped_exists over a
        # grouped_dnf of literal cubes) that the extraction rules may only
        # complete late, so one aux round was not always enough. Repeat the
        # round until the extracted term is an integrity constraint or holds
        # an AuxCall for the next pass, with a small cap. An unchanged
        # extracted term is not a stopping criterion: the e-graph can still be
        # progressing while the cheapest representative stays the same
        # (docs/known-issues.md, B2).
        if self.verbose:
            print("Running aux predicate introduction...")
            t0 = time.perf_counter()
        best = None
        best_str = ""
        for aux_round in range(self._AUX_ROUNDS):
            self.egraph.run(
                run(aux_set, scheduler=back_off()) * 1
                + run(extraction_rules, scheduler=back_off()) * 10
            )
            best = self.egraph.extract(cons_list, include_cost=True)
            best_str = str(best)
            if "Literal.AuxCall(" in best_str or not self._contains_non_ic(best_str):
                break
        if self.verbose:
            print(f"  Phase 2 (aux intro): {time.perf_counter() - t0:.3f}s, {aux_round + 1} round(s)")
            print(f"best extracted cons_list: {best_str}...")
            print(f"After aux introduction: cost={best[1] if isinstance(best, tuple) else '?'}")

        
        # Phase 3: Replace AuxCall patterns and recursively rewrite if needed
        result_from_aux = None
        if "Literal.AuxCall(" in best_str and max_depth > 0:
            if self.verbose:
                print(f"Found AuxCall patterns, replacing and recursively rewriting (depth={max_depth})...")
                t_iter = time.perf_counter()
            
            # Normalize and replace AuxCall patterns
            normalized_str = self._normalize_cons_list_str(best_str)
            modified_str, new_aux_rules = self._replace_aux_calls(normalized_str)
            self.aux_rules.extend(new_aux_rules)
            
            if self.verbose:
                print(f"  Replaced AuxCall patterns in cons_list.")
                print(f"  Modified cons_list: {modified_str}")
                print(f"Generated {len(new_aux_rules)} aux rules:")
                for r in new_aux_rules:
                    print(f"    {r}")
            
            # Parse the modified expression and extract individual constraints
            try:
                modified_expr = eval(modified_str)
                modified_constraints = self._extract_constraints_from_cons_list(modified_expr)
                
                if self.verbose:
                    print(f"  Extracted {len(modified_constraints)} constraints after aux replacement")
                
                # Recursively rewrite each constraint with reduced depth
                all_results = []
                for i, c in enumerate(modified_constraints):
                    if self.verbose:
                        print(f"\n  --- Recursive rewrite of constraint {i+1}/{len(modified_constraints)} (depth={max_depth-1}) ---")
                    results = self._rewrite_single_constraint(c, eq_rules, extraction_rules, max_depth - 1)
                    all_results.extend(results)
                
                if self.verbose:
                    print(f"Recursive rewrite complete, time={time.perf_counter() - t_iter:.3f}s")

                result_from_aux = all_results

            except Exception as e:
                if self.verbose:
                    print(f"Warning: Failed to recursively rewrite: {e}")
                    import traceback
                    traceback.print_exc()
                # Fall through to return the original best
        
        elif "Literal.AuxCall(" in best_str and max_depth <= 0:
            if self.verbose:
                print(f"Warning: Reached max recursion depth, AuxCall patterns remain")
        
        # Final result: from aux handling or direct extraction
        if result_from_aux is not None:
            final_result = result_from_aux
        else:
            if isinstance(best, tuple):
                best = best[0]
            final_result = self._extract_constraints_from_cons_list(best)

        # Fallback: if cost-conversion produced non-IC output, retry without it
        if (self.enable_cost_conversion and
                any(self._contains_non_ic(str(c)) for c in final_result)):
            if self.verbose:
                print("Cost-conversion produced non-IC output, retrying without cost-conversion...")
            self.enable_cost_conversion = False
            try:
                final_result = self._rewrite_single_constraint(constraint, eq_rules, extraction_rules, max_depth)
            finally:
                self.enable_cost_conversion = True

        return final_result
    
    def _contains_non_ic(self, expr_str: str) -> bool:
        """Check if the extracted expression contains non-IC constraints.
        
        A constraint is IC if it's in the form Constraint.integrity_constraints(...).
        If we see raw Constraint(...) (not integrity_constraints), it's non-IC.
        """
        # If there's a Constraint( that isn't Constraint.integrity_constraints(
        # then it's not yet fully converted to IC form
        import re
        # Find all Constraint( occurrences that are NOT Constraint.integrity_constraints(
        # This regex looks for "Constraint(" not followed by "integrity_constraints"
        if re.search(r'Constraint\((?!integrity_constraints)', expr_str):
            return True
        return False
    
    def _extract_constraints_from_cons_list(self, cons_list) -> list[Constraint]:
        """Extract all Constraints from a ConsList (cons_constraint chain).

        Walks the term structurally with ``get_callable_args``; the chain is
        never printed, so its length is not limited by the printer (B5).
        """
        # A printed chain (debugging) still goes through the string parser.
        if isinstance(cons_list, str):
            return self._parse_cons_list_str(cons_list)

        constraints: list[Constraint] = []
        current = cons_list
        while True:
            args = get_callable_args(current, cons_constraint)
            if args is not None:
                head, tail = args
                constraints.append(head)
                current = tail
                continue
            if get_callable_args(current, nil_constraint) is not None:
                return constraints
            raise ValueError(f"Unknown cons_list form: {str(current)[:200]}")

    def _parse_cons_list_str(self, s: str) -> list[Constraint]:
        """Parse cons_constraint string into list of Constraint strings, then eval them."""
        constraints = []
        normalized = self._normalize_cons_list_str(s)
        current = normalized.strip()
        
        while current.startswith("cons_constraint("):
            # Extract the cons_constraint call
            content = self._extract_balanced_call(current, 0)
            inner = content[16:-1].strip()  # Remove "cons_constraint(" and ")"
            
            # Find the FIRST top-level comma to split constraint from tail
            depth = 0
            first_comma = -1
            for i, c in enumerate(inner):
                if c in '([{':
                    depth += 1
                elif c in ')]}':
                    depth -= 1
                elif c == ',' and depth == 0:
                    first_comma = i
                    break
            
            if first_comma == -1:
                break
            
            constraint_str = inner[:first_comma].strip()
            tail = inner[first_comma+1:].strip()
            
            # Eval the constraint
            try:
                constraint_obj = eval(constraint_str)
                constraints.append(constraint_obj)
            except Exception as e:
                if self.verbose:
                    print(f"Warning: Failed to parse constraint: {e}")
                    print(f"  String: {constraint_str[:200]}...")
            
            current = tail
        
        return constraints
    
    def _normalize_cons_list_str(self, s: str) -> str:
        """Normalize egglog's extracted ConsList expression to valid Python.
        
        Handles auxiliary bindings like:
            (_VarList_1 = cons_var(...), cons_constraint(...), 123)
        
        Also handles multi-line bindings like:
            _GeneralLit_3 = GeneralLit.from_literal(
                Literal(
                    ...
                )
            )
            cons_constraint(...)
        """
        s = s.strip()
        
        # Find where cons_constraint starts
        cons_start = s.find("cons_constraint(")
        if cons_start == -1:
            # Maybe it's nil_constraint
            nil_start = s.find("nil_constraint(")
            if nil_start == -1:
                return s
            cons_start = nil_start
        
        # Parse bindings before cons_constraint
        bindings = self._parse_binding_prefix(s[:cons_start])

        # Resolve bindings among themselves (iterate to fixed point)
        # Sort by name length descending so longer names (e.g. _Formula_10) are
        # resolved before shorter prefixes (e.g. _Formula_1) to avoid substring aliasing.
        max_iterations = 20
        for _ in range(max_iterations):
            changed = False
            for name in bindings:
                old_value = bindings[name]
                new_value = old_value
                for other_name, other_value in sorted(bindings.items(), key=lambda x: len(x[0]), reverse=True):
                    if other_name != name and other_name in new_value:
                        # Use word-boundary replacement to avoid substring aliasing
                        new_value = re.sub(re.escape(other_name) + r'(?!\w)', other_value, new_value)
                if new_value != old_value:
                    bindings[name] = new_value
                    changed = True
            if not changed:
                break
        
        # Extract cons_constraint(...) or nil_constraint() expression
        cons_expr = self._extract_balanced_call(s, cons_start)
        
        # MARK: AND-split — substitute bindings (longest names first to avoid
        # substring aliasing, e.g. _Formula_1 matching inside _Formula_10)
        result = cons_expr
        for name, value in sorted(bindings.items(), key=lambda x: len(x[0]), reverse=True):
            result = re.sub(re.escape(name) + r'(?!\w)', value, result)
        
        # MARK: AND-split — normalize egglog extraction quirks to valid Python
        result = result.replace("Vec[LetExpr].empty()", "Vec[LetExpr]()")
        # Strip e-class indices that egglog appends between closing parens.
        # These look like "))0)" or ")))1)" — bare digits sandwiched between
        # closing parens.  In valid Python a digit never appears between ")" and ")".
        # We must NOT strip digits that are actual arguments like Term.Int(1).
        # Use a lookahead so the trailing ")" is not consumed and overlapping
        # matches (e.g. ")))0)))1)") are handled correctly.
        result = re.sub(r'(?<=\))\d+(?=\))', '', result)
        
        return result
    
    def _parse_binding_prefix(self, prefix: str) -> dict[str, str]:
        """Parse the let-style bindings egglog prints before the body.

        egglog emits them either comma-separated on one line

            (_VarList_1 = cons_var(...), _Set_1 = Set[Term](...), cons_constraint(...), 12)

        or one per line, with the first following the tuple's "(" and later
        ones possibly indented

            (_Formula_1 = Formula.Lit(
                 Literal(...)
             )
             _VarList_1 = cons_var(...)

        A binding starts where a name appears at parenthesis depth 0 followed
        by "="; its value runs to the next such start.  Scanning by depth
        handles both layouts and never mistakes a *use* of a name inside a
        value for a new binding.  Splitting on commas (no commas in the
        multi-line form) or anchoring names to the start of a line (missing
        the first binding after "(" and every indented one) made one binding's
        value swallow the text of the next, and substituting that value
        spliced a binding definition into the middle of the expression --
        which then no longer parsed, so auxiliary calls were left unlowered
        and the transpiler crashed on them (docs/known-issues.md, B1).
        """
        s = prefix.strip()
        if s.startswith("("):
            s = s[1:]

        starts: list[tuple[str, int, int]] = []  # (name, value start, binding start)
        depth = 0
        i = 0
        n = len(s)
        while i < n:
            c = s[i]
            if c in "([{":
                depth += 1
                i += 1
                continue
            if c in ")]}":
                depth -= 1
                i += 1
                continue
            if depth == 0 and c == "_":
                m = re.match(r"_[A-Za-z0-9_]*", s[i:])
                if m:
                    j = i + m.end()
                    while j < n and s[j] in " \t\r\n":
                        j += 1
                    # "=" but not "==": a binding, not a comparison
                    if j < n and s[j] == "=" and (j + 1 >= n or s[j + 1] != "="):
                        j += 1
                        while j < n and s[j] in " \t\r\n":
                            j += 1
                        starts.append((m.group(0), j, i))
                        i = j
                        continue
            i += 1

        bindings: dict[str, str] = {}
        for k, (name, value_start, _) in enumerate(starts):
            value_end = starts[k + 1][2] if k + 1 < len(starts) else len(s)
            value = s[value_start:value_end].strip().rstrip(",").strip()
            if name and value:
                bindings[name] = value
        return bindings

    def _parse_multiline_bindings(self, prefix: str) -> dict[str, str]:
        """Deprecated alias of :meth:`_parse_binding_prefix`."""
        return self._parse_binding_prefix(prefix)

    def _replace_aux_calls(self, expr_str: str) -> tuple[str, list[str]]:
        """Replace Literal.AuxCall patterns with regular Literal predicates.
        
        This allows the modified expression to be fed back to egg for further
        rewriting (e.g., converting ∀R.aux(R,A,B) to count aggregates).
        
        Returns:
            (modified_expr_str, list_of_aux_rules_as_asp)
        """
        aux_rules: list[str] = []
        result = expr_str
        
        # Pattern: Literal.AuxCall(body_lits_set, qvars_set, free_vars_set)
        auxcall_pattern = r'Literal\.AuxCall\('
        
        while True:
            match = re.search(auxcall_pattern, result)
            if not match:
                break
            
            start = match.start()
            # Extract the full AuxCall(...) expression
            call_str = self._extract_balanced_call(result, start + len("Literal."))
            call_full = "Literal." + call_str
            
            try:
                aux_info = self._parse_aux_call(call_full)
                if aux_info is None:
                    # Can't parse, skip this match
                    break
                
                cubes_asp, free_vars = aux_info

                # Generate aux predicate name
                aux_name = f"__aux_{self._next_aux}"
                self._next_aux += 1

                # Generate one aux rule per DNF cube: aux_name(free_vars) :- lits_in_cube
                for cube_asp in cubes_asp:
                    aux_rules.append(self._generate_aux_rule(aux_name, cube_asp, free_vars))
                
                # Generate replacement: Literal(Atom.Pred("aux_name", varlist), True)
                replacement = self._generate_aux_literal(aux_name, free_vars)
                
                # Replace in result
                end = start + len(call_full)
                result = result[:start] + replacement + result[end:]
                
            except Exception as e:
                if self.verbose:
                    print(f"Warning: Failed to parse AuxCall: {e}")
                break
        
        return result, aux_rules
    
    def _split_top_level(self, s: str, sep: str) -> list[str]:
        """Split string at top-level occurrences of separator."""
        parts = []
        depth = 0
        current = []
        for c in s:
            if c in '([{':
                depth += 1
                current.append(c)
            elif c in ')]}':
                depth -= 1
                current.append(c)
            elif c == sep and depth == 0:
                parts.append(''.join(current))
                current = []
            else:
                current.append(c)
        if current:
            parts.append(''.join(current))
        return parts
    
    def _extract_balanced_call(self, s: str, start: int) -> str:
        """Extract a balanced function call starting at position start."""
        depth = 0
        i = start
        while i < len(s):
            if s[i] == '(':
                depth += 1
            elif s[i] == ')':
                depth -= 1
                if depth == 0:
                    return s[start:i+1]
            i += 1
        return s[start:]
    
    def _parse_aux_call(self, call_str: str) -> tuple[list[list[str]], list[str]] | None:
        """Parse Literal.AuxCall(body_cubes, qvars).

        body_cubes is Vec[Formula] where each element is Formula.grouped_and_lit(Set[Literal]).
        Returns (cubes_as_asp, free_vars) where cubes_as_asp is a list of cubes,
        each cube being a list of ASP literal strings, and free_vars is derived by
        collecting all variables from the cubes then removing the quantified vars (qvars).
        Returns None if can't parse.
        """
        import ast as pyast

        try:
            expr = pyast.parse(call_str, mode="eval").body
        except SyntaxError:
            return None

        if not isinstance(expr, pyast.Call):
            return None

        # Check it's Literal.AuxCall
        func = expr.func
        if not (isinstance(func, pyast.Attribute) and
                isinstance(func.value, pyast.Name) and
                func.value.id == "Literal" and func.attr == "AuxCall"):
            return None

        if len(expr.args) != 2:
            return None

        body_cubes_node, qvars_node = expr.args

        # Parse body_cubes (Vec[Formula]): each element is Formula.grouped_and_lit(Set[Literal])
        cube_nodes = self._parse_vec_call(body_cubes_node)
        cubes_asp = []
        all_vars: list[str] = []
        for cube_node in cube_nodes:
            lit_nodes = self._parse_grouped_and_lit(cube_node)
            if lit_nodes is None:
                return None
            cube_lits = [self._literal_to_asp(lit) for lit in lit_nodes]
            cubes_asp.append(cube_lits)
            all_vars.extend(self._vars_in_lit_nodes(lit_nodes))

        # Parse qvars (Set[Term]) — the quantified (existential) variables
        qvar_nodes = self._parse_set_call(qvars_node)
        qvars = {v for v in (self._extract_var_name(n) for n in qvar_nodes) if v is not None}

        # free_vars = all vars appearing in cubes, minus the quantified vars
        seen: set[str] = set()
        free_vars: list[str] = []
        for v in all_vars:
            if v not in qvars and v not in seen:
                seen.add(v)
                free_vars.append(v)

        return cubes_asp, free_vars

    def _parse_vec_call(self, node) -> list:
        """Parse Vec[T](...) or Vec[T].empty() and return list of elements."""
        import ast as pyast

        if isinstance(node, pyast.Call):
            if isinstance(node.func, pyast.Attribute) and node.func.attr == "empty":
                return []
            return list(node.args)
        return []

    def _parse_grouped_and_lit(self, node) -> list | None:
        """Parse a conjunction of literals in any form and return list of Literal AST nodes.

        Handles:
          - Formula.grouped_and_lit(Set[Literal](...))
          - Formula.And(a, b)   -- extractor picks And when it's cheaper than grouped_and_lit
          - Formula.Lit(GeneralLit.from_literal(Literal(...)))  -- single literal
        """
        import ast as pyast

        if not isinstance(node, pyast.Call):
            return None
        func = node.func
        if not isinstance(func, pyast.Attribute):
            return None
        cls_name = func.value.id if isinstance(func.value, pyast.Name) else None
        method = func.attr

        if cls_name == "Formula" and method == "grouped_and_lit":
            # Formula.grouped_and_lit(Set[Literal](...))
            if len(node.args) != 1:
                return None
            return self._parse_set_call(node.args[0])

        if cls_name == "Formula" and method == "And":
            # Formula.And(left, right) — flatten recursively
            if len(node.args) != 2:
                return None
            left = self._parse_grouped_and_lit(node.args[0])
            right = self._parse_grouped_and_lit(node.args[1])
            if left is None or right is None:
                return None
            return left + right

        if cls_name == "Formula" and method == "Lit":
            # Formula.Lit(GeneralLit.from_literal(Literal(...))) — single literal
            if len(node.args) != 1:
                return None
            gl_node = node.args[0]
            lit_node = self._unwrap_from_literal(gl_node)
            if lit_node is None:
                return None
            return [lit_node]

        return None

    def _unwrap_from_literal(self, node):
        """Unwrap GeneralLit.from_literal(Literal(...)) and return the Literal node."""
        import ast as pyast

        if not isinstance(node, pyast.Call):
            return None
        func = node.func
        if (isinstance(func, pyast.Attribute) and
                isinstance(func.value, pyast.Name) and
                func.value.id == "GeneralLit" and func.attr == "from_literal"):
            if len(node.args) == 1:
                return node.args[0]
        return None
    
    def _vars_in_lit_nodes(self, lit_nodes: list) -> list[str]:
        """Collect all variable names from a list of Literal AST nodes by traversing the AST."""
        vars_found: list[str] = []
        for lit_node in lit_nodes:
            self._collect_vars_from_node(lit_node, vars_found)
        return vars_found

    def _collect_vars_from_node(self, node, result: list[str]) -> None:
        """Recursively collect Term.Var names from an AST node."""
        import ast as pyast

        if not isinstance(node, pyast.AST):
            return
        # Check for Term.Var("name")
        if (isinstance(node, pyast.Call) and
                isinstance(node.func, pyast.Attribute) and
                isinstance(node.func.value, pyast.Name) and
                node.func.value.id == "Term" and node.func.attr == "Var"):
            if node.args and isinstance(node.args[0], pyast.Constant):
                result.append(node.args[0].value)
            return
        # Recurse into all child nodes
        for child in pyast.iter_child_nodes(node):
            self._collect_vars_from_node(child, result)

    def _parse_set_call(self, node) -> list:
        """Parse Set[T](...) or Set[T].empty() and return list of elements."""
        import ast as pyast
        
        if isinstance(node, pyast.Call):
            # Could be Set[T](...) or Set[T].empty()
            if isinstance(node.func, pyast.Attribute) and node.func.attr == "empty":
                return []
            # Set[T](elem1, elem2, ...)
            return list(node.args)
        return []
    
    def _extract_var_name(self, node) -> str | None:
        """Extract variable name from Term.Var("X") node."""
        import ast as pyast
        
        if isinstance(node, pyast.Call):
            func = node.func
            if (isinstance(func, pyast.Attribute) and 
                isinstance(func.value, pyast.Name) and
                func.value.id == "Term" and func.attr == "Var"):
                if len(node.args) == 1 and isinstance(node.args[0], pyast.Constant):
                    return node.args[0].value
        return None
    
    def _literal_to_asp(self, node) -> str:
        """Convert a Literal(...) AST node to ASP string."""
        import ast as pyast
        
        if not isinstance(node, pyast.Call):
            return "?"
        
        func = node.func
        # Literal(atom, sign)
        if isinstance(func, pyast.Name) and func.id == "Literal":
            if len(node.args) != 2:
                return "?"
            atom_node, sign_node = node.args
            atom_str = self._atom_to_asp(atom_node)
            sign = sign_node.value if isinstance(sign_node, pyast.Constant) else True
            if sign:
                return atom_str
            else:
                return f"not {atom_str}"
        return "?"
    
    def _atom_to_asp(self, node) -> str:
        """Convert an Atom.Pred(...) or Atom.Comp(...) AST node to ASP string."""
        import ast as pyast
        
        if not isinstance(node, pyast.Call):
            return "?"
        
        func = node.func
        if isinstance(func, pyast.Attribute) and isinstance(func.value, pyast.Name):
            if func.value.id == "Atom" and func.attr == "Pred":
                # Atom.Pred(name, varlist)
                if len(node.args) != 2:
                    return "?"
                name = node.args[0].value if isinstance(node.args[0], pyast.Constant) else "?"
                args = self._parse_varlist(node.args[1])
                if args:
                    return f"{name}({', '.join(args)})"
                else:
                    return name
            elif func.value.id == "Atom" and func.attr == "Comp":
                # Atom.Comp(op, left, right)
                if len(node.args) != 3:
                    return "?"
                op = node.args[0].value if isinstance(node.args[0], pyast.Constant) else "?"
                if op == "==":
                    op = "="
                left = self._term_to_asp(node.args[1])
                right = self._term_to_asp(node.args[2])
                return f"{left} {op} {right}"
        return "?"
    
    def _parse_varlist(self, node) -> list[str]:
        """Parse cons_var/nil_var varlist to list of ASP terms."""
        import ast as pyast
        
        result = []
        current = node
        while True:
            if isinstance(current, pyast.Call):
                func = current.func
                if isinstance(func, pyast.Name) and func.id == "nil_var":
                    break
                elif isinstance(func, pyast.Name) and func.id == "cons_var":
                    if len(current.args) >= 2:
                        result.append(self._term_to_asp(current.args[0]))
                        current = current.args[1]
                    else:
                        break
                else:
                    break
            else:
                break
        return result
    
    def _term_to_asp(self, node) -> str:
        """Convert a Term AST node to ASP string."""
        import ast as pyast
        
        if isinstance(node, pyast.Constant):
            return str(node.value)
        
        if isinstance(node, pyast.Call):
            func = node.func
            if isinstance(func, pyast.Attribute) and isinstance(func.value, pyast.Name):
                if func.value.id == "Term":
                    if func.attr == "Var":
                        if len(node.args) == 1 and isinstance(node.args[0], pyast.Constant):
                            return node.args[0].value
                    elif func.attr == "Const":
                        if len(node.args) == 1 and isinstance(node.args[0], pyast.Constant):
                            return str(node.args[0].value)
                    elif func.attr == "Id":
                        if len(node.args) == 1 and isinstance(node.args[0], pyast.Constant):
                            return node.args[0].value
                    elif func.attr == "Int":
                        if len(node.args) == 1 and isinstance(node.args[0], pyast.Constant):
                            return str(node.args[0].value)
                    elif func.attr == "Symbol":
                        if len(node.args) == 1 and isinstance(node.args[0], pyast.Constant):
                            return str(node.args[0].value)
                    elif func.attr == "Anon":
                        return "_"
                    elif func.attr == "BinaryExpr":
                        # Term.BinaryExpr(op, left, right)
                        if len(node.args) == 3:
                            op = node.args[0].value if isinstance(node.args[0], pyast.Constant) else "?"
                            left = self._term_to_asp(node.args[1])
                            right = self._term_to_asp(node.args[2])
                            return f"({left} {op} {right})"
        return "?"
    
    def _generate_aux_rule(self, aux_name: str, body_lits: list[str], free_vars: list[str]) -> str:
        """Generate aux predicate rule: aux_name(free_vars) :- body_lits."""
        if free_vars:
            head = f"{aux_name}({', '.join(free_vars)})"
        else:
            head = aux_name
        
        if body_lits:
            body = ", ".join(body_lits)
            return f"{head} :- {body}."
        else:
            return f"{head}."
    
    def _generate_aux_literal(self, aux_name: str, free_vars: list[str]) -> str:
        """Generate egg Literal expression for aux predicate call."""
        # Build varlist: cons_var(Term.Var("X"), cons_var(Term.Var("Y"), nil_var()))
        if free_vars:
            varlist = "nil_var()"
            for v in reversed(free_vars):
                varlist = f'cons_var(Term.Var("{v}"), {varlist})'
        else:
            varlist = "nil_var()"
        
        return f'Literal(Atom.Pred("{aux_name}", {varlist}), True)'

    def _generate_entailment_ruleset(self):
        """
        Generate dynamic rewrite rules for each entailment.
        This allows egglog's variable unification to handle matching automatically.
        Returns a Ruleset (not a Schedule) so it can be combined with equal_set.
        """
        ent_ruleset = ruleset()
        count = 0
        
        if self.verbose:
            print("Generating entailment rewrite rules...")
        
        for pred_name, pred_info in self.checker.predicates.items():
            if pred_info.is_external or not pred_info.entailments:
                continue
            
            for ent_info in pred_info.entailments:
                # Create egglog *pattern variables* for matching any Term
                # (Do NOT use Term.Var("v0") etc; those are concrete terms.)
                pattern_vars: list[Term] = [var(f"{pred_name}_{count}_v{i}", Term) for i in range(pred_info.arity)]
                
                # Build the entailed atom pattern with mapped variables
                entailed_pred_name = ent_info.body_atom.predicate.name
                entailed_var_list = []
                for arg in ent_info.body_atom.args:
                    if isinstance(arg, nodes.Variable) and arg.name in ent_info.var_mapping:
                        pos = ent_info.var_mapping[arg.name]
                        entailed_var_list.append(pattern_vars[pos])
                    else:
                        # Handle constants
                        entailed_var_list.append(to_egg(arg))
                
                # Create the entailing and entailed atoms
                entailing_atom = Atom.Pred(pred_name, pattern_vars)
                entailed_atom = Atom.Pred(entailed_pred_name, entailed_var_list)

                # Canonical literal representation used throughout the converter/extractor.
                entailing_glit = GeneralLit.from_literal(Literal(entailing_atom, True))
                entailed_glit = GeneralLit.from_literal(Literal(entailed_atom, True))
                
                # Append rewrite rules directly to the ruleset.
                # We target the binary `And` form. This is the representation used
                # before the extractor groups conjunctions into `grouped_and` and
                # materializes integrity constraints.
                r_and = rewrite(
                    Formula.And(
                        Formula.Lit(entailing_glit),
                        Formula.Lit(entailed_glit),
                    )
                ).to(Formula.Lit(entailing_glit))
                ent_ruleset.append(r_and)

                count += 1
                if self.verbose:
                    print(f"  Rule: {Literal(entailing_atom, True)} ∧ {Literal(entailed_atom, True)}  => {Literal(entailing_atom, True)}")
        
        if count > 0:
            if self.verbose:
                print(f"Generated {count} entailment rules.\n")
            return ent_ruleset
        return None

    def _export_entailment_specs(self) -> dict[str, list[tuple[str, tuple[int, ...]]]]:
        """Entailments for the transpiler (see ``parsing.checker.export_entailment_specs``)."""
        if not self.checker:
            return {}
        return export_entailment_specs(self.checker)

    def _export_pred_arg_types(self) -> dict[str, tuple[str, ...]]:
        """Predicate argument domains (see ``parsing.checker.export_pred_arg_types``)."""
        if not self.checker:
            return {}
        return export_pred_arg_types(self.checker)

