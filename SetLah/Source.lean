import SetLah.Ast

namespace SetLah

partial def typeToSetLah : TypeNode → String
  | .int => "INT"
  | .symbol => "Symbol"
  | .custom n => n
  | .tuple ts => "Tuple(" ++ joinSep ", " (ts.map typeToSetLah) ++ ")"

def exprToSetLah : Expr → String
  | .var n => n
  | .constInt n => toString n
  | .constSym s => s
  | .binary op l r => "(" ++ op.toSource ++ " " ++ exprToSetLah l ++ " " ++ exprToSetLah r ++ ")"

mutual

partial def setExprToSetLah : SetExpr → String
  | .empty => "EMPTY"
  | .var n [] => "{" ++ n ++ "}"
  | .var n ps => "{" ++ n ++ "}(" ++ joinSep ", " (ps.map exprToSetLah) ++ ")"
  | .pred n => "Set_{" ++ n ++ "}"
  | .op op l r => "(" ++ op.toSource ++ " " ++ setExprToSetLah l ++ " " ++ setExprToSetLah r ++ ")"
  | .comprehension term domainTerm domain cond =>
      "{ (" ++ joinSep ", " (term.map exprToSetLah) ++ ") | (" ++
      joinSep ", " (domainTerm.map exprToSetLah) ++ ") in " ++
      setExprToSetLah domain ++ ", " ++ formulaToSetLah cond ++ " }"

partial def formulaToSetLah : Formula → String
  | .pred n args => n ++ "(" ++ joinSep ", " (args.map exprToSetLah) ++ ")"
  | .comp op l r => "(" ++ op.toSource ++ " " ++ exprToSetLah l ++ " " ++ exprToSetLah r ++ ")"
  | .logic op items => "(" ++ op.toSource ++ " " ++ joinSep " " (items.map (fun f => "(" ++ formulaToSetLah f ++ ")")) ++ ")"
  | .quant q v body => q.toSource ++ " " ++ v ++ ". " ++ formulaToSetLah body
  | .agg op setName params compOp value =>
      op.toSource ++ " {" ++ setName ++ "}" ++
      (if params.isEmpty then "" else "(" ++ joinSep ", " (params.map exprToSetLah) ++ ")") ++
      " " ++ compOp.toSource ++ " " ++ exprToSetLah value
  | .membership v s => "(\\belonging " ++ v ++ " " ++ setExprToSetLah s ++ ")"
  | .subset l r => "(\\subset " ++ l ++ " " ++ setExprToSetLah r ++ ")"
  | .partition target parts => "(\\partition " ++ target ++ " {{" ++ joinSep " " parts ++ "}})"
  | .bool true => "\\true"
  | .bool false => "\\false"

end

def domainDeclToSetLah (d : DomainDecl) : String :=
  match d.kind with
  | .externalDomain =>
      "ExtDOM " ++ d.name ++ ": " ++ typeToSetLah d.type ++
      (match d.extra with | some e => " " ++ e | none => "") ++ "."
  | .definedDomain =>
      "DefDOM " ++ d.name ++ ": " ++ typeToSetLah d.type ++
      (match d.extra with | some e => " " ++ e | none => "") ++ "."
  | .externalPredicate =>
      match d.type with
      | .tuple ts => "ExtPred " ++ d.name ++ ": (" ++ joinSep ", " (ts.map typeToSetLah) ++ ")."
      | ty => "ExtPred " ++ d.name ++ ": (" ++ typeToSetLah ty ++ ")."
  | .constant =>
      "Const " ++ d.name ++ ": " ++ typeToSetLah d.type ++
      (match d.extra with | some e => " = " ++ e | none => "") ++ "."

def ruleToSetLah (r : Rule) : String :=
  let head :=
    match r.head with
    | .pred n args => n ++ "(" ++ joinSep ", " (args.map exprToSetLah) ++ ")" ++ (if r.isChoice then "?" else "")
    | other => formulaToSetLah other
  match r.body with
  | [] => head ++ "."
  | body => head ++ " :- " ++ joinSep ", " (body.map formulaToSetLah) ++ "."

def letExprToSetLah (l : LetExpr) : String :=
  "Let {" ++ l.name ++ "}" ++
  (if l.params.isEmpty then "" else "(" ++ joinSep ", " (l.params.map exprToSetLah) ++ ")") ++
  " = " ++ setExprToSetLah l.value ++ " in"

def statementToSetLah : Statement → String
  | .rule r => "    " ++ ruleToSetLah r
  | .constraint lets f =>
      let pre :=
        match lets with
        | [] => ""
        | ls => joinSep " " (ls.map letExprToSetLah) ++ " "
      "    " ++ pre ++ formulaToSetLah f ++ "."

def blockToSetLah (b : Block) : String :=
  "[\n" ++ joinSep "\n" (b.statements.map statementToSetLah) ++ "\n]"

def programToSetLah (p : Program) : String :=
  joinSep "\n" (p.domains.map domainDeclToSetLah) ++ "\n\n" ++
  joinSep "\n\n" (p.blocks.map blockToSetLah) ++ "\n"

end SetLah
