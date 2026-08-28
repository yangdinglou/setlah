# SetLaH JSON Protocol Version 1

`setlah protocol` reads exactly one JSON request from stdin, writes exactly one
JSON response to stdout, and exits. Protocol stdout is machine-only;
diagnostics are returned structurally or written to stderr.

Every request contains `protocol: 1` and an `operation`. Every response contains
`ok`, `protocol`, and `engineVersion`. An unsuccessful response exits nonzero.

## Operations

### Version

```json
{"protocol":1,"operation":"version"}
```

### Capabilities

```json
{"protocol":1,"operation":"capabilities"}
```

The response includes `capabilities.operations`, `inMemoryFacts`,
`structuredSymbols`, and `defaultMaxModels`.

### Compile

```json
{
  "protocol": 1,
  "operation": "compile",
  "source": "ExtDOM Item: INT. [...]",
  "facts": ["dom_Item(1..3).", "available(1..3)."],
  "options": {
    "grounding": false,
    "costConversion": false,
    "entailmentElim": "asp",
    "verbose": false
  }
}
```

A successful response adds `asp` and a `diagnostics` string array.

### Solve

The solve request uses the compile fields and adds solve options:

```json
{
  "protocol": 1,
  "operation": "solve",
  "source": "ExtDOM Item: INT. [...]",
  "facts": ["dom_Item(1).", "available(1)."],
  "options": {
    "grounding": false,
    "costConversion": false,
    "entailmentElim": "asp",
    "verbose": false,
    "maxModels": 1,
    "clingoArguments": []
  }
}
```

The response contains `status` (`satisfiable`, `unsatisfiable`, or `unknown`),
`models`, and `diagnostics`. `maxModels` defaults to one; zero requests all
models.

Each model contains `symbols`, `cost`, and `optimalityProven`. Symbols are
recursive JSON values rather than printed ASP atoms:

```json
{
  "kind": "function",
  "name": "selected",
  "arguments": [{"kind":"number","value":1}],
  "positive": true
}
```

Supported symbol kinds are `number`, `string`, `function`, `infimum`, and
`supremum`. Function arguments use the same representation. `positive` records
the sign of function symbols.

## Errors

Errors use this shape:

```json
{
  "ok": false,
  "protocol": 1,
  "engineVersion": "0.1.0rc1",
  "error": {"category":"parse","message":"..."}
}
```

Categories are `protocol`, `parse`, `semantic-check`, `compile`, `grounding`,
and `solve`. Clients must reject unsupported protocol versions and should show
the category and message without attempting another compiler implementation.

Protocol version 1 deliberately uses one request per process. Fields may be
added compatibly, but removing fields or changing their meaning requires a new
protocol version.
