"""Stable in-memory compilation and solving API for SetLaH clients."""

from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

import clingo
import clingo.ast

from .parsing.checker import SemanticChecker
from .parsing.parser import Parser
from .rewrite.rw import Rewriter
from .transpile import transpile_program_to_asp, transpile_program_to_clingo


class ErrorCategory(str, Enum):
    PROTOCOL = "protocol"
    PARSE = "parse"
    SEMANTIC_CHECK = "semantic-check"
    COMPILE = "compile"
    GROUNDING = "grounding"
    SOLVE = "solve"


class EngineError(RuntimeError):
    def __init__(self, category: ErrorCategory, message: str):
        super().__init__(message)
        self.category = category
        self.message = message


@dataclass(frozen=True)
class CompileOptions:
    grounding: bool = False
    cost_conversion: bool = False
    entailment_elim: str = "asp"
    verbose: bool = False

    def __post_init__(self) -> None:
        if self.entailment_elim not in {"asp", "egg", "both", "none"}:
            raise ValueError("entailment_elim must be asp, egg, both, or none")


@dataclass(frozen=True)
class SolveOptions:
    compile: CompileOptions = field(default_factory=CompileOptions)
    max_models: int = 1
    clingo_arguments: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.max_models < 0:
            raise ValueError("max_models must be non-negative; use 0 for all models")


@dataclass(frozen=True)
class CompileResult:
    asp: str
    diagnostics: tuple[str, ...] = ()


class SymbolKind(str, Enum):
    INFIMUM = "infimum"
    NUMBER = "number"
    STRING = "string"
    FUNCTION = "function"
    SUPREMUM = "supremum"


@dataclass(frozen=True)
class Symbol:
    kind: SymbolKind
    number: int | None = None
    string: str | None = None
    name: str | None = None
    arguments: tuple["Symbol", ...] = ()
    positive: bool = True

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"kind": self.kind.value}
        if self.kind is SymbolKind.NUMBER:
            result["value"] = self.number
        elif self.kind is SymbolKind.STRING:
            result["value"] = self.string
        elif self.kind is SymbolKind.FUNCTION:
            result.update(
                name=self.name,
                arguments=[argument.to_dict() for argument in self.arguments],
                positive=self.positive,
            )
        return result

    def render(self) -> str:
        if self.kind is SymbolKind.INFIMUM:
            return "#inf"
        if self.kind is SymbolKind.SUPREMUM:
            return "#sup"
        if self.kind is SymbolKind.NUMBER:
            return str(self.number)
        if self.kind is SymbolKind.STRING:
            escaped = (self.string or "").replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        prefix = "" if self.positive else "-"
        if not self.arguments:
            return prefix + (self.name or "")
        args = ",".join(argument.render() for argument in self.arguments)
        return f"{prefix}{self.name}({args})"


@dataclass(frozen=True)
class Model:
    symbols: tuple[Symbol, ...]
    cost: tuple[int, ...] = ()
    optimality_proven: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbols": [symbol.to_dict() for symbol in self.symbols],
            "cost": list(self.cost),
            "optimalityProven": self.optimality_proven,
        }


class SolveStatus(str, Enum):
    SATISFIABLE = "satisfiable"
    UNSATISFIABLE = "unsatisfiable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SolveResult:
    status: SolveStatus
    models: tuple[Model, ...]
    diagnostics: tuple[str, ...] = ()

    @property
    def satisfiable(self) -> bool:
        return self.status is SolveStatus.SATISFIABLE


def _symbol_from_clingo(symbol: clingo.Symbol) -> Symbol:
    if symbol.type is clingo.SymbolType.Infimum:
        return Symbol(SymbolKind.INFIMUM)
    if symbol.type is clingo.SymbolType.Supremum:
        return Symbol(SymbolKind.SUPREMUM)
    if symbol.type is clingo.SymbolType.Number:
        return Symbol(SymbolKind.NUMBER, number=symbol.number)
    if symbol.type is clingo.SymbolType.String:
        return Symbol(SymbolKind.STRING, string=symbol.string)
    if symbol.type is clingo.SymbolType.Function:
        return Symbol(
            SymbolKind.FUNCTION,
            name=symbol.name,
            arguments=tuple(_symbol_from_clingo(arg) for arg in symbol.arguments),
            positive=symbol.positive,
        )
    raise EngineError(ErrorCategory.SOLVE, f"unsupported Clingo symbol type: {symbol.type}")


def _parse_and_rewrite(source: str, options: CompileOptions) -> tuple[Any, tuple[str, ...]]:
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):
            program = Parser().parse(source)
    except Exception as exc:
        raise EngineError(ErrorCategory.PARSE, str(exc)) from exc

    checker = SemanticChecker(verbose=options.verbose)
    with contextlib.redirect_stdout(captured):
        valid = checker.check_program(program)
    if not valid:
        raise EngineError(ErrorCategory.SEMANTIC_CHECK, "\n".join(checker.errors))

    try:
        rewriter = Rewriter(
            verbose=options.verbose,
            entailment_elim=options.entailment_elim,
            enable_cost_conversion=options.cost_conversion,
        )
        with contextlib.redirect_stdout(captured):
            rewritten = rewriter.rewrite_program(program, convert_only=False)
    except Exception as exc:
        raise EngineError(ErrorCategory.COMPILE, str(exc)) from exc

    diagnostics = tuple(
        line for line in captured.getvalue().splitlines() if line.strip()
    ) + tuple(checker.warnings)
    return rewritten, diagnostics


def compile_source(
    source: str,
    facts: Iterable[str] = (),
    options: CompileOptions | None = None,
) -> CompileResult:
    """Compile SetLaH and optional in-memory ASP facts to one ASP program."""
    options = options or CompileOptions()
    rewritten, diagnostics = _parse_and_rewrite(source, options)
    try:
        asp = transpile_program_to_asp(rewritten, grounding=options.grounding)
    except Exception as exc:
        raise EngineError(ErrorCategory.COMPILE, str(exc)) from exc

    fact_parts = [part.rstrip() for part in facts if part.strip()]
    if fact_parts:
        asp = asp.rstrip() + "\n\n" + "\n".join(fact_parts) + "\n"
    return CompileResult(asp=asp, diagnostics=diagnostics)


def solve_source(
    source: str,
    facts: Iterable[str] = (),
    options: SolveOptions | None = None,
) -> SolveResult:
    """Compile and solve SetLaH source without filesystem intermediates."""
    options = options or SolveOptions()
    rewritten, diagnostics = _parse_and_rewrite(source, options.compile)
    try:
        transpiled = transpile_program_to_clingo(
            rewritten, grounding=options.compile.grounding
        )
    except Exception as exc:
        raise EngineError(ErrorCategory.COMPILE, str(exc)) from exc

    arguments = list(options.clingo_arguments)
    has_model_limit = any(
        argument in {"-n", "--models"} or argument.startswith("--models=")
        for argument in arguments
    )
    if not has_model_limit:
        arguments[0:0] = ["-n", str(options.max_models)]
    try:
        control = clingo.Control(arguments)
    except Exception as exc:
        raise EngineError(ErrorCategory.SOLVE, str(exc)) from exc
    try:
        with clingo.ast.ProgramBuilder(control) as builder:
            for node in transpiled.ast:
                builder.add(node)
            for fact_source in facts:
                clingo.ast.parse_string(fact_source, builder.add)
        control.ground([("base", [])])
    except Exception as exc:
        raise EngineError(ErrorCategory.GROUNDING, str(exc)) from exc

    models: list[Model] = []

    def on_model(model: clingo.Model) -> None:
        models.append(
            Model(
                symbols=tuple(_symbol_from_clingo(s) for s in model.symbols(shown=True)),
                cost=tuple(model.cost),
                optimality_proven=model.optimality_proven,
            )
        )

    try:
        result = control.solve(on_model=on_model)
    except Exception as exc:
        raise EngineError(ErrorCategory.SOLVE, str(exc)) from exc

    if result.satisfiable:
        status = SolveStatus.SATISFIABLE
    elif result.unsatisfiable:
        status = SolveStatus.UNSATISFIABLE
    else:
        status = SolveStatus.UNKNOWN
    return SolveResult(status=status, models=tuple(models), diagnostics=diagnostics)
