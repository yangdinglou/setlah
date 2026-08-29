"""Ergonomic in-process API for embedding SetLaH in Python applications."""

from __future__ import annotations

import contextlib
import io
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TypeAlias

from .engine import (
    CompileOptions,
    CompileResult,
    EngineError,
    ErrorCategory,
    SolveOptions,
    SolveResult,
    Symbol,
    SymbolKind,
    compile_source,
    solve_source,
)
from .parsing.parser import Parser


_IDENTIFIER = re.compile(r"^[a-z][A-Za-z0-9_]*$")


def _check_identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(
            f"{label} must be an ASP identifier beginning with a lowercase letter: {value!r}"
        )
    return value


TermInput: TypeAlias = int | Symbol


def number(value: int) -> Symbol:
    """Create an integer term."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("number value must be an integer")
    return Symbol(SymbolKind.NUMBER, number=value)


def string(value: str) -> Symbol:
    """Create a quoted ASP string term."""
    if not isinstance(value, str):
        raise TypeError("string value must be a Python string")
    return Symbol(SymbolKind.STRING, string=value)


def function(
    name: str,
    *arguments: TermInput,
    positive: bool = True,
) -> Symbol:
    """Create a symbolic constant or nested ASP function term."""
    _check_identifier(name, "function name")
    if not isinstance(positive, bool):
        raise TypeError("function positive flag must be a boolean")
    return Symbol(
        SymbolKind.FUNCTION,
        name=name,
        arguments=tuple(_coerce_term(argument) for argument in arguments),
        positive=positive,
    )


def symbol(name: str) -> Symbol:
    """Create an unquoted symbolic constant such as ``red``."""
    return function(name)


def _coerce_term(value: TermInput) -> Symbol:
    if isinstance(value, bool):
        raise TypeError("booleans are not ASP integer terms")
    if isinstance(value, int):
        return number(value)
    if isinstance(value, Symbol):
        return value
    raise TypeError(
        "fact arguments must be integers or typed terms from number(), "
        "string(), symbol(), or function()"
    )


@dataclass(frozen=True)
class Atom:
    """A typed ASP fact that can be attached to an :class:`Instance`."""

    name: str
    arguments: tuple[Symbol, ...] = ()
    positive: bool = True

    def __post_init__(self) -> None:
        _check_identifier(self.name, "atom name")
        object.__setattr__(
            self,
            "arguments",
            tuple(_coerce_term(argument) for argument in self.arguments),
        )
        if not isinstance(self.positive, bool):
            raise TypeError("atom positive flag must be a boolean")

    @classmethod
    def create(
        cls,
        name: str,
        *arguments: TermInput,
        positive: bool = True,
    ) -> Atom:
        return cls(name, tuple(_coerce_term(value) for value in arguments), positive)

    def render(self) -> str:
        return Symbol(
            SymbolKind.FUNCTION,
            name=self.name,
            arguments=self.arguments,
            positive=self.positive,
        ).render()


def atom(
    name: str,
    *arguments: TermInput,
    positive: bool = True,
) -> Atom:
    """Create a typed atom for later use with :meth:`Instance.add_atom`."""
    return Atom.create(name, *arguments, positive=positive)


@dataclass(frozen=True)
class Program:
    """Parsed SetLaH source ready to instantiate, compile, or solve."""

    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, str):
            raise TypeError("program source must be a string")
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                Parser().parse(self.source)
        except Exception as exc:
            raise EngineError(ErrorCategory.PARSE, str(exc)) from exc

    @classmethod
    def from_file(cls, path: str | Path) -> Program:
        return cls(Path(path).read_text(encoding="utf-8"))

    def instance(self) -> Instance:
        return Instance(self)

    def compile(self, options: CompileOptions | None = None) -> CompileResult:
        return compile_source(self.source, options=options)

    def solve(self, options: SolveOptions | None = None) -> SolveResult:
        return solve_source(self.source, options=options)


@dataclass(frozen=True)
class Instance:
    """A SetLaH program paired with immutable in-memory ASP input facts."""

    program: Program
    fact_sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.program, Program):
            raise TypeError("instance program must be a setlah.Program")
        if not all(isinstance(source, str) for source in self.fact_sources):
            raise TypeError("fact sources must be strings")

    def add_raw_facts(self, source: str) -> Instance:
        """Return a new instance with arbitrary Clingo source appended."""
        if not isinstance(source, str):
            raise TypeError("raw fact source must be a string")
        return replace(self, fact_sources=(*self.fact_sources, source))

    def add_atom(self, atom: Atom) -> Instance:
        if not isinstance(atom, Atom):
            raise TypeError("add_atom expects a setlah.Atom")
        return self.add_raw_facts(atom.render() + ".")

    def add_fact(
        self,
        name: str,
        *arguments: TermInput,
        positive: bool = True,
    ) -> Instance:
        return self.add_atom(Atom.create(name, *arguments, positive=positive))

    def add_const(self, name: str, value: TermInput) -> Instance:
        _check_identifier(name, "constant name")
        return self.add_raw_facts(f"#const {name}={_coerce_term(value).render()}.")

    def compile(self, options: CompileOptions | None = None) -> CompileResult:
        return compile_source(self.program.source, self.fact_sources, options)

    def solve(self, options: SolveOptions | None = None) -> SolveResult:
        return solve_source(self.program.source, self.fact_sources, options)
