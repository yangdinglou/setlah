# Provenance of the techniques on branch `grounding-split`

Which parts of the direct lowering and its new pass come from which
published techniques, so that the paper can cite them and readers can
tell what is borrowed from what is ours. Written 2026-09-11.

## 1. The rule-decomposition pass (`DirectLowerer._split_cube`, `--split-width`)

| element | based on | where it differs |
|---|---|---|
| splitting one wide integrity constraint into several rules over fewer variables, one per bag of a tree decomposition of the rule's variable graph | Morak and Woltran, "Preprocessing of complex non-ground rules in answer set programming" (LPNMR 2012); Bichler, Morak, Woltran, "lpopt: A Rule Optimization Tool for Answer Set Programming" (WLP/WFLP 2016; Fundamenta Informaticae 2020). lpopt computes a tree decomposition of minimal width and emits one rule per bag, bottom-up. | applied inside the compiler at the point where the lowering emits constraints, not as a program-level preprocessor; only to integrity constraints, not to rules with heads; only above a width threshold |
| the elimination-order heuristic (min-fill, ties by degree) that produces the bags | the standard greedy treewidth heuristics (Bodlaender and Koster, "Treewidth computations I: Upper bounds", Information and Computation 2010) | lpopt uses the htd library's decompositions; ours is a 20-line min-fill, adequate for cubes of tens of variables |
| the bag rule's arguments being the bag's separator (the eliminated variable's neighbours), children consumed by the first later bag that covers their arguments | the lpopt construction | none |
| soundness argument: temporaries are fresh, stratified, positively defined, so answer sets projected on the original signature are unchanged (a conservative extension) | the correctness argument of lpopt; the same "equi-assignability" notion the SetLah! paper already uses for auxiliary predicates (Tseitin; "Tseitin or not Tseitin" in the paper's references) | none |
| domain guards `dom_T(V)` for every bag variable no positive literal binds | the direct lowering's own guard mechanism for auxiliary predicates (`make_aux`), which uses the checker's variable types; the egglog path relied on the safety pass (B6) | none |
| the width threshold as the trigger | FM-Darwin's clause splitting for finite-model finding (Baumgartner, Fuchs, de Nivelle, Tinelli, "Computing finite models by reduction to function-free clause logic", J. Applied Logic 2009), which fmc2iasp relied on (Gebser, Sabuncu, Schaub, "Finite Model Computation via Answer Set Programming", IJCAI 2011); Paradox's clause splitting (Claessen and Sörensson, "New techniques that improve MACE-style finite model finding", 2003) | those split clauses greedily in two through a fresh relation chosen freely (an equisatisfiable split); ours is the full decomposition with positively defined temporaries, which preserves answer sets rather than only satisfiability |

What is ours: putting the decomposition at the cube level of the
lowering so that it composes with conjunction splitting and quantifier
elimination (below), the threshold trigger and its measurement on the
study's corpora, and the guard construction.

## 2. The direct lowering it sits in (branch `direct-lowering`, commit 5fbe0b6 onward)

| element | based on |
|---|---|
| negation normal form of the violated formula, DNF cubes, one integrity constraint per cube | the classic encoding of clauses as integrity constraints (Simons, Niemelä, Soininen, "Extending and implementing the stable model semantics", AIJ 2002), which fmc2iasp also uses; the SetLah! paper's "conversion to IC form" |
| conjunction splitting (`forall X. (A and B)` into two constraints) | the SetLah! paper, phase 1; it is the formula-level analogue of putting each conjunct in its own rule and never introduces predicates |
| auxiliary predicates for quantifier alternations (`forall X. exists Y. psi` into `aux(X) :- cubes`, `:- not aux(X)`) | the SetLah! paper's auxiliary-based quantifier elimination, essentially Skolemisation into a defined predicate; the direct lowering reproduces what the egglog rules did, without the e-graph |
| inlining an existential over one positive literal with anonymous variables | the egglog rule `exists_to_anonymous` of the previous front half |
| aggregate-based elimination of a single existential block (`#count{...} = 0`) | the SetLah! paper's aggregate-based quantifier elimination; related to Dingess and Truszczynski's "Automated Aggregator" rewriting (2020) |
| bounding the DNF (`MAX_DNF_CUBES`) by turning large subformulas into auxiliaries | the direct lowering's own device; the same trade-off lpopt makes between rule count and rule width |
| symmetry breaking `not X = Y` to `X < Y` only where the constraint is symmetric (fix of B10) | the least-number and constant-ordering heuristics of finite-model finders (Zhang 1996; Claessen and Sörensson 2003), restricted to the symmetric case |

## 3. Techniques considered and not adopted here

| technique | reference | why not (yet) |
|---|---|---|
| body-decoupled grounding | Besin, Hecher, Woltran, "Body-decoupled grounding via solving" (KR 2022) | changes who does the join rather than the number of variables; pays on dense rules where decomposition cannot help; would be a per-constraint alternative chosen by estimated ground size |
| hybrid grounding (per-rule choice between semi-naive grounding and BDG by structural and data-driven estimates) | Beiser, Hecher, Unalan, Woltran, "Bypassing the ASP Bottleneck: Hybrid Grounding by Splitting and Rewriting" (IJCAI 2024); "Automated Hybrid Grounding Using Structural and Data-Driven Heuristics" (TPLP 2025) | the estimate they compute from the instance is one the compiler could compute from declared domains; a natural follow-up once decomposition alone stops paying |
| constraints as propagators, blended grounding and compilation | Cuteri, Dodaro, Ricca, Schüller, "Overcoming the grounding bottleneck due to constraints in ASP solving" (IJCAI 2020); Dodaro, Mazzotta, Ricca, "Blending Grounding and Compilation for Efficient ASP Solving" (KR 2024) | needs a modified solver; the right tool for constraints with astronomically many instances and few violations (the VCh-rf channel closure is the study's example) |
| lazy grounding | Weinzierl, Alpha (2017) | a different solver |
| incremental grounding over the domain size | Gebser, Sabuncu, Schaub 2011 (iClingo); clingo's multi-shot API | a runtime mode for size sweeps, not a lowering; measured by the fmc2iasp paper at about a second on average |
| sort inference | Claessen and Sörensson 2003; Baumgartner et al. 2009 | belongs in a translator; SetLah! users declare sorts |

## 4. The study-side expert arm these numbers are compared with

`corpus/tools/cnf2fmc.py` in setlah-apps reproduces fmc2iasp with today's
tools: Vampire's clausifier in place of FM-Darwin; McCune's flattening
(MACE, 1994); term values reified as `assign(T, D)` with one cardinality
rule per term for uniqueness and totality; constants ordered for symmetry
breaking (the paper's rule, from Claessen and Sörensson); clauses as
integrity constraints; greedy or tree-decomposition clause splitting.

## References

- Baumgartner, Fuchs, de Nivelle, Tinelli. Computing finite models by reduction to function-free clause logic. J. Applied Logic 7(1), 2009.
- Beiser, Hecher, Unalan, Woltran. Bypassing the ASP Bottleneck: Hybrid Grounding by Splitting and Rewriting. IJCAI 2024.
- Besin, Hecher, Woltran. Body-decoupled grounding via solving: a novel approach for the ground-and-solve paradigm. KR 2022.
- Bichler, Morak, Woltran. lpopt: A Rule Optimization Tool for Answer Set Programming. WFLP 2016; Fundamenta Informaticae 177, 2020.
- Bodlaender, Koster. Treewidth computations I: Upper bounds. Information and Computation 208(3), 2010.
- Claessen, Sörensson. New techniques that improve MACE-style finite model finding. CADE-19 Workshop on Model Computation, 2003.
- Cuteri, Dodaro, Ricca, Schüller. Overcoming the grounding bottleneck due to constraints in ASP solving: constraints become propagators. IJCAI 2020.
- Dodaro, Mazzotta, Ricca. Blending Grounding and Compilation for Efficient ASP Solving. KR 2024.
- Gebser, Sabuncu, Schaub. Finite Model Computation via Answer Set Programming. IJCAI 2011.
- McCune. A Davis-Putnam program and its application to finite first-order model search. ANL/MCS-TM-194, 1994.
- Morak, Woltran. Preprocessing of complex non-ground rules in answer set programming. LPNMR 2012.
- Simons, Niemelä, Soininen. Extending and implementing the stable model semantics. AIJ 138, 2002.
- Zhang. Constructing finite algebras with FALCON. J. Automated Reasoning 17(1), 1996.
