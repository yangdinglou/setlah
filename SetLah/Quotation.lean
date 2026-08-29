import Lean.Elab.Term
import SetLah.Parser

namespace SetLah

def parseProgram! (source : String) : Program :=
  match parseProgram source with
  | .ok program => program
  | .error error => panic! s!"invalid SetLaH quotation: {error}"

elab "setlah% " source:str : term => do
  let value := source.getString
  match parseProgram value with
  | .error error => Lean.throwErrorAt source error
  | .ok _ =>
      Lean.Elab.Term.elabTerm (← `(SetLah.parseProgram! $source)) none

end SetLah
