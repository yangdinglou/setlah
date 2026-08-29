namespace SetLah

inductive TypeNode where
  | int
  | symbol
  | custom (name : String)
  | tuple (items : List TypeNode)
  deriving Repr, BEq, Inhabited

inductive ArithmeticOp where
  | add | subtract | multiply | divide
  deriving Repr, BEq, Inhabited

inductive SetOp where
  | union | intersection | difference | symmetricDifference
  deriving Repr, BEq, Inhabited

inductive CompareOp where
  | equal | notEqual | less | lessEqual | greater | greaterEqual
  deriving Repr, BEq, Inhabited

inductive LogicOp where
  | and | or | implies | not
  deriving Repr, BEq, Inhabited

inductive Quantifier where
  | forall | exists
  deriving Repr, BEq, Inhabited

inductive AggregateOp where
  | count | sum | minimum | maximum
  deriving Repr, BEq, Inhabited

inductive DeclKind where
  | externalDomain | definedDomain | externalPredicate | constant
  deriving Repr, BEq, Inhabited

def ArithmeticOp.toSource : ArithmeticOp → String
  | .add => "+"
  | .subtract => "-"
  | .multiply => "*"
  | .divide => "/"

def SetOp.toSource : SetOp → String
  | .union => "∪"
  | .intersection => "∩"
  | .difference => "Δ"
  | .symmetricDifference => "⊕"

def CompareOp.toSource : CompareOp → String
  | .equal => "="
  | .notEqual => "!="
  | .less => "<"
  | .lessEqual => "<="
  | .greater => ">"
  | .greaterEqual => ">="

def LogicOp.toSource : LogicOp → String
  | .and => "\\and"
  | .or => "\\or"
  | .implies => "\\impl"
  | .not => "\\neg"

def Quantifier.toSource : Quantifier → String
  | .forall => "\\forall"
  | .exists => "\\exists"

def AggregateOp.toSource : AggregateOp → String
  | .count => "#count"
  | .sum => "#sum"
  | .minimum => "#min"
  | .maximum => "#max"

inductive Expr where
  | var (name : String)
  | constInt (value : Int)
  | constSym (value : String)
  | binary (op : ArithmeticOp) (left right : Expr)
  deriving Repr, BEq, Inhabited

mutual

inductive SetExpr where
  | empty
  | var (name : String) (params : List Expr)
  | pred (name : String)
  | op (op : SetOp) (left right : SetExpr)
  | comprehension (term domainTerm : List Expr) (domain : SetExpr) (condition : Formula)
  deriving Repr, Inhabited

inductive Formula where
  | pred (name : String) (args : List Expr)
  | comp (op : CompareOp) (left right : Expr)
  | logic (op : LogicOp) (items : List Formula)
  | quant (q : Quantifier) (var : String) (body : Formula)
  | agg (op : AggregateOp) (setName : String) (params : List Expr) (compOp : CompareOp) (value : Expr)
  | membership (var : String) (setExpr : SetExpr)
  | subset (left : String) (right : SetExpr)
  | partition (target : String) (parts : List String)
  | bool (value : Bool)
  deriving Repr, Inhabited

end

structure DomainDecl where
  kind : DeclKind
  name : String
  type : TypeNode
  extra : Option String := none
  deriving Repr, BEq, Inhabited

structure Rule where
  head : Formula
  body : List Formula
  isChoice : Bool
  deriving Repr, Inhabited

structure LetExpr where
  name : String
  params : List Expr
  value : SetExpr
  deriving Repr, Inhabited

inductive Statement where
  | rule (r : Rule)
  | constraint (lets : List LetExpr) (formula : Formula)
  deriving Repr, Inhabited

structure Block where
  statements : List Statement
  deriving Repr, Inhabited

structure Program where
  domains : List DomainDecl
  blocks : List Block
  deriving Repr, Inhabited

def joinSep (sep : String) : List String → String
  | [] => ""
  | [x] => x
  | x :: xs => x ++ sep ++ joinSep sep xs

def isUpperIdent (s : String) : Bool :=
  match s.toList with
  | c :: _ => c.isUpper
  | [] => false

def exprToSource : Expr → String
  | .var n => n
  | .constInt n => toString n
  | .constSym s => s
  | .binary op l r => "(" ++ exprToSource l ++ " " ++ op.toSource ++ " " ++ exprToSource r ++ ")"

mutual

partial def setExprToSource : SetExpr → String
  | .empty => "EMPTY"
  | .var n [] => "{" ++ n ++ "}"
  | .var n ps => "{" ++ n ++ "}(" ++ joinSep ", " (ps.map exprToSource) ++ ")"
  | .pred n => "Set_{" ++ n ++ "}"
  | .op op l r => "(" ++ op.toSource ++ " " ++ setExprToSource l ++ " " ++ setExprToSource r ++ ")"
  | .comprehension term domTerm dom cond =>
      "{(" ++ joinSep ", " (term.map exprToSource) ++ ") | (" ++
      joinSep ", " (domTerm.map exprToSource) ++ ") in " ++
      setExprToSource dom ++ ", " ++ formulaToSource cond ++ "}"

partial def formulaToSource : Formula → String
  | .pred n args => n ++ "(" ++ joinSep ", " (args.map exprToSource) ++ ")"
  | .comp op l r => "(" ++ op.toSource ++ " " ++ exprToSource l ++ " " ++ exprToSource r ++ ")"
  | .logic op items => "(" ++ op.toSource ++ " " ++ joinSep " " (items.map formulaToSource) ++ ")"
  | .quant q v body => q.toSource ++ " " ++ v ++ ". " ++ formulaToSource body
  | .agg op setName params compOp value =>
      op.toSource ++ " {" ++ setName ++ "}" ++
      (if params.isEmpty then "" else "(" ++ joinSep ", " (params.map exprToSource) ++ ")") ++
      " " ++ compOp.toSource ++ " " ++ exprToSource value
  | .membership v s => "(\\belonging " ++ v ++ " " ++ setExprToSource s ++ ")"
  | .subset l r => "(\\subset " ++ l ++ " " ++ setExprToSource r ++ ")"
  | .partition target parts => "(\\partition " ++ target ++ " {{" ++ joinSep " " parts ++ "}})"
  | .bool true => "\\true"
  | .bool false => "\\false"

end

end SetLah
