% B11 reproducer (limits harness flat13): the egglog path emits an auxiliary rule
% whose body is the single token '?', so the program does not parse; exit 0.
% The direct lowering (--lowering direct) compiles it correctly.
ExtDOM S: INT.
ExtPred rel: (S, S).
ExtPred p: (S).

[
    pick(X)? :- dom_S(X).
    (\forall V0, V1, V2, V3, V4, V5, V6, V7, V8, V9, V10, V11, V12. (\impl (\and rel(V0, V1) rel(V1, V2) rel(V2, V3) rel(V3, V4) rel(V4, V5) rel(V5, V6) rel(V6, V7) rel(V7, V8) rel(V8, V9) rel(V9, V10) rel(V10, V11) rel(V11, V12) dom_S(V0) dom_S(V1) dom_S(V2) dom_S(V3) dom_S(V4) dom_S(V5) dom_S(V6) dom_S(V7) dom_S(V8) dom_S(V9) dom_S(V10) dom_S(V11) dom_S(V12)) p(V12))).
]
