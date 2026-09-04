ExtDOM Node: INT.
ExtDOM Quorum: INT.
ExtDOM Value: INT.

[
    pre_leader(X0)? :- dom_Node(X0).
    leader(X0)? :- dom_Node(X0).
    member(X0, X1)? :- dom_Node(X0), dom_Quorum(X1).
    votes(X0, X1)? :- dom_Node(X0), dom_Node(X1).
    decided(X0, X1)? :- dom_Node(X0), dom_Value(X1).
    k_pre_fml_n(X)? :- dom_Node(X).
    (\exists X. k_pre_fml_n(X)).
    (\forall X, Y. (\impl (\and k_pre_fml_n(X) k_pre_fml_n(Y)) (= X Y))).
    k_voting_quorum(X)? :- dom_Quorum(X).
    (\exists X. k_voting_quorum(X)).
    (\forall X, Y. (\impl (\and k_voting_quorum(X) k_voting_quorum(Y)) (= X Y))).
    k_v2(X)? :- dom_Value(X).
    (\exists X. k_v2(X)).
    (\forall X, Y. (\impl (\and k_v2(X) k_v2(Y)) (= X Y))).
    k_v1(X)? :- dom_Value(X).
    (\exists X. k_v1(X)).
    (\forall X, Y. (\impl (\and k_v1(X) k_v1(Y)) (= X Y))).
    k_n2(X)? :- dom_Node(X).
    (\exists X. k_n2(X)).
    (\forall X, Y. (\impl (\and k_n2(X) k_n2(Y)) (= X Y))).
    k_n1(X)? :- dom_Node(X).
    (\exists X. k_n1(X)).
    (\forall X, Y. (\impl (\and k_n1(X) k_n1(Y)) (= X Y))).
    aux_0(V_Q1_QUORUM, V_Q2_QUORUM) :- dom_Node(V_N_NODE), member(V_N_NODE, V_Q1_QUORUM), member(V_N_NODE, V_Q2_QUORUM).

    % assert 3
    (\forall K_PRE_FML_N. (\impl k_pre_fml_n(K_PRE_FML_N) (\forall V_V0_NODE. (\impl dom_Node(V_V0_NODE) (\and (\impl (= V_V0_NODE K_PRE_FML_N) leader(V_V0_NODE)) (\impl (\neg (= V_V0_NODE K_PRE_FML_N)) (\and (\impl leader(V_V0_NODE) pre_leader(V_V0_NODE)) (\impl pre_leader(V_V0_NODE) leader(V_V0_NODE))))))))).

]
