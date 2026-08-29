import Lean.Data.Json.FromToJson
import SetLah.DSL

namespace SetLah

def protocolVersion : Nat := 1

private def toJson [Lean.ToJson α] (value : α) : Lean.Json :=
  Lean.toJson value

structure EngineConfig where
  executable : Option String := none
  deriving Repr, Inhabited

structure CompileOptions where
  grounding : Bool := false
  costConversion : Bool := false
  entailmentElim : String := "asp"
  verbose : Bool := false
  deriving Repr, Inhabited

structure SolveOptions extends CompileOptions where
  maxModels : Nat := 1
  clingoArguments : Array String := #[]
  deriving Repr, Inhabited

inductive Term where
  | infimum
  | number (value : Int)
  | string (value : String)
  | function (name : String) (arguments : List Term) (positive : Bool)
  | supremum
  deriving Repr, Inhabited, BEq

structure Atom where
  name : String
  arguments : List Term := []
  positive : Bool := true
  deriving Repr, Inhabited, BEq

structure Model where
  atoms : List Atom
  cost : List Int := []
  optimalityProven : Bool := false
  deriving Repr, Inhabited

inductive SolveStatus where
  | satisfiable
  | unsatisfiable
  | unknown
  deriving Repr, Inhabited, BEq

structure CompileResult where
  asp : String
  diagnostics : List String := []
  engineVersion : String
  deriving Repr, Inhabited

structure SolveResult where
  status : SolveStatus
  models : List Model
  diagnostics : List String := []
  engineVersion : String
  deriving Repr, Inhabited

structure BackendError where
  category : String
  message : String
  exitCode : Option UInt32 := none
  deriving Repr, Inhabited

instance : ToString BackendError where
  toString error := s!"{error.category}: {error.message}"

namespace Term

partial def toAsp : Term → String
  | .infimum => "#inf"
  | .supremum => "#sup"
  | .number value => toString value
  | .string value =>
      let escaped := (value.replace "\\" "\\\\").replace "\"" "\\\""
      "\"" ++ escaped ++ "\""
  | .function name [] positive => (if positive then "" else "-") ++ name
  | .function name arguments positive =>
      (if positive then "" else "-") ++ name ++ "(" ++
      String.intercalate "," (arguments.map toAsp) ++ ")"

end Term

namespace Atom

def toAsp (atom : Atom) : String :=
  Term.function atom.name atom.arguments atom.positive |>.toAsp

end Atom

namespace Model

def atomsNamed (model : Model) (name : String) : List Atom :=
  model.atoms.filter (fun atom => atom.name == name)

end Model

structure Instance where
  program : Program
  factSources : List String := []
  deriving Repr, Inhabited

namespace Instance

def ofProgram (program : Program) : Instance := { program }

def addRawFacts (inst : Instance) (source : String) : Instance :=
  { inst with factSources := inst.factSources ++ [source] }

def addAtom (inst : Instance) (atom : Atom) : Instance :=
  inst.addRawFacts (atom.toAsp ++ ".")

def addFact
    (inst : Instance)
    (name : String)
    (arguments : List Term := []) : Instance :=
  inst.addAtom { name, arguments }

def addConst (inst : Instance) (name : String) (value : Int) : Instance :=
  inst.addRawFacts s!"#const {name}={value}."

end Instance

def jsonOptions (options : CompileOptions) : Lean.Json :=
  Lean.Json.mkObj [
    ("grounding", toJson options.grounding),
    ("costConversion", toJson options.costConversion),
    ("entailmentElim", toJson options.entailmentElim),
    ("verbose", toJson options.verbose)
  ]

def jsonSolveOptions (options : SolveOptions) : Lean.Json :=
  Lean.Json.mkObj [
    ("grounding", toJson options.grounding),
    ("costConversion", toJson options.costConversion),
    ("entailmentElim", toJson options.entailmentElim),
    ("verbose", toJson options.verbose),
    ("maxModels", toJson options.maxModels),
    ("clingoArguments", toJson options.clingoArguments)
  ]

def engineExecutable (config : EngineConfig) : IO String := do
  match config.executable with
  | some executable => pure executable
  | none => pure <| (← IO.getEnv "SETLAH_EXE").getD "setlah"

private def exceptGetD (value : Except String α) (fallback : α) : α :=
  match value with
  | .ok result => result
  | .error _ => fallback

private def runProtocolProcess
    (config : EngineConfig)
    (request : Lean.Json) : IO (Except BackendError Lean.Json) := do
  let executable ← engineExecutable config
  try
    let child ← IO.Process.spawn {
      cmd := executable
      args := #["protocol"]
      stdin := .piped
      stdout := .piped
      stderr := .piped
    }
    let child ← do
      let (stdin, child) ← child.takeStdin
      stdin.putStr (request.compress ++ "\n")
      stdin.flush
      pure child
    let stdoutTask ← IO.asTask child.stdout.readToEnd Task.Priority.dedicated
    let stderr ← child.stderr.readToEnd
    let exitCode ← child.wait
    let stdout ← IO.ofExcept stdoutTask.get
    if exitCode != 0 && stdout.trimAscii.isEmpty then
      pure <| .error {
        category := "engine-unavailable"
        message := stderr.trimAscii.copy
        exitCode := some exitCode
      }
    else match Lean.Json.parse stdout with
    | .error error =>
        pure <| .error {
          category := "protocol"
          message := s!"engine returned invalid JSON: {error}; stderr: {stderr.trimAscii.copy}"
          exitCode := some exitCode
        }
    | .ok json =>
        if exitCode == 0 then pure (.ok json)
        else
          let category := exceptGetD (json.getObjVal? "error" >>= (·.getObjVal? "category") >>= (·.getStr?)) "engine"
          let message := exceptGetD (json.getObjVal? "error" >>= (·.getObjVal? "message") >>= (·.getStr?)) stderr.trimAscii.copy
          pure <| .error { category, message, exitCode := some exitCode }
  catch error =>
    pure <| .error {
      category := "engine-unavailable"
      message := s!"could not run '{executable} protocol': {error}"
    }

private def requireResponse (json : Lean.Json) : Except BackendError (String × Lean.Json) := do
  let ok ← json.getObjVal? "ok" >>= (·.getBool?) |>.mapError (fun e => { category := "protocol", message := e })
  let protocol ← json.getObjVal? "protocol" >>= (·.getNat?) |>.mapError (fun e => { category := "protocol", message := e })
  if protocol != protocolVersion then
    throw { category := "protocol", message := s!"engine protocol {protocol} is incompatible with expected {protocolVersion}" }
  let version ← json.getObjVal? "engineVersion" >>= (·.getStr?) |>.mapError (fun e => { category := "protocol", message := e })
  if ok then pure (version, json)
  else
    let category := exceptGetD (json.getObjVal? "error" >>= (·.getObjVal? "category") >>= (·.getStr?)) "engine"
    let message := exceptGetD (json.getObjVal? "error" >>= (·.getObjVal? "message") >>= (·.getStr?)) "unknown engine error"
    throw { category, message }

private partial def termFromJson (json : Lean.Json) : Except BackendError Term := do
  let kind ← json.getObjVal? "kind" >>= (·.getStr?) |>.mapError (fun e => { category := "protocol", message := e })
  match kind with
  | "infimum" => pure .infimum
  | "supremum" => pure .supremum
  | "number" =>
      let value ← json.getObjVal? "value" >>= (·.getInt?) |>.mapError (fun e => { category := "protocol", message := e })
      pure (.number value)
  | "string" =>
      let value ← json.getObjVal? "value" >>= (·.getStr?) |>.mapError (fun e => { category := "protocol", message := e })
      pure (.string value)
  | "function" =>
      let name ← json.getObjVal? "name" >>= (·.getStr?) |>.mapError (fun e => { category := "protocol", message := e })
      let argsJson ← json.getObjVal? "arguments" >>= (·.getArr?) |>.mapError (fun e => { category := "protocol", message := e })
      let arguments ← argsJson.toList.mapM termFromJson
      let positive ← json.getObjVal? "positive" >>= (·.getBool?) |>.mapError (fun e => { category := "protocol", message := e })
      pure (.function name arguments positive)
  | other => throw { category := "protocol", message := s!"unknown symbol kind: {other}" }

private def atomFromJson (json : Lean.Json) : Except BackendError Atom := do
  match ← termFromJson json with
  | .function name arguments positive => pure { name, arguments, positive }
  | _ => throw { category := "protocol", message := "model contained a non-atom top-level symbol" }

private def modelFromJson (json : Lean.Json) : Except BackendError Model := do
  let symbols ← json.getObjVal? "symbols" >>= (·.getArr?) |>.mapError (fun e => { category := "protocol", message := e })
  let atoms ← symbols.toList.mapM atomFromJson
  let costJson ← json.getObjVal? "cost" >>= (·.getArr?) |>.mapError (fun e => { category := "protocol", message := e })
  let cost ← costJson.toList.mapM fun value => value.getInt? |>.mapError (fun e => { category := "protocol", message := e })
  let optimalityProven ← json.getObjVal? "optimalityProven" >>= (·.getBool?) |>.mapError (fun e => { category := "protocol", message := e })
  pure { atoms, cost, optimalityProven }

private def diagnosticsFromJson (json : Lean.Json) : Except BackendError (List String) := do
  let values ← json.getObjVal? "diagnostics" >>= (·.getArr?) |>.mapError (fun e => { category := "protocol", message := e })
  values.toList.mapM fun value => value.getStr? |>.mapError (fun e => { category := "protocol", message := e })

def compile
    (inst : Instance)
    (options : CompileOptions := {})
    (config : EngineConfig := {}) : IO (Except BackendError CompileResult) := do
  let request := Lean.Json.mkObj [
    ("protocol", toJson protocolVersion),
    ("operation", toJson "compile"),
    ("source", toJson (programToSetLah inst.program)),
    ("facts", toJson inst.factSources),
    ("options", jsonOptions options)
  ]
  match ← runProtocolProcess config request with
  | .error error => pure (.error error)
  | .ok raw => pure do
      let (engineVersion, json) ← requireResponse raw
      let asp ← json.getObjVal? "asp" >>= (·.getStr?) |>.mapError (fun e => { category := "protocol", message := e })
      let diagnostics ← diagnosticsFromJson json
      pure { asp, diagnostics, engineVersion }

def solve
    (inst : Instance)
    (options : SolveOptions := {})
    (config : EngineConfig := {}) : IO (Except BackendError SolveResult) := do
  let request := Lean.Json.mkObj [
    ("protocol", toJson protocolVersion),
    ("operation", toJson "solve"),
    ("source", toJson (programToSetLah inst.program)),
    ("facts", toJson inst.factSources),
    ("options", jsonSolveOptions options)
  ]
  match ← runProtocolProcess config request with
  | .error error => pure (.error error)
  | .ok raw => pure do
      let (engineVersion, json) ← requireResponse raw
      let statusString ← json.getObjVal? "status" >>= (·.getStr?) |>.mapError (fun e => { category := "protocol", message := e })
      let status ← match statusString with
        | "satisfiable" => pure SolveStatus.satisfiable
        | "unsatisfiable" => pure SolveStatus.unsatisfiable
        | "unknown" => pure SolveStatus.unknown
        | other => throw { category := "protocol", message := s!"unknown solve status: {other}" }
      let modelsJson ← json.getObjVal? "models" >>= (·.getArr?) |>.mapError (fun e => { category := "protocol", message := e })
      let models ← modelsJson.toList.mapM modelFromJson
      let diagnostics ← diagnosticsFromJson json
      pure { status, models, diagnostics, engineVersion }

def compile!
    (inst : Instance)
    (options : CompileOptions := {})
    (config : EngineConfig := {}) : IO CompileResult := do
  match ← compile inst options config with
  | .ok result => pure result
  | .error error => throw <| IO.userError (toString error)

def solve!
    (inst : Instance)
    (options : SolveOptions := {})
    (config : EngineConfig := {}) : IO SolveResult := do
  match ← solve inst options config with
  | .ok result => pure result
  | .error error => throw <| IO.userError (toString error)

def checkEngine (config : EngineConfig := {}) : IO (Except BackendError String) := do
  let request := Lean.Json.mkObj [
    ("protocol", toJson protocolVersion),
    ("operation", toJson "capabilities")
  ]
  match ← runProtocolProcess config request with
  | .error error => pure (.error error)
  | .ok raw => pure do
      let (engineVersion, _) ← requireResponse raw
      pure engineVersion

end SetLah
