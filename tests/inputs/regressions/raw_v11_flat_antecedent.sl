% B2 reproducer (limits harness flat11): the same shape over 11 variables, the
% second non-monotone failure (8 and 11 fell back; 9, 10, 12, 13 lowered).
ExtDOM S: INT.
ExtPred rel: (S, S).
ExtPred p: (S).

[
    pick(X)? :- dom_S(X).
    (\forall V0, V1, V2, V3, V4, V5, V6, V7, V8, V9, V10. (\impl (\and rel(V0, V1) rel(V1, V2) rel(V2, V3) rel(V3, V4) rel(V4, V5) rel(V5, V6) rel(V6, V7) rel(V7, V8) rel(V8, V9) rel(V9, V10) dom_S(V0) dom_S(V1) dom_S(V2) dom_S(V3) dom_S(V4) dom_S(V5) dom_S(V6) dom_S(V7) dom_S(V8) dom_S(V9) dom_S(V10)) p(V10))).
]
