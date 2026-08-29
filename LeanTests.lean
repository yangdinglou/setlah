import SetLah

open SetLah

def quotedSmoke : Program := setlah% r#"
ExtDOM Item: INT.
ExtPred available: (Item).
[
  selected(X)? :- available(X).
  (\exists X. selected(X)).
]
"#

def assertIO (condition : Bool) (message : String) : IO Unit :=
  unless condition do throw <| IO.userError message

def parserRoundTrips : IO Unit := do
  for path in [
      "examples/choose.sl",
      "examples/maple-set/nqueen.sl",
      "examples/maple-set/GL.sl",
      "examples/maple-set/clique.sl",
      "examples/maple-set/sudoku.sl",
      "examples/maple-set/einstein.sl",
      "examples/maple-set/15.sl"
    ] do
    let source ← IO.FS.readFile path
    let program ← match parseProgram source with
      | .ok program => pure program
      | .error error => throw <| IO.userError s!"{path}: {error}"
    let rendered := programToSetLah program
    match parseProgram rendered with
    | .ok _ => pure ()
    | .error error => throw <| IO.userError s!"round-trip {path}: {error}"

def backendFailureTests : IO Unit := do
  let inst := Instance.ofProgram quotedSmoke

  let missing ← solve inst {} { executable := some "/definitely/missing/setlah" }
  match missing with
  | .error error => assertIO (error.category == "engine-unavailable") s!"missing engine category: {error}"
  | .ok _ => throw <| IO.userError "missing engine unexpectedly succeeded"

  let invalid ← solve inst {} { executable := some "tests/lean/mock-invalid-json" }
  match invalid with
  | .error error => assertIO (error.category == "protocol") "invalid JSON category"
  | .ok _ => throw <| IO.userError "invalid JSON unexpectedly succeeded"

  let version ← solve inst {} { executable := some "tests/lean/mock-version-mismatch" }
  match version with
  | .error error => assertIO (error.category == "protocol") "version mismatch category"
  | .ok _ => throw <| IO.userError "version mismatch unexpectedly succeeded"

  let engineError ← solve inst {} { executable := some "tests/lean/mock-engine-error" }
  match engineError with
  | .error error => do
      assertIO (error.category == "semantic-check") "engine error category"
      assertIO (error.message == "intentional test error") "engine error message"
  | .ok _ => throw <| IO.userError "engine error unexpectedly succeeded"

  let structured ← solve inst {} { executable := some "tests/lean/mock-success" }
  match structured with
  | .error error => throw <| IO.userError s!"structured mock failed: {error}"
  | .ok result => do
      assertIO (result.status == .satisfiable) "structured status"
      assertIO (result.models.length == 1) "structured model count"
      let atoms := result.models.head!.atoms
      assertIO (atoms.any (fun atom => atom.name == "selected")) "structured atom decoding"

def main : IO UInt32 := do
  parserRoundTrips
  backendFailureTests
  IO.println "Lean unit tests: OK"
  pure 0
