"""SetLaH language implementation."""

__version__ = "0.1.0rc1"

from .api import (  # noqa: E402
    Atom,
    Instance,
    Program,
    atom,
    function,
    number,
    string,
    symbol,
)

from .engine import (  # noqa: E402
    CompileOptions,
    CompileResult,
    EngineError,
    ErrorCategory,
    Model,
    SolveOptions,
    SolveResult,
    SolveStatus,
    Symbol,
    SymbolKind,
    compile_source,
    solve_source,
)

__all__ = [
    "Atom",
    "CompileOptions",
    "CompileResult",
    "EngineError",
    "ErrorCategory",
    "Instance",
    "Model",
    "Program",
    "SolveOptions",
    "SolveResult",
    "SolveStatus",
    "Symbol",
    "SymbolKind",
    "atom",
    "compile_source",
    "function",
    "number",
    "solve_source",
    "string",
    "symbol",
]
