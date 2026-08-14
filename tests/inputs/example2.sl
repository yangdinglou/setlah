ExtDOM LQ: INT.
ExtDOM PQ: INT.
ExtDOM NC: INT.
ExtDOM Time: INT.

ExtPred l_qubit: (LQ).
ExtPred p_qubit: (PQ).
ExtPred cp: (PQ,PQ).
ExtPred ord: (NC,NC).
ExtPred cl: (NC,LQ,LQ).

Const t: INT.

[
    m(t,L,P)? :- l_qubit(L), p_qubit(P).
    % \forall L. #count {Set_m}(L) = 1.
    % \forall P. #count {Set_m}(P) <= 1.
]

[
    s(t,P1,P2)? :- cp(P1,P2).
    % #count {Set_s} = 1.
    \forall P1,P1',P2,P2'. 
        (\impl 
            (\and s(t,P1,P1') s(t,P2,P2') (> t 0)) 
            (\and (= P1 P2) (= P1' P2'))
        ).
]

