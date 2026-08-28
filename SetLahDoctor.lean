import SetLah

open SetLah

def smokeProgram : Program := setlah% r#"
ExtDOM Item: INT.
ExtPred available: (Item).
[
  selected(X)? :- available(X).
  (\exists X. selected(X)).
]
"#

def main : IO UInt32 := do
  match ← checkEngine with
  | .error error =>
      IO.eprintln s!"SetLaH engine check failed: {error}"
      pure 1
  | .ok version =>
      let inst := Instance.ofProgram smokeProgram
        |>.addRawFacts "dom_Item(1). available(1)."
      match ← solve inst with
      | .error error =>
          IO.eprintln s!"SetLaH solve check failed: {error}"
          pure 1
      | .ok result =>
          if result.status == .satisfiable && result.models.length == 1 then
            IO.println s!"SetLaH {version}: protocol {protocolVersion}, Clingo solve OK"
            pure 0
          else
            IO.eprintln "SetLaH engine returned an unexpected smoke-test result"
            pure 1
