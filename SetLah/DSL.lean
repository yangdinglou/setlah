import SetLah.Source
import Lean

namespace SetLah
namespace DSL

def INT : TypeNode := .int
def Symbol : TypeNode := .symbol
def ty (name : String) : TypeNode := .custom name

def v (name : String) : Expr := .var name
def i (value : Int) : Expr := .constInt value
def sym (value : String) : Expr := .constSym value

def add (a b : Expr) : Expr := .binary .add a b
def sub (a b : Expr) : Expr := .binary .subtract a b
def mul (a b : Expr) : Expr := .binary .multiply a b
def div (a b : Expr) : Expr := .binary .divide a b

def extDom (name : String) (t : TypeNode := INT) : DomainDecl :=
  { kind := .externalDomain, name := name, type := t }

def defDomRaw (name : String) (t : TypeNode) (setDef : String) : DomainDecl :=
  { kind := .definedDomain, name := name, type := t, extra := some setDef }

def extPred (name : String) (types : List TypeNode) : DomainDecl :=
  { kind := .externalPredicate, name := name, type := .tuple types }

def const (name : String) (t : TypeNode := INT) (value : Option String := none) : DomainDecl :=
  { kind := .constant, name := name, type := t, extra := value }

def atom (name : String) (args : List Expr := []) : Formula := .pred name args
def eq (a b : Expr) : Formula := .comp .equal a b
def ne (a b : Expr) : Formula := .comp .notEqual a b
def lt (a b : Expr) : Formula := .comp .less a b
def le (a b : Expr) : Formula := .comp .lessEqual a b
def gt (a b : Expr) : Formula := .comp .greater a b
def ge (a b : Expr) : Formula := .comp .greaterEqual a b

def land (items : List Formula) : Formula := .logic .and items
def lor (items : List Formula) : Formula := .logic .or items
def impl (a b : Formula) : Formula := .logic .implies [a, b]
def neg (a : Formula) : Formula := .logic .not [a]

def all (name : String) (body : Formula) : Formula := .quant .forall name body
def ex (name : String) (body : Formula) : Formula := .quant .exists name body

def forallMany (names : List String) (body : Formula) : Formula :=
  names.reverse.foldl (fun f n => all n f) body

def existsMany (names : List String) (body : Formula) : Formula :=
  names.reverse.foldl (fun f n => ex n f) body

def count (setName : String) (params : List Expr) (op : CompareOp) (value : Expr) : Formula :=
  .agg .count setName params op value

def partition (target : String) (parts : List String) : Formula :=
  .partition target parts

def setPred (name : String) : SetExpr := .pred name
def setVar (name : String) (params : List Expr := []) : SetExpr := .var name params

def rule (head : Formula) (body : List Formula := []) : Statement :=
  .rule { head := head, body := body, isChoice := false }

def choice (head : Formula) (body : List Formula := []) : Statement :=
  .rule { head := head, body := body, isChoice := true }

def constraint (f : Formula) : Statement := .constraint [] f

def block (statements : List Statement) : Block := { statements }
def program (domains : List DomainDecl) (blocks : List Block) : Program := { domains, blocks }

def source (p : Program) : String := programToSetLah p

syntax "slv%" str : term
macro_rules
  | `(slv% $s:str) => `(SetLah.DSL.v $s)

syntax "sli%" num : term
macro_rules
  | `(sli% $n:num) => `(SetLah.DSL.i $n)

syntax "atom%" str "[" term,* "]" : term
macro_rules
  | `(atom% $name:str [ $args,* ]) => `(SetLah.DSL.atom $name [ $args,* ])

end DSL
end SetLah
