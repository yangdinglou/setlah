% B7 reproducer: auxiliary predicate names wrap at five, so a constraint that
% needs a sixth auxiliary reuses __aux_0 and ASP unions two unrelated
% definitions, which also closes a cycle through the auxiliary chain.
% Compiles cleanly, exit 0, wrong program. Depths 1-5 are fine; this is 6.
% With aux_collision_depth6.lp the compiled program derives __aux_0(7), which
% the innermost definition ("some successor of X is not p") forbids, because
% node 7's only successor is 0 and p(0) holds.
ExtDOM S: INT.
ExtPred rel: (S, S).
ExtPred p: (S).

[
    pick(X)? :- dom_S(X).
    (\forall V0. (\impl (\and dom_S(V0) pick(V0)) (\forall V1. (\impl (\and dom_S(V1) rel(V0, V1)) (\forall V2. (\impl (\and dom_S(V2) rel(V1, V2)) (\forall V3. (\impl (\and dom_S(V3) rel(V2, V3)) (\forall V4. (\impl (\and dom_S(V4) rel(V3, V4)) (\forall V5. (\impl (\and dom_S(V5) rel(V4, V5)) (\forall V6. (\impl (\and dom_S(V6) rel(V5, V6)) p(V6))))))))))))))).
]
