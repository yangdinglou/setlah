import SetLah

open SetLah
open SetLah.DSL

def choiceQuoted : Program := setlah% r#"
ExtDOM Item: INT.
ExtPred available: (Item).
[
  selected(X)? :- available(X).
  (\exists X. selected(X)).
]
"#

def choiceDsl : Program :=
  program
    [extDom "Item", extPred "available" [ty "Item"]]
    [block [
      choice (atom "selected" [v "X"]) [atom "available" [v "X"]],
      constraint (ex "X" (atom "selected" [v "X"]))
    ]]

def nqueenQuoted : Program := setlah% r#"
ExtDOM Index: INT.
ExtPred n_map: (Index, Index).
[
  queen(R, C)? :- n_map(R, C).
  \forall R. #count {Set_queen}(C) = 1.
  \forall C. #count {Set_queen}(R) = 1.
  \forall R1, C1, R2, C2.
    (\impl
      (\and queen(R1, C1) queen(R2, C2) (!= R1 R2))
      (\and
        (!= (- R1 R2) (- C1 C2))
        (!= (- R1 R2) (- C2 C1))
      )
    ).
]
"#

def nqueenDsl : Program :=
  program
    [extDom "Index", extPred "n_map" [ty "Index", ty "Index"]]
    [block [
      choice (atom "queen" [v "R", v "C"]) [atom "n_map" [v "R", v "C"]],
      constraint <| all "R" <| count "Set_queen" [v "C"] .equal (i 1),
      constraint <| all "C" <| count "Set_queen" [v "R"] .equal (i 1),
      constraint <| forallMany ["R1", "C1", "R2", "C2"] <|
        impl
          (land [
            atom "queen" [v "R1", v "C1"],
            atom "queen" [v "R2", v "C2"],
            ne (v "R1") (v "R2")
          ])
          (land [
            ne (sub (v "R1") (v "R2")) (sub (v "C1") (v "C2")),
            ne (sub (v "R1") (v "R2")) (sub (v "C2") (v "C1"))
          ])
    ]]

def parseProgramIO (source : String) : IO Program :=
  match parseProgram source with
  | .ok program => pure program
  | .error error => throw <| IO.userError error

def readInstance (modelPath factsPath : String) : IO Instance := do
  let model ← IO.FS.readFile modelPath
  let facts ← IO.FS.readFile factsPath
  pure <| (Instance.ofProgram (← parseProgramIO model)).addRawFacts facts

def runSat (name : String) (inst : Instance) (options : SolveOptions := {}) : IO Unit := do
  let result ← solve! inst options
  if result.status != .satisfiable || result.models.isEmpty then
    throw <| IO.userError s!"{name}: expected SAT with a model, got {repr result.status}"
  IO.println s!"{name}: SAT ({result.models.length} model)"

def runAll : IO Unit := do
  let choiceFacts := "dom_Item(1..3). available(1..3)."
  runSat "choice quotation" <| (Instance.ofProgram choiceQuoted).addRawFacts choiceFacts
  runSat "choice combinators" <| (Instance.ofProgram choiceDsl).addRawFacts choiceFacts

  let nqueenFacts ← IO.FS.readFile "examples/instances/nqueen-4.lp"
  let solveOptions : SolveOptions := { grounding := true, costConversion := true }
  runSat "nqueen quotation" ((Instance.ofProgram nqueenQuoted).addRawFacts nqueenFacts) solveOptions
  runSat "nqueen combinators" ((Instance.ofProgram nqueenDsl).addRawFacts nqueenFacts) solveOptions

  for (name, model, facts) in [
      ("GL square", "examples/maple-set/GL.sl", "examples/instances/gl-3.lp"),
      ("clique", "examples/maple-set/clique.sl", "examples/instances/clique-4.lp"),
      ("Sudoku", "examples/maple-set/sudoku.sl", "examples/instances/sudoku-easy.lp"),
      ("Einstein", "examples/maple-set/einstein.sl", "examples/instances/einstein.lp"),
      ("15-puzzle", "examples/maple-set/15.sl", "examples/instances/15-solved.lp")
    ] do
    runSat name (← readInstance model facts) solveOptions

  let unsat := Instance.ofProgram choiceQuoted |>.addRawFacts "dom_Item(1..3)."
  let unsatResult ← solve! unsat
  if unsatResult.status != .unsatisfiable then
    throw <| IO.userError "intentional UNSAT example returned a different status"
  IO.println "empty choice: UNSAT"

def main : IO UInt32 := do
  runAll
  pure 0
