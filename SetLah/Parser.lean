import SetLah.Ast

namespace SetLah

abbrev ParseM := Except String

structure ParserState where
  tokens : Array String
  pos : Nat := 0
  deriving Repr

abbrev P := StateT ParserState ParseM

private def isIdentChar (c : Char) : Bool :=
  c.isAlphanum || c == '_' || c == '\'' || c == '\\'

private def isOpChar (c : Char) : Bool :=
  c == '=' || c == '!' || c == '<' || c == '>' || c == ':' || c == '-' ||
  c == '+' || c == '*' || c == '/' || c == '∪' || c == '∩' || c == 'Δ' ||
  c == '⊕' || c == '∊' || c == '∀' || c == '∃' || c == '∧' || c == '∨' ||
  c == '→' || c == '¬'

partial def tokenizeChars : List Char → List Char → List String → List String
  | [], cur, acc =>
      let acc := if cur.isEmpty then acc else String.ofList cur.reverse :: acc
      acc.reverse
  | '%' :: cs, cur, acc =>
      let acc := if cur.isEmpty then acc else String.ofList cur.reverse :: acc
      let rest := cs.dropWhile (fun c => c != '\n')
      tokenizeChars rest [] acc
  | c :: cs, cur, acc =>
      if c.isWhitespace then
        let acc := if cur.isEmpty then acc else String.ofList cur.reverse :: acc
        tokenizeChars cs [] acc
      else if "()[]{}.,?".contains c then
        let acc := if cur.isEmpty then acc else String.ofList cur.reverse :: acc
        tokenizeChars cs [] (String.singleton c :: acc)
      else if isIdentChar c || c == '#' then
        tokenizeChars cs (c :: cur) acc
      else if isOpChar c then
        let acc := if cur.isEmpty then acc else String.ofList cur.reverse :: acc
        let (opChars, rest) := (c :: cs).span isOpChar
        tokenizeChars rest [] (String.ofList opChars :: acc)
      else
        let acc := if cur.isEmpty then acc else String.ofList cur.reverse :: acc
        tokenizeChars cs [] (String.singleton c :: acc)

def tokenize (s : String) : Array String :=
  (tokenizeChars s.toList [] []).toArray

def peek : P (Option String) := do
  let st ← get
  pure <| st.tokens[st.pos]?

def peekD (fallback : String := "<eof>") : P String := do
  pure <| (← peek).getD fallback

def peekAt (offset : Nat) : P (Option String) := do
  let st ← get
  pure <| st.tokens[st.pos + offset]?

def bump : P String := do
  let st ← get
  match st.tokens[st.pos]? with
  | none => throw "unexpected end of input"
  | some t =>
      set { st with pos := st.pos + 1 }
      pure t

def expect (wanted : String) : P Unit := do
  let st ← get
  let got ← bump
  if got != wanted then
    throw s!"expected '{wanted}', got '{got}' at token {st.pos}"

def accept (wanted : String) : P Bool := do
  if (← peek) == some wanted then
    discard bump
    pure true
  else
    pure false

def parseIdent : P String := do
  let t ← bump
  if t.isEmpty then
    throw "expected identifier"
  else
    pure t

partial def parseType : P TypeNode := do
  let t ← bump
  match t with
  | "INT" => pure .int
  | "Symbol" => pure .symbol
  | "Tuple" =>
      expect "("
      let rec loop (acc : List TypeNode) : P (List TypeNode) := do
        let ty ← parseType
        let acc := ty :: acc
        if (← accept ",") then loop acc else pure acc.reverse
      let items ← loop []
      expect ")"
      pure (.tuple items)
  | other => pure (.custom other)

def parseConstAtom (t : String) : Expr :=
  match t.toInt? with
  | some n => .constInt n
  | none => if isUpperIdent t then .var t else .constSym t

def arithmeticOpOfString : String → Except String ArithmeticOp
  | "+" => pure .add
  | "-" => pure .subtract
  | "*" => pure .multiply
  | "/" => pure .divide
  | op => throw s!"unknown arithmetic operator '{op}'"

def setOpOfString : String → Except String SetOp
  | "∪" => pure .union
  | "∩" => pure .intersection
  | "Δ" => pure .difference
  | "⊕" => pure .symmetricDifference
  | op => throw s!"unknown set operator '{op}'"

def compareOpOfString : String → Except String CompareOp
  | "=" | "==" => pure .equal
  | "!=" => pure .notEqual
  | "<" => pure .less
  | "<=" => pure .lessEqual
  | ">" => pure .greater
  | ">=" => pure .greaterEqual
  | op => throw s!"unknown comparison operator '{op}'"

def quantifierOfString : String → Except String Quantifier
  | "\\forall" | "∀" => pure .forall
  | "\\exists" | "∃" => pure .exists
  | q => throw s!"unknown quantifier '{q}'"

def aggregateOpOfString : String → Except String AggregateOp
  | "#count" => pure .count
  | "#sum" => pure .sum
  | "#min" => pure .minimum
  | "#max" => pure .maximum
  | op => throw s!"unknown aggregate operator '{op}'"

mutual

partial def parseExpr : P Expr := parseCompareExpr

partial def parseCompareExpr : P Expr := do
  let left ← parseAddSub
  pure left

partial def parseAddSub : P Expr := do
  let mut left ← parseMulDiv
  let mut cont := true
  while cont do
    match (← peek) with
    | some "+" =>
        discard bump
        let right ← parseMulDiv
        left := .binary .add left right
    | some "-" =>
        discard bump
        let right ← parseMulDiv
        left := .binary .subtract left right
    | _ => cont := false
  pure left

partial def parseMulDiv : P Expr := do
  let mut left ← parseExprAtom
  let mut cont := true
  while cont do
    match (← peek) with
    | some "*" =>
        discard bump
        let right ← parseExprAtom
        left := .binary .multiply left right
    | some "/" =>
        discard bump
        let right ← parseExprAtom
        left := .binary .divide left right
    | _ => cont := false
  pure left

partial def parseExprAtom : P Expr := do
  if (← accept "(") then
    match (← peekD) with
    | "+" | "-" | "*" | "/" =>
        let op ← arithmeticOpOfString (← bump)
        let l ← parseExpr
        let r ← parseExpr
        expect ")"
        pure (.binary op l r)
    | _ =>
        let e ← parseExpr
        expect ")"
        pure e
  else
    parseConstAtom <$> bump

end

partial def parseExprListUntil (stop : String) : P (List Expr) := do
  if (← accept stop) then
    pure []
  else
    let rec loop (acc : List Expr) : P (List Expr) := do
      let e ← parseExpr
      let acc := e :: acc
      if (← accept ",") then
        loop acc
      else
        expect stop
        pure acc.reverse
    loop []

partial def parsePredAtom : P Formula := do
  let name ← parseIdent
  expect "("
  let args ← parseExprListUntil ")"
  pure (.pred name args)

partial def parseSetVar : P (String × List Expr) := do
  expect "{"
  let name ← parseIdent
  expect "}"
  let params ←
    if (← accept "(") then
      parseExprListUntil ")"
    else
      pure []
  pure (name, params)

mutual

partial def parseSetExpr : P SetExpr := do
  match (← peekD) with
  | "EMPTY" => discard bump; pure .empty
  | "Set_" =>
      discard bump
      expect "{"
      let n ← parseIdent
      expect "}"
      pure (.pred n)
  | "{" =>
      discard bump
      if (← accept "(") then
        let term ← parseExprListUntil ")"
        expect "|"
        expect "("
        let domainTerm ← parseExprListUntil ")"
        expect "in"
        let domain ← parseSetExpr
        expect ","
        let cond ← parseFormula
        expect "}"
        pure (.comprehension term domainTerm domain cond)
      else
        let name ← parseIdent
        expect "}"
        let params ←
          if (← accept "(") then parseExprListUntil ")" else pure []
        pure (.var name params)
  | "(" =>
      discard bump
      let op ← setOpOfString (← bump)
      let l ← parseSetExpr
      let r ← parseSetExpr
      expect ")"
      pure (.op op l r)
  | other => throw s!"expected set expression, got '{other}'"

partial def parseComparisonAfterLParen (op : CompareOp) : P Formula := do
  let l ← parseExpr
  let r ← parseExpr
  expect ")"
  pure (.comp op l r)

partial def parsePrefixFormula : P Formula := do
  expect "("
  match (← peekD) with
  | "\\and" | "∧" =>
      discard bump
      let items ← parseFormulaItemsUntil ")"
      pure (.logic .and items)
  | "\\or" | "∨" =>
      discard bump
      let items ← parseFormulaItemsUntil ")"
      pure (.logic .or items)
  | "\\impl" | "→" =>
      discard bump
      let a ← parseFormula
      let b ← parseFormula
      expect ")"
      pure (.logic .implies [a, b])
  | "\\neg" | "¬" =>
      discard bump
      let a ← parseFormula
      expect ")"
      pure (.logic .not [a])
  | "\\belonging" =>
      discard bump
      let v ← parseIdent
      let s ← parseSetExpr
      expect ")"
      pure (.membership v s)
  | "\\subset" =>
      discard bump
      let v ← parseIdent
      let s ← parseSetExpr
      expect ")"
      pure (.subset v s)
  | "\\partition" =>
      discard bump
      let target ← parseIdent
      expect "{"
      expect "{"
      let rec parts (acc : List String) : P (List String) := do
        if (← accept "}") then
          expect "}"
          pure acc.reverse
        else
          let p ← parseIdent
          parts (p :: acc)
      let ps ← parts []
      expect ")"
      pure (.partition target ps)
  | "=" | "==" | "!=" | "<" | "<=" | ">" | ">=" =>
      parseComparisonAfterLParen (← compareOpOfString (← bump))
  | _ =>
      let f ← parseFormula
      expect ")"
      pure f

partial def parseFormulaItemsUntil (stop : String) : P (List Formula) := do
  let rec loop (acc : List Formula) : P (List Formula) := do
    if (← peek) == some stop then
      discard bump
      pure acc.reverse
    else
      let f ← parseFormula
      loop (f :: acc)
  loop []

partial def parseQuant : P Formula := do
  let q ← quantifierOfString (← bump)
  let rec vars (acc : List String) : P (List String) := do
    let v ← parseIdent
    let acc := v :: acc
    if (← accept ",") then vars acc else pure acc.reverse
  let vs ← vars []
  expect "."
  let body ← parseFormula
  pure <| vs.reverse.foldl (fun b v => Formula.quant q v b) body

partial def parseAgg : P Formula := do
  let op ← aggregateOpOfString (← bump)
  let (name, setParams) ← parseSetVar
  let params ←
    if (← accept "(") then parseExprListUntil ")" else pure setParams
  let compOp ← compareOpOfString (← bump)
  let value ← parseExpr
  pure (.agg op name params compOp value)

partial def parseInfixOrAtom : P Formula := do
  let t ← peekD
  if t == "\\true" then
    discard bump
    pure (.bool true)
  else if t == "\\false" then
    discard bump
    pure (.bool false)
  else
    match (← peek) with
    | some name =>
        if (← peekAt 1) == some "(" && !isUpperIdent name && name.toInt?.isNone then
          parsePredAtom
        else if isUpperIdent name || name.toInt?.isSome || !isUpperIdent name then
          let l ← parseExpr
          let op ← bump
          if ["=", "==", "!=", "<", "<=", ">", ">="].contains op then
            let r ← parseExpr
            pure (.comp (← compareOpOfString op) l r)
          else
            throw s!"expected comparison operator after expression, got '{op}'"
        else
          parsePredAtom
    | none => throw "expected formula"

partial def parseFormula : P Formula := do
  match (← peekD) with
  | "\\forall" | "∀" | "\\exists" | "∃" => parseQuant
  | "#count" | "#sum" | "#min" | "#max" => parseAgg
  | "(" => parsePrefixFormula
  | _ => parseInfixOrAtom

end

partial def parseLiteralList : P (List Formula) := do
  let rec loop (acc : List Formula) : P (List Formula) := do
    let f ← parseFormula
    let acc := f :: acc
    if (← accept ",") then loop acc else pure acc.reverse
  loop []

partial def parseLetExpr : P LetExpr := do
  expect "Let"
  let (name, params) ← parseSetVar
  expect "="
  let value ← parseSetExpr
  expect "in"
  pure { name, params, value }

partial def parseStatement : P Statement := do
  if (← peek) == some "Let" then
    let rec lets (acc : List LetExpr) : P (List LetExpr) := do
      if (← peek) == some "Let" then
        let l ← parseLetExpr
        lets (l :: acc)
      else pure acc.reverse
    let ls ← lets []
    let f ← parseFormula
    expect "."
    pure (.constraint ls f)
  else
    match (← peek) with
    | some t =>
        if t == "[" || t == "]" then
          throw s!"unexpected '{t}'"
        else if !isUpperIdent t && !(t.startsWith "\\") && (← peekAt 1) == some "(" then
          let head ← parsePredAtom
          let choice ← accept "?"
          if (← accept ":-") then
            let body ← parseLiteralList
            expect "."
            pure (.rule { head, body, isChoice := choice })
          else
            expect "."
            if choice then
              pure (.rule { head, body := [], isChoice := true })
            else
              pure (.rule { head, body := [], isChoice := false })
        else
          let f ← parseFormula
          expect "."
          pure (.constraint [] f)
    | none => throw "unexpected end of input in statement"

partial def parseBlock : P Block := do
  expect "["
  let rec loop (acc : List Statement) : P (List Statement) := do
    if (← accept "]") then
      pure acc.reverse
    else
      let s ← parseStatement
      loop (s :: acc)
  let statements ← loop []
  pure { statements }

partial def skipSetDefinition : P (Option String) := do
  let start ← bump
  let rec collect (acc : List String) : P (List String) := do
    if (← accept ".") then pure acc.reverse
    else collect ((← bump) :: acc)
  let rest ← collect []
  pure (some (joinSep " " (start :: rest)))

partial def parseDomainDecl : P DomainDecl := do
  let kind ← bump
  match kind with
  | "ExtDOM" =>
      let name ← parseIdent
      expect ":"
      let ty ← parseType
      let extra ←
        if (← accept ".") then pure none
        else
          let e ← parseIdent
          expect "."
          pure (some e)
      pure { kind := .externalDomain, name, type := ty, extra }
  | "DefDOM" =>
      let name ← parseIdent
      expect ":"
      let ty ← parseType
      let extra ← skipSetDefinition
      pure { kind := .definedDomain, name, type := ty, extra }
  | "ExtPred" =>
      let name ← parseIdent
      expect ":"
      expect "("
      let rec tys (acc : List TypeNode) : P (List TypeNode) := do
        let ty ← parseType
        let acc := ty :: acc
        if (← accept ",") then tys acc else pure acc.reverse
      let sig ← tys []
      expect ")"
      expect "."
      pure { kind := .externalPredicate, name, type := .tuple sig }
  | "Const" =>
      let name ← parseIdent
      expect ":"
      let ty ← parseType
      let extra ←
        if (← accept "=") then
          let v ← bump
          expect "."
          pure (some v)
        else
          expect "."
          pure none
      pure { kind := .constant, name, type := ty, extra }
  | other => throw s!"expected declaration, got '{other}'"

partial def parseProgramP : P Program := do
  let rec decls (acc : List DomainDecl) : P (List DomainDecl) := do
    match (← peek) with
    | some "[" | none => pure acc.reverse
    | some _ =>
        let d ← parseDomainDecl
        decls (d :: acc)
  let ds ← decls []
  let rec blocks (acc : List Block) : P (List Block) := do
    match (← peek) with
    | none => pure acc.reverse
    | some "[" =>
        let b ← parseBlock
        blocks (b :: acc)
    | some t => throw s!"expected block, got '{t}'"
  let bs ← blocks []
  pure { domains := ds, blocks := bs }

def parseProgram (source : String) : ParseM Program := do
  let toks := tokenize source
  let (p, st) ← parseProgramP.run { tokens := toks }
  if st.pos == st.tokens.size then
    pure p
  else
    throw s!"unconsumed input at token {st.pos}: {(st.tokens[st.pos]?).getD "<eof>"}"

end SetLah
