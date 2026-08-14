"""
Normalize
=========

String normalization and splitting utilities for egg expressions.
"""

from __future__ import annotations

import re

from .ir import TranspileError


# =============================================================================
# 3. POST-PROCESSING UTILITIES (string normalization / splitting)
# =============================================================================


def _normalize_extracted_egg_str(s: str) -> str:
    """Normalize egglog's pretty-printed extracted expressions.

    egglog may print auxiliary bindings like:

        (_VarList_1 = cons_var(...), _VarList_2 = ..., Block(... _VarList_1 ...))

    which is not valid Python syntax (due to `=`). We rewrite it into a pure
    expression by substituting the bound names into the final expression.
    """
    s = s.strip()

    # Fast path: already a pure expression.
    if "=" not in s and "Block(" in s:
        return s

    # Prefer a robust strategy: extract the actual Block(...) call (ignoring any trailing cost/id)
    # and substitute any auxiliary bindings that appear before it.
    block_start = s.find("Block(")
    if block_start != -1:
        block_expr = _extract_balanced_call(s, block_start)
        prefix = s[:block_start]
        # egglog may log bindings as "Registering [ ..."; strip that wrapper so we can
        # still parse `_X = ...` bindings that are otherwise nested under `[`.
        if "Registering" in prefix and "[" in prefix:
            prefix = prefix[prefix.rfind("[") + 1 :]
        # If this came from a tuple pretty-print "(<bindings> Block(...), cost)",
        # drop the leading tuple paren so bindings appear at top-level.
        prefix = prefix.lstrip()
        if prefix.startswith("("):
            prefix = prefix[1:]
        bindings = _parse_top_level_bindings(prefix)
        if bindings:
            return _expand_bindings(block_expr, bindings)
        return block_expr

    # Fallback: old tuple-like printer form "(..., Block(...), 74)".
    if "=" not in s:
        return s
    if not (s.startswith("(") and s.endswith(")")):
        return s

    inner = s[1:-1].strip()
    parts = _split_top_level(inner, seps={",", ";"})
    if len(parts) < 2:
        return s

    bindings: dict[str, str] = {}
    expr_parts: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        lhs_rhs = _split_first_top_level_eq(p)
        if lhs_rhs is None:
            expr_parts.append(p)
            continue
        lhs, rhs = lhs_rhs
        name = lhs.strip()
        if not name.isidentifier():
            expr_parts.append(p)
            continue
        bindings[name] = rhs.strip()

    if not bindings or not expr_parts:
        return s

    final_expr = None
    for p in reversed(expr_parts):
        if "Block(" in p:
            final_expr = p
            break
    if final_expr is None:
        final_expr = expr_parts[-1]

    return _expand_bindings(final_expr, bindings)


def _extract_balanced_call(s: str, start: int) -> str:
    """Extract a call-like substring starting at `start` (e.g. the 'B' in 'Block(').

    Returns the substring from `start` through the matching closing parenthesis.
    """
    i = start
    # Find the first '(' after the callee name.
    while i < len(s) and s[i] != "(":
        i += 1
    if i >= len(s) or s[i] != "(":
        raise TranspileError("Malformed extracted expression: expected '(' after callee")

    paren = 0
    in_str: str | None = None
    j = start
    while j < len(s):
        ch = s[j]
        if in_str is not None:
            if ch == "\\" and j + 1 < len(s):
                j += 2
                continue
            if ch == in_str:
                in_str = None
            j += 1
            continue

        if ch in ("'", '"'):
            in_str = ch
            j += 1
            continue

        if ch == "(":
            paren += 1
        elif ch == ")":
            paren -= 1
            if paren == 0:
                return s[start : j + 1]

        j += 1

    raise TranspileError("Malformed extracted expression: unbalanced parentheses")


def _parse_top_level_bindings(prefix: str) -> dict[str, str]:
    """Parse auxiliary bindings of the form `_X = <expr>` occurring at top level.

    This is intentionally forgiving: it stops each RHS at a top-level separator (`,` or `;`)
    or at the end of `prefix` (which is typically right before the `Block(`).
    """
    text = prefix.strip()
    if not text or "=" not in text:
        return {}

    bindings: dict[str, str] = {}
    i = 0
    paren = bracket = brace = 0
    in_str: str | None = None

    def skip_ws(k: int) -> int:
        while k < len(text) and text[k].isspace():
            k += 1
        return k

    while i < len(text):
        ch = text[i]

        if in_str is not None:
            if ch == "\\" and i + 1 < len(text):
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue

        if ch in ("'", '"'):
            in_str = ch
            i += 1
            continue

        if ch == "(":
            paren += 1
        elif ch == ")":
            paren -= 1
        elif ch == "[":
            bracket += 1
        elif ch == "]":
            bracket -= 1
        elif ch == "{":
            brace += 1
        elif ch == "}":
            brace -= 1

        if paren == 0 and bracket == 0 and brace == 0:
            # Try to recognize an identifier followed by '='.
            if ch.isalpha() or ch == "_":
                lhs_start = i
                j = i + 1
                while j < len(text) and (text[j].isalnum() or text[j] == "_"):
                    j += 1
                lhs = text[lhs_start:j]
                k = skip_ws(j)
                if k < len(text) and text[k] == "=":
                    k += 1
                    k = skip_ws(k)

                    # Parse RHS until a top-level separator (',' ';' or newline) or end.
                    rhs_start = k
                    rhs_paren = rhs_bracket = rhs_brace = 0
                    rhs_in_str: str | None = None
                    m = k
                    while m < len(text):
                        ch2 = text[m]
                        if rhs_in_str is not None:
                            if ch2 == "\\" and m + 1 < len(text):
                                m += 2
                                continue
                            if ch2 == rhs_in_str:
                                rhs_in_str = None
                            m += 1
                            continue
                        if ch2 in ("'", '"'):
                            rhs_in_str = ch2
                            m += 1
                            continue
                        if ch2 == "(":
                            rhs_paren += 1
                        elif ch2 == ")":
                            rhs_paren -= 1
                        elif ch2 == "[":
                            rhs_bracket += 1
                        elif ch2 == "]":
                            rhs_bracket -= 1
                        elif ch2 == "{":
                            rhs_brace += 1
                        elif ch2 == "}":
                            rhs_brace -= 1

                        if rhs_paren == 0 and rhs_bracket == 0 and rhs_brace == 0 and ch2 in {",", ";", "\n"}:
                            break
                        m += 1

                    rhs = text[rhs_start:m].strip()
                    if lhs.isidentifier() and rhs:
                        bindings[lhs] = rhs
                    i = m + 1
                    continue

        i += 1

    return bindings


def _split_top_level(s: str, *, seps: set[str]) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    paren = bracket = brace = 0
    in_str: str | None = None
    i = 0
    while i < len(s):
        ch = s[i]
        if in_str is not None:
            buf.append(ch)
            if ch == "\\" and i + 1 < len(s):
                i += 1
                buf.append(s[i])
            elif ch == in_str:
                in_str = None
            i += 1
            continue

        if ch in ("'", '"'):
            in_str = ch
            buf.append(ch)
            i += 1
            continue

        if ch == "(":
            paren += 1
        elif ch == ")":
            paren -= 1
        elif ch == "[":
            bracket += 1
        elif ch == "]":
            bracket -= 1
        elif ch == "{":
            brace += 1
        elif ch == "}":
            brace -= 1

        if paren == 0 and bracket == 0 and brace == 0 and ch in seps:
            parts.append("".join(buf).strip())
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _split_first_top_level_eq(s: str) -> tuple[str, str] | None:
    paren = bracket = brace = 0
    in_str: str | None = None
    i = 0
    while i < len(s):
        ch = s[i]
        if in_str is not None:
            if ch == "\\" and i + 1 < len(s):
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in ("'", '"'):
            in_str = ch
            i += 1
            continue
        if ch == "(":
            paren += 1
        elif ch == ")":
            paren -= 1
        elif ch == "[":
            bracket += 1
        elif ch == "]":
            bracket -= 1
        elif ch == "{":
            brace += 1
        elif ch == "}":
            brace -= 1

        if paren == 0 and bracket == 0 and brace == 0 and ch == "=":
            return s[:i], s[i + 1 :]
        i += 1
    return None


def _expand_bindings(expr: str, bindings: dict[str, str]) -> str:
    # Expand until fixed point; protect against cycles.
    cache: dict[str, str] = {}

    def expand_name(name: str, stack: set[str]) -> str:
        if name in cache:
            return cache[name]
        if name in stack:
            return name
        if name not in bindings:
            return name
        stack.add(name)
        rhs = bindings[name]
        rhs_expanded = _expand_text(rhs, stack)
        stack.remove(name)
        cache[name] = rhs_expanded
        return rhs_expanded

    def _expand_text(text: str, stack: set[str]) -> str:
        # Token-ish scan replacing whole identifiers that match bindings.
        out: list[str] = []
        i = 0
        in_str: str | None = None
        while i < len(text):
            ch = text[i]
            if in_str is not None:
                out.append(ch)
                if ch == "\\" and i + 1 < len(text):
                    i += 1
                    out.append(text[i])
                elif ch == in_str:
                    in_str = None
                i += 1
                continue
            if ch in ("'", '"'):
                in_str = ch
                out.append(ch)
                i += 1
                continue
            if ch == "_" or ch.isalpha():
                j = i + 1
                while j < len(text) and (text[j] == "_" or text[j].isalnum()):
                    j += 1
                ident = text[i:j]
                if ident in bindings:
                    out.append(f"({expand_name(ident, stack)})")
                else:
                    out.append(ident)
                i = j
                continue
            out.append(ch)
            i += 1
        return "".join(out)

    return _expand_text(expr, set())


def _alpha_normalize_var_in_lit(lit: str, var_name: str, placeholder: str) -> str:
    # Replace whole-word occurrences (avoids partial replacements).
    return re.sub(rf"\b{re.escape(var_name)}\b", placeholder, lit)


def _split_top_level_commas(s: str) -> list[str]:
    """Split `s` on commas that are not nested in parentheses/braces."""
    out: list[str] = []
    buf: list[str] = []
    paren = 0
    brace = 0
    bracket = 0
    for ch in s:
        if ch == "(" and brace == 0 and bracket == 0:
            paren += 1
        elif ch == ")" and brace == 0 and bracket == 0:
            paren = max(0, paren - 1)
        elif ch == "{":
            brace += 1
        elif ch == "}":
            brace = max(0, brace - 1)
        elif ch == "[":
            bracket += 1
        elif ch == "]":
            bracket = max(0, bracket - 1)

        if ch == "," and paren == 0 and brace == 0 and bracket == 0:
            out.append("".join(buf))
            buf = []
            continue
        buf.append(ch)

    out.append("".join(buf))
    return out


def _replace_singleton_vars_in_line(line: str) -> str:
    """Replace variables appearing exactly once in a rule/constraint with `_`.

    For a line like:
        {lp(t, L, L')} :- m(t, L', P'), m(t, L, P), cl(NC, L, L').
    Variables P, P', NC appear once (across head+body), so they become `_`:
        {lp(t, L, L')} :- m(t, L', _), m(t, L, _), cl(_, L, L').

    Handles rules (with ":-"), constraints (":- ..."), and facts (no ":-").

    IMPORTANT: For integrity constraints (headless rules), singleton variables
    are only replaced in positive literals. Variables appearing only in:
    - Aggregates (e.g., #count{...}, #sum{...})
    - Negative literals (e.g., not pred(...))
    should NOT be replaced with _, as they need explicit safety guards.
    """
    if not line.strip() or line.strip().startswith("%"):
        return line

    # Check if it's a rule/constraint or a fact
    if ":-" in line:
        # Split into head and body
        head_part, body_part = line.split(":-", 1)
        head = head_part.strip()
        body = body_part.strip().rstrip(".")
    else:
        # It's a fact or a standalone constraint (shouldn't happen post-Phase 4, but handle it)
        head = line.strip().rstrip(".")
        body = ""

    # Check if this is an integrity constraint (no head)
    is_integrity_constraint = not head and body

    # Helper to find positions of variables that are in "unsafe" contexts
    # (inside aggregates or negative literals) for integrity constraints
    def find_unsafe_var_positions(text: str) -> set[tuple[int, int]]:
        """Find (start, end) positions of variables inside aggregates or negative literals."""
        unsafe_positions: set[tuple[int, int]] = set()

        # Find aggregate regions: #count{...}, #sum{...}, #min{...}, #max{...}
        # Need to handle nested braces
        agg_pattern = r'#(count|sum|min|max|any)\s*\{'
        for agg_match in re.finditer(agg_pattern, text):
            start = agg_match.end() - 1  # Position of opening brace
            brace_count = 1
            pos = start + 1
            while pos < len(text) and brace_count > 0:
                if text[pos] == '{':
                    brace_count += 1
                elif text[pos] == '}':
                    brace_count -= 1
                pos += 1
            # Mark all variable positions within this aggregate
            agg_content = text[start:pos]
            for var_match in re.finditer(r'\b([A-Z][A-Za-z0-9_]*\'*)(?![A-Za-z0-9_\'])', agg_content):
                # Adjust position to be relative to original text
                unsafe_positions.add((start + var_match.start(1), start + var_match.end(1)))

        # Find negative literal regions: not pred(...) or not (...)
        # Pattern matches "not" followed by predicate call or parenthesized expression
        not_pattern = r'\bnot\s+([a-z_][a-zA-Z0-9_]*\s*\([^)]*\)|\([^)]*\))'
        for not_match in re.finditer(not_pattern, text):
            not_content = not_match.group(0)
            not_start = not_match.start()
            for var_match in re.finditer(r'\b([A-Z][A-Za-z0-9_]*\'*)(?![A-Za-z0-9_\'])', not_content):
                unsafe_positions.add((not_start + var_match.start(1), not_start + var_match.end(1)))

        return unsafe_positions

    # Extract all variables from head and body
    var_counts: dict[str, int] = {}

    def count_vars_in_text(text: str) -> None:
        """Scan text for capitalized variable names (simple heuristic)."""
        # Match capitalized identifiers (variables in ASP), including primed variables like P', X'', etc.
        # Pattern: capital letter followed by alphanumerics/underscores, then zero or more apostrophes
        # Use lookahead instead of \b at the end to handle apostrophes correctly
        for match in re.finditer(r'\b([A-Z][A-Za-z0-9_]*\'*)(?![A-Za-z0-9_\'])', text):
            var = match.group(1)
            var_counts[var] = var_counts.get(var, 0) + 1

    count_vars_in_text(head)
    count_vars_in_text(body)

    # Identify singletons
    singletons = {var for var, count in var_counts.items() if count == 1}

    if not singletons:
        return line

    # For integrity constraints, find unsafe positions in body
    unsafe_positions_in_body: set[tuple[int, int]] = set()
    if is_integrity_constraint and body:
        unsafe_positions_in_body = find_unsafe_var_positions(body)

    # Replace singletons with _, but only if they are standalone terms
    # (not inside arithmetic expressions like X+1)
    # For integrity constraints, also skip variables in unsafe positions
    def replace_vars(text: str, unsafe_positions: set[tuple[int, int]] = set()) -> str:
        def replacer(match: re.Match) -> str:
            var = match.group(1)
            if var not in singletons:
                return var

            start, end = match.start(1), match.end(1)

            # Check if this position is in an unsafe context (for ICs)
            if (start, end) in unsafe_positions:
                return var  # Don't replace: in aggregate or negative literal

            # Check if variable is inside an arithmetic expression
            # by looking at what comes before and after
            # Characters that indicate arithmetic context
            arith_chars = set("+-*/%")
            # Check character before (skip whitespace)
            before_ctx = text[:start].rstrip()
            if before_ctx and before_ctx[-1] in arith_chars:
                return var  # Don't replace: ...+ X
            # Also check if preceded by '(' then arithmetic, like (X+1)
            if before_ctx and before_ctx[-1] == '(':
                # Look ahead to see if this is (X op ...) pattern
                after_ctx = text[end:].lstrip()
                if after_ctx and after_ctx[0] in arith_chars:
                    return var  # Don't replace: (X +...
            # Check character after (skip whitespace)
            after_ctx = text[end:].lstrip()
            if after_ctx and after_ctx[0] in arith_chars:
                return var  # Don't replace: X +...
            return "_"
        # Match capitalized identifiers including primed variables
        # Use lookahead instead of \b at the end to handle apostrophes correctly
        return re.sub(r'\b([A-Z][A-Za-z0-9_]*\'*)(?![A-Za-z0-9_\'])', replacer, text)

    new_head = replace_vars(head)
    if body:
        new_body = replace_vars(body, unsafe_positions_in_body)
        if new_head:
            return f"{new_head} :- {new_body}."
        else:
            return f":- {new_body}."
    else:
        return f"{new_head}."
