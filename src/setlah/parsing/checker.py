'''
The checker module performs semantic analysis on the AST.

This module performs:
1. Domain and type checking
2. Predicate signature inference and validation
3. Dependency graph construction for rules
4. Variable type unification within formulas
5. Symbol tables collection for optimization
6. Predicate flow information for later compilation stages
'''

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple, Any
from ..ast import nodes


@dataclass
class DomainInfo:
    """Information about a declared domain."""
    name: str
    type_def: nodes.TypeNode
    values: Optional[Any] = None  # SetEnum values or IntRange


@dataclass
class EntailmentInfo:
    """
    Information about a body literal entailed by specific head arguments.
    Maps head argument positions to body literals.
    """
    body_atom: nodes.PredAtom  # The entailed body literal
    head_arg_positions: Tuple[int, ...]  # Which head argument positions are involved
    var_mapping: Dict[str, int]  # Maps variable names to head positions
    
    def __repr__(self):
        pred_str = f"{self.body_atom.predicate.name}("
        arg_strs = []
        for arg in self.body_atom.args:
            if isinstance(arg, nodes.Variable) and arg.name in self.var_mapping:
                arg_strs.append(f"${self.var_mapping[arg.name]}")
            else:
                arg_strs.append(str(arg))
        pred_str += ", ".join(arg_strs) + ")"
        return f"{pred_str} via args{self.head_arg_positions}"


@dataclass
class PredicateInfo:
    """Information about a predicate."""
    name: str
    arity: int
    arg_types: List[str]  # Domain names for each argument
    defined_in_blocks: List[int] = field(default_factory=list)  # Block indices where defined
    depends_on: Set[str] = field(default_factory=set)  # Other predicates it depends on
    entailments: List[EntailmentInfo] = field(default_factory=list)  # Position-specific entailments
    is_external: bool = False
    canonical_args: List[str] = field(default_factory=list)  # Canonical arg names from first rule head
    
    def __repr__(self):
        deps = f", depends_on={self.depends_on}" if self.depends_on else ""
        blocks = f", blocks={self.defined_in_blocks}" if self.defined_in_blocks else ""
        ext = " [EXTERNAL]" if self.is_external else ""
        entail_str = ""
        if self.entailments:
            entail_strs = [str(ent) for ent in self.entailments]
            entail_str = f"\n    entails: {', '.join(entail_strs)}"
        return f"{self.name}/{self.arity}: ({', '.join(self.arg_types)}){ext}{blocks}{deps}{entail_str}"


class SemanticChecker:
    def __init__(self, verbose: bool = False):
        self.domains: Dict[str, DomainInfo] = {}
        self.predicates: Dict[str, PredicateInfo] = {}
        self.constants: Dict[str, Tuple[str, Optional[Any]]] = {}  # name -> (type, value)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.current_block_idx = 0
        self.verbose = verbose
        
    def check_program(self, program: nodes.Program) -> bool:
        """
        Main entry point for checking a program.
        Returns True if no errors, False otherwise.
        """
        # Phase 1: Collect domain and external predicate declarations
        for decl in program.domains:
            self._process_domain_decl(decl)
        
        # Phase 2: Process each block
        for block_idx, block in enumerate(program.blocks):
            self.current_block_idx = block_idx
            self._process_block(block)
        
        # Phase 3: Validate that all used predicates are defined
        self._validate_all_predicates_defined()
        
        # Report results
        if self.errors:
            print("\n=== SEMANTIC ERRORS ===")
            for err in self.errors:
                print(f"  ERROR: {err}")

        if self.warnings and self.verbose:
            print("\n=== WARNINGS ===")
            for warn in self.warnings:
                print(f"  WARNING: {warn}")

        if not self.errors and self.verbose:
            print("\n=== PREDICATE SUMMARY ===")
            for pred_name in sorted(self.predicates.keys()):
                print(f"  {self.predicates[pred_name]}")
        
        return len(self.errors) == 0
    
    def _process_domain_decl(self, decl: nodes.DomainDecl):
        """Process domain declarations (DefDOM, ExtDOM, ExtPred, ConstDecl)."""
        if isinstance(decl, nodes.DefDOM):
            domain_name = decl.var.name
            self.domains[domain_name] = DomainInfo(
                name=domain_name,
                type_def=decl.dtype,
                values=decl.set_def
            )
            # Automatically create domain membership predicate: dom_DomainName(DomainName)
            dom_pred_name = f"dom_{domain_name}"
            self.predicates[dom_pred_name] = PredicateInfo(
                name=dom_pred_name,
                arity=1,
                arg_types=[domain_name],
                is_external=True  # Domain predicates are implicitly external/built-in
            )
        
        elif isinstance(decl, nodes.ExtDOM):
            domain_name = decl.var.name
            self.domains[domain_name] = DomainInfo(
                name=domain_name,
                type_def=decl.dtype,
                values=None  # External, values from input
            )
            # Automatically create domain membership predicate: dom_DomainName(DomainName)
            dom_pred_name = f"dom_{domain_name}"
            self.predicates[dom_pred_name] = PredicateInfo(
                name=dom_pred_name,
                arity=1,
                arg_types=[domain_name],
                is_external=True  # Domain predicates are implicitly external/built-in
            )
        
        elif isinstance(decl, nodes.ExtPred):
            # Extract types from tuple_var
            arg_types = []
            for elem in decl.tuple_var.elements:
                if isinstance(elem, nodes.Variable):
                    # This should be a domain reference
                    if elem.name in self.domains:
                        arg_types.append(elem.name)
                    else:
                        self.errors.append(
                            f"External predicate {decl.name.name}: unknown domain '{elem.name}'"
                        )
                        arg_types.append("UNKNOWN")
                else:
                    self.errors.append(
                        f"External predicate {decl.name.name}: expected domain reference, got {type(elem)}"
                    )
                    arg_types.append("UNKNOWN")
            
            self.predicates[decl.name.name] = PredicateInfo(
                name=decl.name.name,
                arity=len(arg_types),
                arg_types=arg_types,
                is_external=True
            )
        
        elif isinstance(decl, nodes.ConstDecl):
            type_name = self._type_to_string(decl.dtype)
            self.constants[decl.name.name] = (type_name, decl.value)
    
    def _process_block(self, block: nodes.Block):
        """Process a block: infer types from rules, check constraints."""
        # First pass: collect all rule heads and infer their signatures
        for stmt in block.statements:
            if isinstance(stmt, nodes.Rule):
                self._process_rule(stmt)
        
        # Second pass: check constraints
        for stmt in block.statements:
            if isinstance(stmt, nodes.SetConstraint):
                self._process_constraint(stmt)
    
    def _process_rule(self, rule: nodes.Rule):
        """
        Process a rule: infer predicate signature from body literals,
        check consistency, build dependency graph, and compute entailments.
        """
        # Infer variable types from body
        var_types: Dict[str, str] = {}  # var_name -> domain_name
        body_preds: Set[str] = set()
        body_atoms: List[nodes.PredAtom] = []
        
        for lit in rule.body:
            if isinstance(lit, nodes.PredAtom):
                body_preds.add(lit.predicate.name)
                body_atoms.append(lit)
                self._infer_types_from_atom(lit, var_types)
            elif isinstance(lit, nodes.Comparison):
                # Comparisons don't contribute type info directly
                pass
        
        # Now check the head
        head_name = rule.head.predicate.name
        head_arg_types = []
        head_arg_names = []  # Ordered arg names for canonical_args
        head_vars: Set[str] = set()  # Variables in the head
        head_var_positions: Dict[str, int] = {}  # Maps variable name to position in head

        for pos, arg in enumerate(rule.head.args):
            if isinstance(arg, nodes.Variable):
                head_vars.add(arg.name)
                head_var_positions[arg.name] = pos
                head_arg_names.append(arg.name)
                if arg.name in var_types:
                    head_arg_types.append(var_types[arg.name])
                else:
                    self.errors.append(
                        f"Block {self.current_block_idx}: Variable '{arg.name}' in head of rule for '{head_name}' is not bound in body"
                    )
                    head_arg_types.append("UNKNOWN")
            elif isinstance(arg, nodes.Constant):
                # A literal may inhabit any compatible declared domain. The
                # concrete primitive type is not enough to choose between
                # multiple INT- or Symbol-backed domains, so preserve an
                # existing signature instead of manufacturing a conflict.
                head_arg_types.append("UNKNOWN")
                head_arg_names.append(str(arg.value))
            elif isinstance(arg, nodes.Identifier):
                # Could be a constant identifier
                if arg.name in self.constants:
                    head_arg_types.append(self.constants[arg.name][0])
                else:
                    self.warnings.append(
                        f"Block {self.current_block_idx}: Identifier '{arg.name}' in head of '{head_name}' not declared as constant"
                    )
                    head_arg_types.append("UNKNOWN")
                head_arg_names.append(arg.name)
            else:
                self.errors.append(
                    f"Block {self.current_block_idx}: Unsupported argument type in head: {type(arg)}"
                )
                head_arg_types.append("UNKNOWN")
        
        # Compute entailments: literals that use only head variables (or constants)
        entailment_infos = self._compute_entailments(body_atoms, head_vars, head_var_positions)
        
        # Check if predicate already exists
        if head_name in self.predicates:
            existing = self.predicates[head_name]
            if existing.is_external:
                self.errors.append(
                    f"Block {self.current_block_idx}: Cannot define external predicate '{head_name}'"
                )
            elif existing.arity != len(head_arg_types):
                self.errors.append(
                    f"Block {self.current_block_idx}: Arity mismatch for '{head_name}': expected {existing.arity}, got {len(head_arg_types)}"
                )
            else:
                # TODO: check if the logic here is complete
                # Unify types across multiple defining rules.
                # Treat UNKNOWN as a wildcard so mutually-informative rules can refine
                # a signature over time (common with recursion / partially-typed bodies).
                unified: List[str] = []
                for i, (exp, got) in enumerate(zip(existing.arg_types, head_arg_types)):
                    if exp == got:
                        unified.append(exp)
                        continue
                    if exp == "UNKNOWN" and got != "UNKNOWN":
                        unified.append(got)
                        continue
                    if got == "UNKNOWN" and exp != "UNKNOWN":
                        unified.append(exp)
                        continue
                    # Both known and different => conflict
                    self.errors.append(
                        f"Block {self.current_block_idx}: Type mismatch for '{head_name}' arg {i}: expected {exp}, got {got}"
                    )
                    unified.append(exp)

                existing.arg_types = unified
            
            # Update dependencies, entailments, and block info
            existing.depends_on.update(body_preds)
            # Merge entailments (keep unique)
            for ent_info in entailment_infos:
                if not any(self._entailments_equal(ent_info, existing_ent) 
                          for existing_ent in existing.entailments):
                    existing.entailments.append(ent_info)
            if self.current_block_idx not in existing.defined_in_blocks:
                existing.defined_in_blocks.append(self.current_block_idx)
        else:
            # New predicate
            self.predicates[head_name] = PredicateInfo(
                name=head_name,
                arity=len(head_arg_types),
                arg_types=head_arg_types,
                defined_in_blocks=[self.current_block_idx],
                depends_on=body_preds,
                entailments=entailment_infos,
                canonical_args=head_arg_names,
            )
    
    def _compute_entailments(self, body_atoms: List[nodes.PredAtom], head_vars: Set[str], 
                            head_var_positions: Dict[str, int]) -> List[EntailmentInfo]:
        """
        Compute which body literals are entailed by specific head argument positions.
        A literal is entailed if it uses only variables that appear in the head (or constants).
        
        Returns EntailmentInfo objects that map head positions to body literals.
        """
        entailments = []
        
        for atom in body_atoms:
            atom_vars = self._collect_atom_vars(atom)
            # Check if all variables in this atom are in the head
            if atom_vars.issubset(head_vars):
                # Build mapping from variable name to head position
                var_mapping = {}
                positions = []
                for var_name in atom_vars:
                    if var_name in head_var_positions:
                        var_mapping[var_name] = head_var_positions[var_name]
                        positions.append(head_var_positions[var_name])
                
                entailments.append(EntailmentInfo(
                    body_atom=atom,
                    head_arg_positions=tuple(sorted(positions)),
                    var_mapping=var_mapping
                ))
        
        return entailments
    
    def _collect_atom_vars(self, atom: nodes.PredAtom) -> Set[str]:
        """Collect all variables used in an atom."""
        vars_set = set()
        for arg in atom.args:
            if isinstance(arg, nodes.Variable):
                vars_set.add(arg.name)
            elif isinstance(arg, nodes.BinaryExpr):
                # Recursively collect from expressions
                vars_set.update(self._collect_expr_vars(arg))
        return vars_set
    
    def _collect_expr_vars(self, expr: nodes.ExprType) -> Set[str]:
        """Recursively collect variables from an expression."""
        if isinstance(expr, nodes.Variable):
            return {expr.name}
        elif isinstance(expr, nodes.BinaryExpr):
            left_vars = self._collect_expr_vars(expr.left)
            right_vars = self._collect_expr_vars(expr.right)
            return left_vars.union(right_vars)
        else:
            return set()
    
    def _entailments_equal(self, ent1: EntailmentInfo, ent2: EntailmentInfo) -> bool:
        """Check if two entailment infos are equal."""
        return (self._atoms_equal(ent1.body_atom, ent2.body_atom) and
                ent1.head_arg_positions == ent2.head_arg_positions)
    
    def _atoms_equal(self, atom1: nodes.PredAtom, atom2: nodes.PredAtom) -> bool:
        """Check if two atoms are structurally equal."""
        if atom1.predicate.name != atom2.predicate.name:
            return False
        if len(atom1.args) != len(atom2.args):
            return False
        for arg1, arg2 in zip(atom1.args, atom2.args):
            if not self._args_equal(arg1, arg2):
                return False
        return True
    
    def _args_equal(self, arg1, arg2) -> bool:
        """Check if two arguments are equal."""
        if type(arg1) != type(arg2):
            return False
        if isinstance(arg1, nodes.Variable):
            return arg1.name == arg2.name
        elif isinstance(arg1, nodes.Constant):
            return arg1.value == arg2.value
        elif isinstance(arg1, nodes.Identifier):
            return arg1.name == arg2.name
        elif isinstance(arg1, nodes.BinaryExpr):
            return (arg1.op == arg2.op and 
                    self._args_equal(arg1.left, arg2.left) and 
                    self._args_equal(arg1.right, arg2.right))
        return False
    
    def _infer_types_from_atom(self, atom: nodes.PredAtom, var_types: Dict[str, str]):
        """
        Infer variable types from a predicate atom.
        If predicate is known, propagate types; otherwise, collect constraints.
        """
        pred_name = atom.predicate.name
        
        if pred_name not in self.predicates:
            # Unknown predicate; we'll check later
            return
        
        pred_info = self.predicates[pred_name]
        
        if len(atom.args) != pred_info.arity:
            self.errors.append(
                f"Block {self.current_block_idx}: Arity mismatch for '{pred_name}': expected {pred_info.arity}, got {len(atom.args)}"
            )
            return
        
        for i, (arg, expected_type) in enumerate(zip(atom.args, pred_info.arg_types)):
            if isinstance(arg, nodes.Variable):
                if arg.name in var_types:
                    # Check consistency
                    if not self._types_compatible(var_types[arg.name], expected_type):
                        self.errors.append(
                            f"Block {self.current_block_idx}: Type conflict for variable '{arg.name}': inferred {var_types[arg.name]}, but '{pred_name}' arg {i} expects {expected_type}"
                        )
                else:
                    var_types[arg.name] = expected_type

    def _types_compatible(self, left: str, right: str) -> bool:
        """Return whether two nominal domains share a usable representation."""
        if left == right or left == "UNKNOWN" or right == "UNKNOWN":
            return True
        left_domain = self.domains.get(left)
        right_domain = self.domains.get(right)
        if left_domain is None or right_domain is None:
            return False
        return self._type_to_string(left_domain.type_def) == self._type_to_string(right_domain.type_def)
    
    def _process_constraint(self, constraint: nodes.SetConstraint):
        """
        Process a constraint: check that all variables are typed,
        and all predicates are defined.
        """
        # Process let expressions (set variables)
        for let_expr in constraint.let_exprs:
            # For now, just validate set expressions don't reference undefined things
            pass
        
        # Check the formula
        var_types: Dict[str, str] = {}
        self._check_foset(constraint.formula, var_types)
    
    def _check_foset(self, foset: nodes.FoSet, var_types: Dict[str, str]):
        """Recursively check a FoSet formula for type consistency and predicate definitions."""
        if isinstance(foset, nodes.PredAtom):
            pred_name = foset.predicate.name
            if pred_name not in self.predicates:
                self.errors.append(
                    f"Block {self.current_block_idx}: Undefined predicate '{pred_name}' in constraint"
                )
            else:
                self._infer_types_from_atom(foset, var_types)
        
        elif isinstance(foset, nodes.LogicalOp):
            for operand in foset.operands:
                self._check_foset(operand, var_types)
        
        elif isinstance(foset, nodes.QuantifiedFormula):
            # Introduce variable (we don't track its type in constraints unless bound by a predicate)
            self._check_foset(foset.body, var_types)
        
        elif isinstance(foset, nodes.Comparison):
            # Check that variables in comparisons are typed
            self._check_expr_typed(foset.left, var_types)
            self._check_expr_typed(foset.right, var_types)
        
        elif isinstance(foset, nodes.SetMembership):
            # Check set expression validity
            pass
        
        elif isinstance(foset, nodes.SetSubset):
            pass
        
        elif isinstance(foset, nodes.SetPartition):
            pass
        
        elif isinstance(foset, nodes.Aggregation):
            # Check set variable and expression
            pass
        
        elif isinstance(foset, nodes.BooleanConst):
            pass
        
        else:
            self.warnings.append(
                f"Block {self.current_block_idx}: Unhandled FoSet type: {type(foset)}"
            )
    
    def _check_expr_typed(self, expr: nodes.ExprType, var_types: Dict[str, str]):
        """Check that all variables in an expression are typed."""
        if isinstance(expr, nodes.Variable):
            if expr.name not in var_types:
                self.warnings.append(
                    f"Block {self.current_block_idx}: Variable '{expr.name}' in comparison may be unbound"
                )
        elif isinstance(expr, nodes.BinaryExpr):
            self._check_expr_typed(expr.left, var_types)
            self._check_expr_typed(expr.right, var_types)
        # Constants and identifiers are fine
    
    def _validate_all_predicates_defined(self):
        """Check that all predicates used in dependencies are actually defined."""
        for pred_name, pred_info in self.predicates.items():
            if pred_info.is_external:
                continue
            
            if not pred_info.defined_in_blocks:
                self.errors.append(
                    f"Predicate '{pred_name}' is used but never defined"
                )
            
            for dep_name in pred_info.depends_on:
                if dep_name not in self.predicates:
                    self.errors.append(
                        f"Predicate '{pred_name}' depends on undefined predicate '{dep_name}'"
                    )
    
    def _type_to_string(self, type_node: nodes.TypeNode) -> str:
        """Convert a TypeNode to a string representation."""
        if isinstance(type_node, nodes.IntType):
            return "INT"
        elif isinstance(type_node, nodes.SymbolType):
            return f"Symbol({type_node.name or ''})"
        elif isinstance(type_node, nodes.TupleType):
            subtypes = ", ".join(self._type_to_string(st) for st in type_node.subtypes)
            return f"Tuple({subtypes})"
        else:
            return str(type_node)


def check_program(program: nodes.Program) -> bool:
    """Convenience function to check a program."""
    checker = SemanticChecker()
    return checker.check_program(program) 
