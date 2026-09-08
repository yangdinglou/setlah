"""Direct, syntax-directed lowering of SetLaH to the transpiler's IR (no egglog)."""

from .lower import DirectLowerer

__all__ = ["DirectLowerer"]
