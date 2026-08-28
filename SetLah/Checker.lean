import SetLah.Ast

namespace SetLah

structure Signature where
  argTypes : List String
  argNames : List String
  external : Bool
  deriving Repr, BEq

abbrev SigTable := List (String × Signature)

def lookupSig (sigs : SigTable) (name : String) : Option Signature :=
  match sigs.find? (fun p => p.fst == name) with
  | some p => some p.snd
  | none => none

def upsertSig (sigs : SigTable) (name : String) (sig : Signature) : SigTable :=
  (name, sig) :: sigs.filter (fun p => p.fst != name)

def typeName : TypeNode → String
  | .int => "INT"
  | .symbol => "Symbol"
  | .custom n => n
  | .tuple _ => "Tuple"

def exprName : Expr → String
  | .var v => v
  | _ => "?"

def declaredSignatures (p : Program) : SigTable :=
  p.domains.foldl
    (fun sigs d =>
      match d.kind, d.type with
      | .externalPredicate, .tuple ts =>
          upsertSig sigs d.name
            { argTypes := ts.map typeName, argNames := List.replicate ts.length "?", external := true }
      | _, _ => sigs)
    []

partial def checkFormula (sigs : SigTable) : Formula → Except String SigTable
  | .pred n args =>
      match lookupSig sigs n with
      | none =>
          pure <| upsertSig sigs n
            { argTypes := List.replicate args.length "?", argNames := args.map exprName, external := false }
      | some sig =>
          if sig.argTypes.length == args.length then pure sigs
          else throw s!"predicate '{n}' used with arity {args.length}, declared with arity {sig.argTypes.length}"
  | .comp _ _ _ => pure sigs
  | .logic _ items => items.foldlM checkFormula sigs
  | .quant _ _ body => checkFormula sigs body
  | .agg _ _ _ _ _ => pure sigs
  | .membership _ _ => pure sigs
  | .subset _ _ => pure sigs
  | .partition _ _ => pure sigs
  | .bool _ => pure sigs

def bindingsFromFormula (sigs : SigTable) : Formula → List (String × String)
  | .pred n args =>
      let domBinding :=
        match args with
        | [.var v] => if n.startsWith "dom_" then [(v, (n.drop 4).toString)] else []
        | _ => []
      let sigBindings :=
        match lookupSig sigs n with
        | none => []
        | some sig =>
            args.zip sig.argTypes |>.filterMap (fun p =>
              match p.fst with
              | .var v => if p.snd == "?" then none else some (v, p.snd)
              | _ => none)
      domBinding ++ sigBindings
  | _ => []

def domainBindings (sigs : SigTable) (body : List Formula) : List (String × String) :=
  body.flatMap (bindingsFromFormula sigs)

def inferHeadTypes (sigs : SigTable) (body : List Formula) (head : Formula) :
    Option (String × List String × List String) :=
  match head with
  | .pred n args =>
      let bs := domainBindings sigs body
      let names := args.map exprName
      let types := args.map (fun
        | .var v =>
            match bs.find? (fun p => p.fst == v) with
            | some p => p.snd
            | none => "?"
        | _ => "?")
      some (n, names, types)
  | _ => none

def mergeUnknowns (old fresh : List String) : List String :=
  old.zip fresh |>.map (fun p => if p.fst == "?" then p.snd else p.fst)

def refineSignature (sigs : SigTable) (name : String) (names types : List String) : SigTable :=
  match lookupSig sigs name with
  | none => upsertSig sigs name { argTypes := types, argNames := names, external := false }
  | some sig =>
      if sig.argTypes.length == types.length then
        upsertSig sigs name
          { sig with argTypes := mergeUnknowns sig.argTypes types, argNames := mergeUnknowns sig.argNames names }
      else sigs

def checkStatement (sigs : SigTable) : Statement → Except String SigTable
  | .rule r => do
      let sigs ← checkFormula sigs r.head
      let sigs ← r.body.foldlM checkFormula sigs
      let sigs :=
        match inferHeadTypes sigs r.body r.head with
        | some (n, ns, ts) => refineSignature sigs n ns ts
        | none => sigs
      pure sigs
  | .constraint _ f => checkFormula sigs f

def checkProgram (p : Program) : Except String SigTable := do
  let mut sigs := declaredSignatures p
  for b in p.blocks do
    for s in b.statements do
      sigs ← checkStatement sigs s
  pure sigs

end SetLah
