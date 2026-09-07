% B2 reproducer (limits harness n07): nested universal implications of depth 7.
% Each rewriter pass lowers one level to an auxiliary predicate; the old cap of
% five passes plus the transpiler's one residual reached depth 6, so depth 7
% fell back to a raw-constraint comment.
ExtDOM S: INT.
ExtPred rel: (S, S).
ExtPred p: (S).

[
    pick(X)? :- dom_S(X).
    (\forall V0. (\impl (\and dom_S(V0) pick(V0)) (\forall V1. (\impl (\and dom_S(V1) rel(V0, V1)) (\forall V2. (\impl (\and dom_S(V2) rel(V1, V2)) (\forall V3. (\impl (\and dom_S(V3) rel(V2, V3)) (\forall V4. (\impl (\and dom_S(V4) rel(V3, V4)) (\forall V5. (\impl (\and dom_S(V5) rel(V4, V5)) (\forall V6. (\impl (\and dom_S(V6) rel(V5, V6)) (\forall V7. (\impl (\and dom_S(V7) rel(V6, V7)) p(V7))))))))))))))))).
]
