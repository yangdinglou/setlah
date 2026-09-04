% Minimal reproducer (delta-debugged from u1_unsafe_aux_in_context.sl, 61 -> 13 lines).
% Ivy invariant [105] as Ivy writes it: nested one-variable quantifier layers, and an
% existential over an IMPLICATION whose antecedent mentions only the outer variables
% (D1, N1, RES1) and not the bound one (REQ1).
% Compiles with exit 0; Clingo rejects the output (unsafe variable V_D1): the aux rule
% for the existential gets an 'empty domain' cube (not dom_Request(_)) in which the
% antecedent -- the only positive occurrence of D1 -- is logically unnecessary and
% therefore omitted, and no dom_Dbid(D1) guard is added in its place.
% Facts: u1.lp or u1_context.lp (any non-empty domains).
ExtDOM Node: INT.
ExtDOM Request: INT.
ExtDOM Response: INT.
ExtDOM Dbid: INT.
ExtDOM Act: Symbol.
ExtPred act: (Act).
[
    match(R, P)? :- dom_Request(R), dom_Response(P).
    pre_request_sent(N, R)? :- dom_Node(N), dom_Request(R).
    pre_db_response_sent(I, P)? :- dom_Dbid(I), dom_Response(P).
    pre_t(I, N)? :- dom_Dbid(I), dom_Node(N).
    (\forall V_D1. (\impl dom_Dbid(V_D1) (\forall V_N1. (\impl dom_Node(V_N1) (\forall V_RES1. (\impl dom_Response(V_RES1) (\exists V_REQ1. (\and dom_Request(V_REQ1) (\impl (\and pre_db_response_sent(V_D1, V_RES1) pre_t(V_D1, V_N1)) (\and match(V_REQ1, V_RES1) pre_request_sent(V_N1, V_REQ1))))))))))).
]
