from __future__ import annotations

import io
import json

from setlah.protocol import PROTOCOL_VERSION, handle_request, protocol_main


CHOICE = r"""
ExtDOM Item: INT.
ExtPred available: (Item).
[
    selected(X)? :- available(X).
    (\exists X. selected(X)).
]
"""


def test_version_and_capabilities() -> None:
    version = handle_request({"protocol": 1, "operation": "version"})
    capabilities = handle_request({"protocol": 1, "operation": "capabilities"})
    assert version["protocol"] == PROTOCOL_VERSION
    assert capabilities["capabilities"]["structuredSymbols"] is True


def test_compile_request() -> None:
    response = handle_request({
        "protocol": 1,
        "operation": "compile",
        "source": CHOICE,
        "facts": ["dom_Item(1). available(1)."],
    })
    assert response["ok"] is True
    assert "available(1)." in response["asp"]


def test_solve_request_returns_structured_symbols() -> None:
    response = handle_request({
        "protocol": 1,
        "operation": "solve",
        "source": CHOICE,
        "facts": ["dom_Item(1). available(1)."],
    })
    assert response["status"] == "satisfiable"
    assert response["models"][0]["symbols"][0]["kind"] == "function"


def test_protocol_errors_are_json_and_nonzero() -> None:
    stdout = io.StringIO()
    code = protocol_main(io.StringIO('{"protocol":99,"operation":"version"}'), stdout)
    response = json.loads(stdout.getvalue())
    assert code == 1
    assert response["ok"] is False
    assert response["error"]["category"] == "protocol"
    assert "expected 1" in response["error"]["message"]


def test_protocol_rejects_boolean_version_and_non_boolean_options() -> None:
    for request in [
        {"protocol": True, "operation": "version"},
        {
            "protocol": 1,
            "operation": "compile",
            "source": CHOICE,
            "options": {"grounding": "yes"},
        },
    ]:
        stdout = io.StringIO()
        assert protocol_main(io.StringIO(json.dumps(request)), stdout) == 1
        assert json.loads(stdout.getvalue())["error"]["category"] == "protocol"


def test_malformed_json_is_json_error() -> None:
    stdout = io.StringIO()
    code = protocol_main(io.StringIO("{"), stdout)
    response = json.loads(stdout.getvalue())
    assert code == 1
    assert response["error"]["category"] == "protocol"


def test_parse_and_semantic_errors_are_categorized() -> None:
    parse = io.StringIO()
    parse_code = protocol_main(io.StringIO(json.dumps({
        "protocol": 1, "operation": "compile", "source": "not valid"
    })), parse)
    assert parse_code == 1
    assert json.loads(parse.getvalue())["error"]["category"] == "parse"

    semantic = io.StringIO()
    semantic_code = protocol_main(io.StringIO(json.dumps({
        "protocol": 1,
        "operation": "compile",
        "source": "ExtPred bad: (Missing). [ bad(X)? :- bad(X). ]",
    })), semantic)
    assert semantic_code == 1
    assert json.loads(semantic.getvalue())["error"]["category"] == "semantic-check"
