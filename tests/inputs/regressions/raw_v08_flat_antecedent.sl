% B2 reproducer (limits harness flat08): one universal implication with a flat
% conjunctive antecedent over 8 variables fell back to a raw-constraint comment
% while 7 and 9 variables lowered. With raw_v08.lp: p holds on the end of the
% only 7-step rel path, so SAT (256 answer sets: pick is unconstrained); drop
% p(6) and the program must be UNSAT.
ExtDOM S: INT.
ExtPred rel: (S, S).
ExtPred p: (S).

[
    pick(X)? :- dom_S(X).
    (\forall V0, V1, V2, V3, V4, V5, V6, V7. (\impl (\and rel(V0, V1) rel(V1, V2) rel(V2, V3) rel(V3, V4) rel(V4, V5) rel(V5, V6) rel(V6, V7) dom_S(V0) dom_S(V1) dom_S(V2) dom_S(V3) dom_S(V4) dom_S(V5) dom_S(V6) dom_S(V7)) p(V7))).
]
