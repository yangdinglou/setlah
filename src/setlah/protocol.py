"""Versioned JSON subprocess protocol for non-Python SetLaH clients."""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from . import __version__
from .engine import CompileOptions, EngineError, ErrorCategory, SolveOptions, compile_source, solve_source

PROTOCOL_VERSION = 1


def _expect_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EngineError(ErrorCategory.PROTOCOL, f"{label} must be a JSON object")
    return value


def _expect_source(request: dict[str, Any]) -> str:
    source = request.get("source")
    if not isinstance(source, str):
        raise EngineError(ErrorCategory.PROTOCOL, "source must be a string")
    return source


def _expect_facts(request: dict[str, Any]) -> list[str]:
    facts = request.get("facts", [])
    if not isinstance(facts, list) or not all(isinstance(item, str) for item in facts):
        raise EngineError(ErrorCategory.PROTOCOL, "facts must be an array of strings")
    return facts


def _bool_option(obj: dict[str, Any], name: str, default: bool) -> bool:
    value = obj.get(name, default)
    if not isinstance(value, bool):
        raise EngineError(ErrorCategory.PROTOCOL, f"options.{name} must be a boolean")
    return value


def _compile_options(raw: Any) -> CompileOptions:
    obj = _expect_object(raw or {}, "options")
    try:
        return CompileOptions(
            grounding=_bool_option(obj, "grounding", False),
            cost_conversion=_bool_option(obj, "costConversion", False),
            entailment_elim=obj.get("entailmentElim", "asp"),
            verbose=_bool_option(obj, "verbose", False),
        )
    except (TypeError, ValueError) as exc:
        raise EngineError(ErrorCategory.PROTOCOL, str(exc)) from exc


def _solve_options(raw: Any) -> SolveOptions:
    obj = _expect_object(raw or {}, "options")
    args = obj.get("clingoArguments", [])
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise EngineError(ErrorCategory.PROTOCOL, "options.clingoArguments must be an array of strings")
    max_models = obj.get("maxModels", 1)
    if not isinstance(max_models, int) or isinstance(max_models, bool):
        raise EngineError(ErrorCategory.PROTOCOL, "options.maxModels must be an integer")
    try:
        return SolveOptions(
            compile=_compile_options(obj),
            max_models=max_models,
            clingo_arguments=tuple(args),
        )
    except (TypeError, ValueError) as exc:
        raise EngineError(ErrorCategory.PROTOCOL, str(exc)) from exc


def _success(**payload: Any) -> dict[str, Any]:
    return {"ok": True, "protocol": PROTOCOL_VERSION, "engineVersion": __version__, **payload}


def handle_request(request: Any) -> dict[str, Any]:
    request = _expect_object(request, "request")
    version = request.get("protocol")
    if not isinstance(version, int) or isinstance(version, bool) or version != PROTOCOL_VERSION:
        raise EngineError(
            ErrorCategory.PROTOCOL,
            f"unsupported protocol version {version!r}; expected {PROTOCOL_VERSION}",
        )
    operation = request.get("operation")
    if operation == "version":
        return _success()
    if operation == "capabilities":
        return _success(capabilities={
            "operations": ["compile", "solve", "version", "capabilities"],
            "inMemoryFacts": True,
            "structuredSymbols": True,
            "defaultMaxModels": 1,
        })
    if operation == "compile":
        result = compile_source(
            _expect_source(request), _expect_facts(request), _compile_options(request.get("options"))
        )
        return _success(asp=result.asp, diagnostics=list(result.diagnostics))
    if operation == "solve":
        result = solve_source(
            _expect_source(request), _expect_facts(request), _solve_options(request.get("options"))
        )
        return _success(
            status=result.status.value,
            models=[model.to_dict() for model in result.models],
            diagnostics=list(result.diagnostics),
        )
    raise EngineError(ErrorCategory.PROTOCOL, f"unknown operation: {operation!r}")


def protocol_main(stdin: TextIO | None = None, stdout: TextIO | None = None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    try:
        response = handle_request(json.load(stdin))
        exit_code = 0
    except EngineError as exc:
        response = {
            "ok": False,
            "protocol": PROTOCOL_VERSION,
            "engineVersion": __version__,
            "error": {"category": exc.category.value, "message": exc.message},
        }
        exit_code = 1
    except Exception as exc:
        response = {
            "ok": False,
            "protocol": PROTOCOL_VERSION,
            "engineVersion": __version__,
            "error": {"category": ErrorCategory.PROTOCOL.value, "message": str(exc)},
        }
        exit_code = 1
    json.dump(response, stdout, separators=(",", ":"), sort_keys=True)
    stdout.write("\n")
    return exit_code
