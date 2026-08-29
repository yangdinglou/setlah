# Contributing

Set up a development environment with Python 3.11 or later:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
```

Please include focused tests for parser, rewriting, or transpilation changes.
Executable examples should include a `.sl` model, matching input facts, and an
entry in `examples/check.sh`. Experimental compiler examples must at least
compile with `setlah <example> --print-asp`.

Changes to the Lean client or JSON protocol must also pass:

```bash
lake build SetLah setlahDoctor setlahExamples setlahTests
lake exe setlahDoctor
lake exe setlahTests
lake exe setlahExamples
```

Protocol changes require tests on both the Python producer and Lean consumer.
Keep protocol stdout machine-only and preserve backward compatibility within a
protocol version.
