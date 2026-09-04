ExtDOM Request: INT.
ExtDOM Node: INT.
ExtDOM Db_request_id: INT.
ExtDOM Response: INT.

[
    t(X0, X1)? :- dom_Db_request_id(X0), dom_Node(X1).
    db_response_sent(X0, X1)? :- dom_Db_request_id(X0), dom_Response(X1).
    db_request_sent(X0, X1)? :- dom_Db_request_id(X0), dom_Request(X1).
    response_received(X0, X1)? :- dom_Node(X0), dom_Response(X1).
    response_sent(X0, X1)? :- dom_Node(X0), dom_Response(X1).
    request_sent(X0, X1)? :- dom_Node(X0), dom_Request(X1).
    k_res1(X)? :- dom_Response(X).
    (\exists X. k_res1(X)).
    (\forall X, Y. (\impl (\and k_res1(X) k_res1(Y)) (= X Y))).
    k_n1(X)? :- dom_Node(X).
    (\exists X. k_n1(X)).
    (\forall X, Y. (\impl (\and k_n1(X) k_n1(Y)) (= X Y))).

    % assert 6
    (\forall K_N1, K_RES1. (\impl (\and k_n1(K_N1) k_res1(K_RES1)) (\neg (\or response_sent(K_N1, K_RES1) (\neg response_received(K_N1, K_RES1)))))).

]
